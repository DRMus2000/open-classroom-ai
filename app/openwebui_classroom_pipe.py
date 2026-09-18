"""Async native Pipe: submit once and relay durable events from the service."""
import asyncio
import json


class Pipe:
    def __init__(self):
        self.type = 'pipe'
        self.name = '课堂 AI'

    async def pipe(self, body: dict, __user__: dict, __metadata__: dict, __request__):
        from fastapi.responses import StreamingResponse
        client = __request__.app.state.classroom_client
        identity = getattr(__request__.state, 'classroom_identity', None)
        operation = getattr(__request__.state, 'classroom_operation_id', None)
        if not identity or identity.get('user_id') != __user__.get('id') or not operation:
            raise RuntimeError('课堂原生身份或操作 ID 缺失')
        metadata = __metadata__ or {}
        messages = [m for m in body.get('messages', []) if m.get('role') == 'user']
        if not messages:
            raise RuntimeError('请输入问题')
        settings = await client.request('GET', '/api/classroom/v1/me', principal=identity)
        if settings.status_code != 200 or not settings.json().get('allowed_models'):
            raise RuntimeError('课堂模型配置不可用')
        model = settings.json()['allowed_models'][0]
        attachments = (await client.control('identity/files-resolve', {'user_id': identity['user_id'],
            'operation_id': operation, 'native_file_ids': getattr(__request__.state, 'classroom_native_file_ids', [])}))['attachments']
        message = dict(messages[-1])
        if attachments and isinstance(message.get('content'), list):
            message['content'] = [p for p in message['content'] if p.get('type') == 'text']
        if identity.get('role') == 'admin':
            history = [dict(m) for m in body.get('messages', []) if m.get('role') in {'system', 'user', 'assistant'} and m.get('content')]
            if history and history[-1].get('role') == 'user':
                history[-1] = message
            return await client.download('/api/classroom/v1/admin/chat/completions', identity,
                method='POST', body={'model': model, 'messages': history, 'attachments': attachments})
        response = await client.request('POST', '/api/classroom/v1/requests', principal=identity,
            extra_headers={'Idempotency-Key': operation}, body={
                'operation_id': operation,
                'chat_id': metadata.get('chat_id'),
                'user_message_id': metadata.get('user_message_id'),
                'assistant_message_id': metadata.get('message_id') or operation,
                'parent_message_id': getattr(__request__.state, 'classroom_parent_message_id', None),
                'payload': {'model': model, 'messages': [message], 'attachments': attachments},
                'attachment_ids': [a['id'] for a in attachments],
            })
        if response.status_code >= 400:
            raise RuntimeError(response.json().get('error', {}).get('message', '课堂提交失败'))
        request_id = response.json()['id']
        prefix = '/api/classroom/v1/requests/' + request_id

        async def events():
            seq = 0
            yield ': classroom_request_id=' + request_id + '\n\n'
            while True:
                response = await client.request('GET', prefix + '/events?after_seq=' + str(seq), principal=identity)
                if response.status_code >= 400:
                    raise RuntimeError('课堂会话或服务不可用，请在状态页恢复请求')
                batch = response.json()['events']
                for event in batch:
                    seq = event['seq']
                    if event['event_type'] == 'delta':
                        chunk = {'id': request_id, 'object': 'chat.completion.chunk', 'model': 'classroom_pipe',
                                 'choices': [{'index': 0, 'delta': {'content': event['payload']['text']}, 'finish_reason': None}]}
                        yield 'data: ' + json.dumps(chunk, ensure_ascii=False) + '\n\n'
                        # The native browser integration acknowledges rendered
                        # output. Server-side consumption is not delivery.
                response = await client.request('GET', prefix, principal=identity)
                if response.status_code >= 400:
                    raise RuntimeError('课堂状态不可用')
                state = response.json()
                if state['status'] not in {'pending', 'approved_queued', 'generating'}:
                    # A completed answer may span several 1000-event pages.
                    # Drain through the durable output sequence before DONE.
                    if seq < state.get('output_seq', 0):
                        continue
                    if state['status'] != 'completed':
                        yield 'data: ' + json.dumps({'error': {'message': '课堂请求结束：' + state['status']}}, ensure_ascii=False) + '\n\n'
                    else:
                        yield 'data: ' + json.dumps({'id': request_id, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}) + '\n\n'
                    yield 'data: [DONE]\n\n'
                    return
                yield ': waiting\n\n'
                await asyncio.sleep(0.05)
        return StreamingResponse(events(), media_type='text/event-stream')
