"""Single-claim execution worker and recording upstreams used by acceptance tests."""

from __future__ import annotations

import json
import asyncio
import queue
import re
import threading
import time
from typing import Iterable, Protocol
from urllib import request as urlrequest

from .service import ClassroomService

_BEARER_RE = re.compile(r"(?i)(bearer\s+)\S+")


class UpstreamError(RuntimeError):
    """A known provider/network failure; classroom charge is released."""


class UnknownOutcome(UpstreamError):
    """The provider may have accepted the request but its result is unknown."""


class Upstream(Protocol):
    def generate(self, payload: dict, *, request_id: str) -> Iterable[str]: ...


def _redact_upstream_text(text: str) -> str:
    return _BEARER_RE.sub(r"\1***", (text or "").replace("\n", " ").strip())[:240]


def _wrap_upstream_exc(exc: BaseException) -> UpstreamError:
    if isinstance(exc, UpstreamError):
        return exc
    detail = _redact_upstream_text(str(exc))
    name = type(exc).__name__
    suffix = f"{name}: {detail}" if detail else name
    return UpstreamError(f"provider stream failed validation or transport ({suffix})")


def _parts_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = []
        for part in value:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks)
    return ""


def _choice_text(choice: dict) -> str:
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
    content = _parts_text(message.get("content")) or _parts_text(delta.get("content"))
    reasoning = _parts_text(message.get("reasoning_content")) or _parts_text(delta.get("reasoning_content"))
    # A separate reasoning field must never override a provided final answer.
    return content or reasoning


def _completion_text_from_payload(event: dict) -> str:
    if not isinstance(event, dict) or event.get("error"):
        raise UpstreamError("provider returned an error event")
    choices = event.get("choices") or []
    if not choices:
        raise UpstreamError("provider stream was truncated or contained no answer")
    if len(choices) != 1:
        raise UpstreamError("provider returned multiple completions")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise UpstreamError("invalid provider content event")
    if choice.get("finish_reason") not in {None, "stop", "length"}:
        raise UpstreamError("provider did not complete a supported answer")
    text = _choice_text(choice)
    if not text:
        raise UpstreamError("provider stream was truncated or contained no answer")
    return text


class RecordingUpstream:
    """Deterministic fake provider: records exactly one call per request."""

    def __init__(self, outputs: dict[str, list[str]] | None = None, *, default: list[str] | None = None,
                 error: Exception | None = None):
        self.outputs = outputs or {}
        self.default = default if default is not None else ["模拟回答"]
        self.error = error
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def generate(self, payload: dict, *, request_id: str, **_kwargs) -> Iterable[str]:
        with self._lock:
            self.calls.append({"request_id": request_id, "payload": payload})
        if self.error:
            raise self.error
        return list(self.outputs.get(request_id, self.default))


class HttpUpstream:
    """Minimal OpenAI-compatible streaming client for the managed provider.

    The API key is supplied by a callback so it never enters classroom
    settings, request snapshots, or exception messages.
    """

    def __init__(self, endpoint: str, api_key_getter, *, timeout: float = 10,
                 first_output_timeout: float = 60, total_timeout: float = 300,
                 complete_timeout: float = 120, complete_read_timeout: float = 90,
                 max_output_bytes: int = 2 * 1024 * 1024, transport=None):
        if not endpoint.startswith("https://"):
            raise ValueError("managed upstream endpoint must use HTTPS")
        self.endpoint = endpoint.rstrip("/") + "/chat/completions"
        self.api_key_getter = api_key_getter
        self.timeout = timeout
        self.first_output_timeout = first_output_timeout
        self.total_timeout = total_timeout
        self.complete_timeout = complete_timeout
        self.complete_read_timeout = complete_read_timeout
        self.max_output_bytes = max_output_bytes
        self.transport = transport
        self._active = {}
        self._lock = threading.Lock()

    def cancel(self, request_id: str) -> None:
        with self._lock:
            execution = self._active.get(request_id)
        if execution:
            loop, task = execution
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # The connection has already been closed.

    def _generate_complete(self, payload: dict, request_id: str, *,
                           total_timeout: float | None = None, read_timeout: float | None = None) -> Iterable[str]:
        import httpx
        body = dict(payload)
        body["stream"] = False
        body["metadata"] = {"classroom_request_id": request_id}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key_getter()}",
            "X-Classroom-Request-ID": request_id,
        }
        overall = self.complete_timeout if total_timeout is None else total_timeout
        read = self.complete_read_timeout if read_timeout is None else read_timeout
        async def complete():
            with self._lock:
                self._active[request_id] = (asyncio.get_running_loop(), asyncio.current_task())
            try:
                timeout = httpx.Timeout(self.timeout, read=read)
                async with httpx.AsyncClient(timeout=timeout, transport=self.transport, follow_redirects=False) as client:
                    async with asyncio.timeout(overall):
                        async with client.stream("POST", self.endpoint, content=raw, headers=headers) as response:
                            try:
                                response.raise_for_status()
                            except httpx.HTTPStatusError as exc:
                                body_text = ""
                                try:
                                    body_text = (await response.aread()).decode("utf-8", "replace")[:300]
                                except Exception:
                                    body_text = ""
                                if exc.response is not None and exc.response.status_code in {400, 422}:
                                    raise UpstreamError(
                                        f"provider rejected complete request ({exc.response.status_code}): {body_text}"
                                    ) from exc
                                raise
                            data = bytearray()
                            async for chunk in response.aiter_bytes():
                                data.extend(chunk)
                                if len(data) > self.max_output_bytes + 65536:
                                    raise UpstreamError("provider response exceeds configured limit")
                            return json.loads(data)
            except asyncio.CancelledError as exc:
                raise UpstreamError("provider execution cancelled") from exc
            except Exception as exc:
                raise _wrap_upstream_exc(exc) from exc
            finally:
                with self._lock:
                    self._active.pop(request_id, None)

        event = asyncio.run(complete())
        text = _completion_text_from_payload(event)
        if len(text.encode("utf-8")) > self.max_output_bytes:
            raise UpstreamError("provider answer exceeds configured limit")
        yield text

    def generate(self, payload: dict, *, request_id: str,
                 total_timeout: float | None = None, read_timeout: float | None = None) -> Iterable[str]:
        body = dict(payload)
        if body.get("stream") is False:
            yield from self._generate_complete(body, request_id, total_timeout=total_timeout, read_timeout=read_timeout)
            return
        body["stream"] = True
        body["metadata"] = {"classroom_request_id": request_id}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key_getter()}",
            "X-Classroom-Request-ID": request_id,
        }
        events = queue.Queue(maxsize=32)
        abandoned = threading.Event()
        finished = threading.Event()
        result = []

        async def publish(text):
            while not abandoned.is_set():
                try:
                    events.put_nowait(text)
                    return
                except queue.Full:
                    await asyncio.sleep(0.01)
            raise asyncio.CancelledError

        async def produce():
            import httpx
            loop = asyncio.get_running_loop()
            with self._lock:
                self._active[request_id] = (loop, asyncio.current_task())
            started = time.monotonic()
            visible = 0
            done = False
            try:
                timeout = httpx.Timeout(self.timeout, read=self.first_output_timeout)
                async with httpx.AsyncClient(timeout=timeout, transport=self.transport, follow_redirects=False) as client:
                    async with asyncio.timeout(self.total_timeout):
                        async with client.stream("POST", self.endpoint, content=raw, headers=headers) as response:
                            response.raise_for_status()
                            content_type = response.headers.get("content-type", "")
                            if "text/event-stream" not in content_type:
                                raw_body = await response.aread()
                                text = _completion_text_from_payload(json.loads(raw_body.decode("utf-8")))
                                if len(text.encode("utf-8")) > self.max_output_bytes:
                                    raise UpstreamError("provider answer exceeds configured limit")
                                await publish(text)
                                return
                            stream = response.aiter_lines().__aiter__()
                            while True:
                                remaining = (self.total_timeout if visible else self.first_output_timeout) - (time.monotonic() - started)
                                if remaining <= 0:
                                    raise TimeoutError
                                try:
                                    line = await asyncio.wait_for(stream.__anext__(), timeout=remaining)
                                except StopAsyncIteration:
                                    break
                                if len(line) > 1024 * 1024:
                                    raise UpstreamError("provider event is too large")
                                if not line.startswith("data:"):
                                    continue
                                value = line[5:].strip()
                                if value == "[DONE]":
                                    done = True
                                    break
                                event = json.loads(value)
                                if not isinstance(event, dict) or event.get("error"):
                                    raise UpstreamError("provider returned an error event")
                                choices = event.get("choices", [])
                                if not choices:
                                    continue  # A usage event is not visible output.
                                if len(choices) != 1:
                                    raise UpstreamError("provider returned multiple completions")
                                choice = choices[0]
                                if choice.get("finish_reason") not in {None, "stop", "length"}:
                                    raise UpstreamError("provider did not complete a supported answer")
                                delta = choice.get("delta", {}).get("content")
                                if delta is not None and not isinstance(delta, str):
                                    raise UpstreamError("invalid provider content event")
                                if delta:
                                    visible += len(delta.encode("utf-8"))
                                    if visible > self.max_output_bytes:
                                        raise UpstreamError("provider answer exceeds configured limit")
                                    await publish(delta)
                            if not done or not visible:
                                raise UpstreamError("provider stream was truncated or contained no answer")
            except asyncio.CancelledError:
                result.append(UpstreamError("provider execution cancelled"))
            except TimeoutError:
                result.append(UnknownOutcome("provider timeout; outcome is unknown"))
            except UpstreamError as exc:
                result.append(exc)
            except Exception as exc:
                result.append(_wrap_upstream_exc(exc))
            finally:
                with self._lock:
                    self._active.pop(request_id, None)
                finished.set()  # AsyncClient has closed before releasing the slot.

        thread = threading.Thread(target=lambda: asyncio.run(produce()), name="classroom-provider", daemon=True)
        thread.start()
        try:
            while not finished.is_set() or not events.empty():
                try:
                    yield events.get(timeout=0.1)
                except queue.Empty:
                    continue
            if result:
                raise result[0]
        finally:
            abandoned.set()
            self.cancel(request_id)
            # A timeout here must never release a reservation while the actual
            # transport remains alive. Cancellation closes the async client;
            # retain the execution slot until its producer has really exited.
            thread.join()


class ClassroomWorker:
    def __init__(self, service: ClassroomService, upstream: Upstream, *, worker_instance_id: str | None = None):
        self.service = service
        self.upstream = upstream
        self.worker_instance_id = worker_instance_id or service.worker_instance_id
        if hasattr(upstream, "cancel"):
            service.cancel_upstream = upstream.cancel

    def run_one(self) -> dict | None:
        claimed = self.service.claim_next(self.worker_instance_id)
        if not claimed:
            return None
        request = claimed["request"]
        request_id = request["id"]
        claim_token = claimed["claim_token"]
        try:
            provider_payload = self.service.materialize_provider_payload(request_id, claimed["payload"])
            self.service.mark_dispatched(request_id, claim_token)
            stream = iter(self.upstream.generate(provider_payload, request_id=request_id))
            try:
                for delta in stream:
                    state = self.service._get_request(request_id)
                    if self.service.is_final(request_id) or state["cancel_source"]:
                        break
                    if isinstance(delta, str) and delta:
                        self.service.append_event(request_id, "delta", {"text": delta})
            finally:
                if hasattr(stream, "close"):
                    stream.close()
            return self.service.finalize(request_id, outcome="completed", actor_id="worker", reason="provider completed")
        except UnknownOutcome as exc:
            return self.service.finalize(request_id, outcome="interrupted_unknown", actor_id="upstream", reason=str(exc), error_code="UPSTREAM_OUTCOME_UNKNOWN")
        except Exception as exc:
            return self.service.finalize(request_id, outcome="interrupted", actor_id="upstream", reason="provider interruption", error_code=type(exc).__name__)

    def run_until_empty(self, max_jobs: int = 100) -> list[dict]:
        results = []
        for _ in range(max(0, max_jobs)):
            result = self.run_one()
            if result is None:
                break
            results.append(result)
        return results
