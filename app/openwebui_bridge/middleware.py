"""Native identity validation and default-deny student capability boundary."""
import json
import re
from urllib.parse import urlsplit
from http.cookies import SimpleCookie

CHAT_PATHS = {"/api/chat/completions", "/api/v1/chat/completions"}
PUBLIC_GET = {"/health", "/api/config", "/api/version", "/api/changelog"}
PUBLIC_POST = {"/api/v1/auths/signin"}
SAFE_CHAT = re.compile(r"^/api/v1/chats(?:/(?:list|new|search|pinned|all|archived|config|[a-zA-Z0-9-]+)(?:/(?:pin|archive|tags|messages/[a-zA-Z0-9-]+))?)?/?$")
# Native provider / capability exits that must stay on the classroom pipe for every role.
MODEL_EGRESS_PREFIXES = (
    '/openai/', '/ollama/',
    '/api/embeddings', '/api/v1/embeddings',
    '/api/v1/messages', '/api/message',
    '/api/v1/audio', '/api/v1/images',
    '/api/completions', '/api/v1/completions',
)


class ClassroomRouteGuardMiddleware:
    def __init__(self, app, *, client=None, verifier=None, require_bootstrap=False):
        self.app, self.client, self.verifier = app, client, verifier
        self.require_bootstrap = require_bootstrap

    async def __call__(self, scope, receive, send):
        if scope['type'] not in {'http', 'websocket'}:
            return await self.app(scope, receive, send)
        websocket = scope['type'] == 'websocket'
        path, method = scope.get('path', ''), scope.get('method', 'GET')
        headers = {k.decode('latin1').lower(): v.decode('latin1') for k, v in scope.get('headers', [])}

        async def deny(status=403, message='学生模型请求必须经过课堂模型出口', code='CLASSROOM_PIPE_REQUIRED'):
            if websocket:
                await send({'type': 'websocket.close', 'code': 1008})
            else:
                raw = json.dumps({'error': {'code': code, 'message': message, 'retryable': False}}, ensure_ascii=False).encode()
                await send({'type': 'http.response.start', 'status': status, 'headers': [(b'content-type', b'application/json; charset=utf-8'), (b'cache-control', b'no-store')]})
                await send({'type': 'http.response.body', 'body': raw})

        origin = headers.get('origin')
        if origin and (method not in {'GET', 'HEAD'} or websocket) and urlsplit(origin).netloc.lower() != headers.get('host', '').lower():
            return await deny(403, '请求来源不匹配', 'ORIGIN_REJECTED')
        if not websocket and ((method in {'GET', 'HEAD'} and (path in PUBLIC_GET or not path.startswith(('/api/', '/openai', '/ollama', '/ws/')))) or (method == 'POST' and path in PUBLIC_POST)):
            return await self.app(scope, receive, send)
        if self.client is None:
            return await deny()
        auth_header = headers.get('authorization', '')
        # Shared guest link: no native session; only guest API under the classroom authority.
        if auth_header.lower().startswith('bearer guest:'):
            if websocket or path.startswith('/ws/'):
                return await deny(403, '访客链接不支持 WebSocket', 'WEBSOCKET_DENIED')
            if any(path.startswith(prefix) for prefix in MODEL_EGRESS_PREFIXES):
                return await deny(403, '模型请求必须经过课堂模型出口', 'CLASSROOM_PIPE_REQUIRED')
            if not path.startswith('/api/classroom/v1/guest/'):
                return await deny(403, '访客链接仅可用于临时对话', 'GUEST_PATH_DENIED')
            lower = auth_header.lower()
            idx = lower.find('guest:')
            guest_token = auth_header[idx + 6:].strip() if idx >= 0 else ''
            if not guest_token:
                return await deny(401, '访客链接令牌无效', 'GUEST_LINK_INVALID')
            try:
                check = await self.client.request(
                    'POST', '/internal/v1/guest/validate',
                    principal={'role': 'bridge'}, body={'token': guest_token})
                if check.status_code >= 400:
                    return await deny(401, '访客链接已关闭或无效', 'GUEST_LINK_INVALID')
            except Exception:
                return await deny(401, '访客链接已关闭或无效', 'GUEST_LINK_INVALID')
            scope.setdefault('state', {})['classroom_identity'] = {
                'role': 'guest', 'user_id': 'guest', 'guest_token': guest_token}
            return await self.app(scope, receive, send)
        cookie_auth = False
        if auth_header.lower().startswith('bearer '):
            token = auth_header[7:]
        else:
            cookie_auth = True
            cookies = SimpleCookie()
            try:
                cookies.load(headers.get('cookie', ''))
                token = cookies['token'].value if 'token' in cookies else ''
            except Exception:
                token = ''
        if not token or token.startswith('sk-'):
            return await deny(401, '请重新登录', 'SESSION_REQUIRED')
        if cookie_auth and (websocket or method not in {'GET', 'HEAD', 'OPTIONS'}):
            host = headers.get('host', '').lower()
            if not origin or urlsplit(origin).netloc.lower() != host:
                return await deny(403, 'Cookie 会话写请求必须携带匹配的 Origin', 'ORIGIN_REQUIRED')
        try:
            if self.verifier:
                user = await self.verifier(token)
            else:
                from open_webui.utils.auth import get_verified_user_by_token
                user = await get_verified_user_by_token(token, getattr(scope['app'].state, 'redis', None))
            if user is None:
                return await deny(401, '会话已失效', 'SESSION_REVOKED')
            identity = self.client.principal(user, token)
            state = await self.client.control('identity/validate', {**identity, 'generation': path in CHAT_PATHS})
        except Exception:
            return await deny(401, '课堂会话验证失败，请重新登录', 'SESSION_REVOKED')
        scope.setdefault('state', {})['classroom_identity'] = identity
        # Teacher chat still needs the Pipe operation and attachment context.
        # Non-chat administration may bypass student allowlists, but never the
        # native provider exits — those stay on the classroom pipe.
        if any(path.startswith(prefix) for prefix in MODEL_EGRESS_PREFIXES):
            return await deny(403, '模型请求必须经过课堂模型出口', 'CLASSROOM_PIPE_REQUIRED')
        if user.role == 'admin' and not (path in CHAT_PATHS and method == 'POST') and not (websocket or path.startswith('/ws/')):
            return await self.app(scope, receive, send)
        if self.require_bootstrap and not getattr(scope['app'].state, 'classroom_bootstrap_ready', False):
            return await deny(503, '课堂保护链正在准备', 'CLASSROOM_NOT_READY')
        if method in {'POST', 'PUT', 'PATCH'}:
            try:
                if int(headers.get('content-length', '0')) > 16 * 1024 * 1024:
                    return await deny(413, '请求过大', 'REQUEST_TOO_LARGE')
            except ValueError:
                return await deny(400, '请求长度无效', 'INVALID_CONTENT_LENGTH')
            original_receive = receive
            received_bytes = 0
            async def bounded_receive():
                nonlocal received_bytes
                event = await original_receive()
                received_bytes += len(event.get('body', b''))
                if received_bytes > 16 * 1024 * 1024:
                    from fastapi import HTTPException
                    raise HTTPException(413, 'request is too large')
                return event
            receive = bounded_receive
        restricted_paths = {'/api/v1/auths/', '/api/v1/auths/signout', '/api/v1/auths/update/password',
                            '/api/classroom/v1/me', '/api/classroom/v1/account/change-initial-password'}
        if state.get('must_change_password') and path not in restricted_paths:
            return await deny(428, '首次登录必须修改密码', 'PASSWORD_CHANGE_REQUIRED')
        if websocket or path.startswith('/ws/'):
            # Students must use the HTTP classroom pipe; WebSocket is not an
            # approved model or capability egress. Teachers keep UI sockets
            # with per-frame session revalidation.
            if user.role != 'admin':
                return await deny(403, '学生不能通过 WebSocket 访问课堂能力', 'WEBSOCKET_DENIED')
            async def guarded_receive():
                event = await receive()
                await self.client.control('identity/validate', identity)
                return event
            return await self.app(scope, guarded_receive, send)
        if path in CHAT_PATHS and method == 'POST':
            raw = bytearray()
            while True:
                event = await receive()
                if event['type'] == 'http.disconnect':
                    return
                raw.extend(event.get('body', b''))
                if len(raw) > 1024 * 1024:
                    return await deny(413, '聊天请求过大', 'REQUEST_TOO_LARGE')
                if not event.get('more_body'):
                    break
            try:
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError()
                # Preserve native history associations; discard all capability
                # knobs before native preprocessing can perform an AI task.
                clean = {k: body[k] for k in ('messages', 'id', 'chat_id', 'parent_id', 'user_message', 'session_id') if k in body}
                entries = body.get('message_ids')
                if isinstance(entries, dict):
                    entries = [{'message_id': v} for v in entries.values()]
                if entries is not None:
                    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
                        raise ValueError()
                    clean['id'] = entries[0].get('message_id')
                if not isinstance(clean.get('id'), str) or not 1 <= len(clean['id']) <= 200:
                    raise ValueError()
                scope['state']['classroom_operation_id'] = clean['id']
                scope['state']['classroom_parent_message_id'] = clean.get('parent_id')
                files = body.get('files') or []
                if not isinstance(files, list) or len(files) > 5 or any(not isinstance(f, dict) or not isinstance(f.get('id'), str) for f in files):
                    raise ValueError()
                scope['state']['classroom_native_file_ids'] = [f['id'] for f in files]
                clean.update(model='classroom_pipe', stream=True, background_tasks={}, features={}, params={}, files=[], tool_ids=[], filter_ids=[])
                if isinstance(clean.get('user_message'), dict):
                    clean['user_message'] = {k: v for k, v in clean['user_message'].items() if k in {'id', 'content', 'role', 'parentId', 'childrenIds', 'timestamp'}}
                encoded = json.dumps(clean, ensure_ascii=False).encode()
            except (ValueError, TypeError):
                return await deny(400, '需要一个有效的原生消息 ID', 'INVALID_CHAT_OPERATION')
            scope['headers'] = [(k, v) for k, v in scope.get('headers', []) if k.lower() != b'content-length'] + [(b'content-length', str(len(encoded)).encode())]
            supplied = False
            async def replay():
                nonlocal supplied
                if not supplied:
                    supplied = True
                    return {'type': 'http.request', 'body': encoded, 'more_body': False}
                return await receive()
            return await self.app(scope, replay, send)
        allowed = (path.startswith('/api/classroom/v1/') or path in restricted_paths
                   or (method == 'POST' and bool(re.fullmatch(r'/api/tasks/chat/[a-zA-Z0-9-]+/stop', path)))
                   or (method == 'GET' and bool(re.fullmatch(r'/api/tasks/chat/[a-zA-Z0-9-]+', path)))
                   or (method == 'POST' and path == '/api/v1/files/')
                   or (method == 'GET' and bool(re.fullmatch(r'/api/v1/files/[a-zA-Z0-9-]+(?:/content|/process/status)?', path)))
                   or (method in {'GET', 'HEAD'} and path in {'/api/models', '/api/v1/users/user/settings'})
                   or (bool(SAFE_CHAT.fullmatch(path)) and method in {'GET', 'POST', 'DELETE'}))
        if not allowed:
            return await deny()
        return await self.app(scope, receive, send)
