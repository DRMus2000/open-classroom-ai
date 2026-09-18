"""Guest link conversations: no login/session, shared token, unlimited use."""
import asyncio
import json
import logging
import threading
import uuid

from .canonical import normalize_payload
from .errors import ConflictError, ForbiddenError, NotReadyError, ValidationError


class GuestChat:
    """Stream classroom-model replies for temporary guest links.

    Concurrent guests share one semaphore (default 64). There is no per-browser
    session table; each request re-validates the shared token.
    """

    def __init__(self, service, runtime, *, max_concurrency: int = 64):
        self.service, self.runtime = service, runtime
        self.max_concurrency = max(1, int(max_concurrency))
        self._active = 0
        self._lock = threading.Lock()

    def response(self, body):
        from fastapi.responses import StreamingResponse
        if self.runtime is None or not self.service.ready_report()['ready']:
            raise NotReadyError('课堂模型服务尚未就绪')
        if self.service._classroom_paused():
            raise ForbiddenError('全班 AI 已暂停，访客链接暂时不可用')
        payload = normalize_payload(body)
        if payload['model'] not in self.service.allowed_models:
            raise ForbiddenError('只能使用课堂配置的模型')
        if payload.get('attachments'):
            raise ForbiddenError('访客链接暂不支持附件')
        last = payload['messages'][-1] if payload['messages'] else None
        if not last or last.get('role') != 'user':
            raise ValidationError('请提交当前用户提问')
        current = last.get('content')
        current_text = current if isinstance(current, str) else '\n'.join(
            part.get('text', '') for part in current if isinstance(part, dict) and part.get('type') == 'text'
        )
        if len(current_text) > 1000:
            raise ValidationError('提问不能超过 1000 字')
        payload['attachments'] = []
        payload['messages'] = self.service.apply_system_prompt(payload['messages'])
        payload = self.service.materialize_provider_payload(None, payload)
        with self._lock:
            if self._active >= self.max_concurrency:
                raise ConflictError('访客并发已满，请稍后再试')
            self._active += 1
        request_id = 'guest-' + uuid.uuid4().hex
        upstream = self.runtime.worker.upstream

        def chunk(delta, finish=None):
            return 'data: ' + json.dumps({
                'id': request_id, 'object': 'chat.completion.chunk',
                'model': 'classroom_pipe',
                'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}],
            }, ensure_ascii=False) + '\n\n'

        async def events():
            iterator = None
            pending = None
            sentinel = object()
            try:
                iterator = iter(upstream.generate(payload, request_id=request_id))
                while True:
                    pending = asyncio.create_task(asyncio.to_thread(next, iterator, sentinel))
                    while not pending.done():
                        done, _ = await asyncio.wait({pending}, timeout=15)
                        if not done:
                            yield ': waiting\n\n'
                    text = pending.result()
                    if text is sentinel:
                        break
                    yield chunk({'content': text})
                yield chunk({}, 'stop')
                yield 'data: [DONE]\n\n'
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    'Guest provider request %s failed (%s)', request_id, type(exc).__name__)
                yield 'data: ' + json.dumps({
                    'error': {'message': '访客对话调用失败，请稍后重试或联系老师。'},
                }, ensure_ascii=False) + '\n\n'
                yield 'data: [DONE]\n\n'
            finally:
                cancel = getattr(upstream, 'cancel', None)
                if cancel:
                    cancel(request_id)
                if pending is not None:
                    try:
                        await asyncio.shield(pending)
                    except Exception:
                        pass
                if iterator is not None and hasattr(iterator, 'close'):
                    await asyncio.to_thread(iterator.close)
                with self._lock:
                    self._active = max(0, self._active - 1)

        return StreamingResponse(events(), media_type='text/event-stream')
