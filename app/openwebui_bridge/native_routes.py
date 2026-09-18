"""Same-origin transport to the sole classroom authority process."""
from pathlib import Path


def raw_token(request):
    auth = request.headers.get("authorization", "")
    return auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get("token", "")


def install_native_routes(app, client, *, web_root=None):
    from contextlib import asynccontextmanager
    original_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        try:
            async with original_lifespan(application) as state:
                yield state
        finally:
            await client.aclose()
    app.router.lifespan_context = lifespan
    from fastapi import Request, HTTPException
    from fastapi.responses import Response
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from open_webui.utils.auth import get_verified_user_by_token
    before = len(app.router.routes)
    app.state.classroom_client = client
    app.state.classroom_bootstrap_ready = False

    @app.post('/api/classroom/bootstrap-complete')
    async def bootstrap_complete(request: Request):
        user = await get_verified_user_by_token(raw_token(request), getattr(app.state, 'redis', None))
        if user is None or user.role != 'admin':
            raise HTTPException(403, 'teacher permission required')
        await client.control('identity/validate', client.principal(user, raw_token(request)))
        from open_webui.models.config import Config
        from open_webui.models.functions import Functions
        function = await Functions.get_function_by_id('classroom_pipe')
        expected = (Path(__file__).resolve().parents[1] / 'openwebui_classroom_pipe.py').read_text(encoding='utf-8-sig')
        if not function or not function.is_active or function.content.lstrip('\ufeff') != expected:
            raise HTTPException(503, 'managed Pipe content verification failed')
        from .policy import POLICY as policy
        await Config.upsert(policy)
        for key, value in policy.items():
            if await Config.get(key) != value:
                raise HTTPException(503, 'native safety configuration readback failed')
        # Active Pipe functions are not automatically readable by students in
        # 0.11.2: a workspace Model row and explicit read grant are required.
        from open_webui.models.models import Models, ModelForm
        form = ModelForm(id='classroom_pipe', name='课堂 AI', base_model_id=None,
                         meta={'capabilities': {'vision': True}}, params={},
                         access_grants=[{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}])
        existing = await Models.get_model_by_id('classroom_pipe')
        model = await Models.update_model_by_id('classroom_pipe', form) if existing else await Models.insert_new_model(form, user.id)
        if not model:
            raise HTTPException(503, 'managed workspace model could not be configured')
        from open_webui.utils.models import get_all_models
        await get_all_models(request, refresh=True, user=user)
        if 'classroom_pipe' not in app.state.MODELS:
            raise HTTPException(503, 'managed model did not enter native model registry')
        app.state.classroom_bootstrap_ready = True
        return {'ready': True}

    @app.api_route("/api/classroom/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def proxy(request: Request, path: str):
        auth = request.headers.get("authorization", "")
        if path.startswith("guest/"):
            lower = auth.lower()
            if not lower.startswith("bearer guest:"):
                raise HTTPException(401, "访客链接令牌无效")
            guest_token = auth[lower.find("guest:") + 6:].strip()
            if not guest_token:
                raise HTTPException(401, "访客链接令牌无效")
            identity = {"role": "guest", "user_id": "guest", "guest_token": guest_token}
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16 * 1024 * 1024:
                    raise HTTPException(413, "请求过大")
            if body and request.headers.get("content-type", "").split(";")[0] != "application/json":
                raise HTTPException(415, "application/json is required")
            target = request.url.path + ("?" + request.url.query if request.url.query else "")
            if path.endswith("chat/completions") and request.method == "POST":
                import json as _json
                payload = _json.loads(bytes(body)) if body else {}
                return await client.download(target, identity, method="POST", body=payload)
            response = await client.request(request.method, target, principal=identity, raw=bytes(body))
            headers = {k: v for k, v in response.headers.items() if k.lower() in {
                "content-type", "content-disposition", "x-content-type-options", "content-security-policy"}}
            headers["Cache-Control"] = "no-store"
            return Response(response.content, status_code=response.status_code, headers=headers)
        token = raw_token(request)
        if not token or token.startswith("sk-"):
            raise HTTPException(401, "请重新登录")
        user = await get_verified_user_by_token(token, getattr(app.state, "redis", None))
        if user is None:
            raise HTTPException(401, "会话已失效")
        identity = client.principal(user, token)
        if path == "account/change-initial-password" or path.startswith(("admin/imports/", "admin/accounts/import/")) or path.endswith("/reset-password"):
            identity["native_token"] = token
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16 * 1024 * 1024:
                raise HTTPException(413, "请求过大")
        if body and request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "application/json is required")
        target = request.url.path + ("?" + request.url.query if request.url.query else "")
        if request.method == 'GET' and path.startswith('admin/exports/'):
            return await client.download(target, identity)
        response = await client.request(request.method, target, principal=identity, raw=bytes(body), extra_headers=request.headers)
        headers = {k: v for k, v in response.headers.items() if k.lower() in {
            "content-type", "content-disposition", "x-content-type-options", "content-security-policy"}}
        headers["Cache-Control"] = "no-store"
        return Response(response.content, status_code=response.status_code, headers=headers)

    if web_root:
        @app.get('/classroom/native.js')
        async def native_script():
            return FileResponse(Path(web_root) / 'native.js', media_type='application/javascript', headers={'Cache-Control': 'no-store'})
        for name in ("teacher", "student", "guest"):
            root = Path(web_root) / name
            if name != "guest" and not root.is_dir():
                raise RuntimeError(f"classroom {name} page is missing")
            if root.is_dir():
                app.mount("/classroom/" + name, StaticFiles(directory=root, html=True), name="classroom-" + name)
    additions = app.router.routes[before:]
    del app.router.routes[before:]
    index = next((i for i, r in enumerate(app.router.routes) if getattr(r, "path", None) == ""), len(app.router.routes))
    app.router.routes[index:index] = additions
    if web_root:
        from .shell import ClassroomShell
        for route in app.router.routes:
            if getattr(route, 'path', None) == '':
                route.app = ClassroomShell(route.app)
