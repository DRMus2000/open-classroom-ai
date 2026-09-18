"""Inject the classroom status/delivery UI into the native SPA shell."""
class ClassroomShell:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        start = None
        chunks = []
        async def intercept(event):
            nonlocal start
            if event['type'] == 'http.response.start':
                headers = dict(event.get('headers', []))
                if b'text/html' in headers.get(b'content-type', b''):
                    start = event
                    return
            if start is not None and event['type'] == 'http.response.body':
                chunks.append(event.get('body', b''))
                if not event.get('more_body'):
                    raw = b''.join(chunks)
                    raw = raw.replace(b'</head>', b'<script defer src="/classroom/native.js"></script></head>', 1)
                    start['headers'] = [(k, v) for k, v in start['headers'] if k.lower() not in {b'content-length', b'etag'}] + [(b'content-length', str(len(raw)).encode())]
                    await send(start)
                    await send({'type': 'http.response.body', 'body': raw})
                return
            await send(event)
        await self.app(scope, receive, intercept)
