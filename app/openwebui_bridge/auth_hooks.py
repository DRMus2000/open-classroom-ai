"""Hooks applied to native endpoints after dependency resolution."""
from datetime import datetime, timezone, timedelta
import hashlib


def install_auth_hooks(app, client):
    from fastapi import HTTPException
    from open_webui.models.users import Users
    from open_webui.models.auths import Auths
    from open_webui.utils.auth import verify_password

    def hook(original, kind):
        async def wrapped(**kwargs):
            form = kwargs.get("form_data")
            db = kwargs.get("db")
            if kind == "signin":
                user = await Users.get_user_by_email(form.email.lower(), db=db)
                prepared = await client.control("identity/prepare", {"user_id": user.id, "role": user.role}) if user else None
                result = await original(**kwargs)
                if not isinstance(result, dict) or not result.get("token"):
                    raise HTTPException(503, "原生登录契约发生变化")
                if prepared is None:
                    if result.get("role") != "admin":
                        raise HTTPException(403, "账号未加入课堂")
                    prepared = await client.control("identity/prepare", {"user_id": result["id"], "role": "admin"})
                expiry = result.get("expires_at")
                expires_at = datetime.fromtimestamp(expiry, timezone.utc) if expiry else datetime.now(timezone.utc) + timedelta(hours=12)
                await client.control("identity/issued", {"user_id": result["id"], "token_fingerprint": hashlib.sha256(result["token"].encode()).hexdigest(),
                                                        "epoch": prepared["epoch"], "expires_at": expires_at.isoformat()})
                return result
            reset = kind == "reset"
            password = form.password if reset else form.new_password
            if reset and not password:
                return await original(**kwargs)
            if not isinstance(password, str) or len(password) < 8 or (not reset and password == form.password):
                raise HTTPException(400, "新密码至少八位，且必须不同于当前密码")
            actor = kwargs["session_user"]
            uid = kwargs["user_id"] if reset else actor.id
            if not reset:
                verified = await Auths.authenticate_user(actor.email, lambda pw: verify_password(form.password, pw), db=db)
                if not verified:
                    raise HTTPException(400, "当前密码不正确")
            epoch = (await client.control("identity/begin", {"user_id": uid, "actor_id": actor.id}))["epoch"]
            success = False
            try:
                result = await original(**kwargs)
                if reset:
                    user = await Users.get_user_by_id(uid, db=db)
                    verified = await Auths.authenticate_user(user.email, lambda pw: verify_password(password, pw), db=db) if user else None
                    success = bool(verified)
                else:
                    success = result is True
                if not success:
                    raise HTTPException(502, "原生密码更新未成功")
                return result
            finally:
                await client.control("identity/finish", {"user_id": uid, "actor_id": actor.id, "epoch": epoch,
                                                        "success": success, "must_change": reset})
        return wrapped

    expected = {"/api/v1/auths/signin": "signin", "/api/v1/auths/update/password": "change",
                "/api/v1/users/{user_id}/update": "reset"}
    installed = set()
    for route in app.router.routes:
        path = getattr(route, "path", "")
        if path in expected and "POST" in getattr(route, "methods", set()):
            route.dependant.call = hook(route.dependant.call, expected[path])
            installed.add(path)
    if installed != set(expected):
        raise RuntimeError("native authentication endpoint contract changed")
    for route in app.router.routes:
        if getattr(route, 'path', '') == '/api/tasks/chat/{chat_id:path}/stop':
            original_stop = route.dependant.call
            async def stop(**kwargs):
                user = kwargs['user']
                if user.role != 'admin':
                    await client.control('identity/cancel-chat', {'user_id': user.id, 'chat_id': kwargs['chat_id']})
                return await original_stop(**kwargs)
            route.dependant.call = stop
            break
    else:
        raise RuntimeError('native stop endpoint contract changed')
