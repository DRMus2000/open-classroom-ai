"""Teacher conversations through the configured provider, without student quota."""
import asyncio
import json
import logging
import threading
import uuid

from .canonical import normalize_payload
from .errors import ConflictError, ForbiddenError, NotReadyError


class TeacherChat:
    def __init__(self, service, runtime):
        self.service, self.runtime = service, runtime
        self.active = set()
        self._active_lock = threading.Lock()

    def response(self, user_id, body):
        from fastapi.responses import StreamingResponse
        if self.runtime is None or not self.service.ready_report()['ready']:
            raise NotReadyError('课堂模型服务尚未就绪')
        payload = normalize_payload(body)
        if payload['model'] not in self.service.allowed_models:
            raise ForbiddenError('只能使用课堂配置的模型')
        for ref in payload['attachments']:
            stored = self.service.attachments.get(ref['id'], user_id=user_id)
            if stored['sha256'].lower() != ref['sha256']:
                raise ForbiddenError('附件内容校验失败')
        attachment_ids = [ref['id'] for ref in payload['attachments']]
        payload['attachments'] = attachment_ids
        payload = self.service.materialize_provider_payload(None, payload)
        with self._active_lock:
            if user_id in self.active or len(self.active) >= self.service.max_concurrency:
                raise ConflictError('老师对话正在生成，请等待完成后重试')
            self.active.add(user_id)
        request_id = 'teacher-' + uuid.uuid4().hex
        upstream = self.runtime.worker.upstream

        def chunk(delta, finish=None):
            return 'data: ' + json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                'model': 'classroom_pipe', 'choices': [{'index': 0, 'delta': delta,
                'finish_reason': finish}]}, ensure_ascii=False) + '\n\n'

        async def events():
            iterator = None
            pending = None
            sentinel = object()
            try:
                if attachment_ids:
                    self.service.attachments.begin_use(attachment_ids)
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
                logging.getLogger(__name__).warning('Teacher provider request %s failed (%s)', request_id, type(exc).__name__)
                yield 'data: ' + json.dumps({'error': {'message': '老师对话调用失败，请检查模型名称、API Key 和服务地址，或查看服务日志。'}}, ensure_ascii=False) + '\n\n'
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
                with self._active_lock:
                    self.active.discard(user_id)
                if attachment_ids:
                    self.service.attachments.end_use(attachment_ids)
        return StreamingResponse(events(), media_type='text/event-stream')
