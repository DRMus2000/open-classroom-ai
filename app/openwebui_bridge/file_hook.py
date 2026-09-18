"""Copy student uploads into immutable storage before native file processing."""
import base64


def install_file_hook(app, client):
    from fastapi import HTTPException
    for route in app.router.routes:
        if getattr(route, 'path', '') == '/api/v1/files/' and 'POST' in getattr(route, 'methods', set()):
            original = route.dependant.call
            async def upload(**kwargs):
                request = kwargs['request']
                identity = getattr(request.state, 'classroom_identity', None)
                if identity is None:
                    raise HTTPException(401, '课堂会话验证失败')
                file = kwargs['file']
                content = await file.read(10 * 1024 * 1024 + 1)
                if len(content) > 10 * 1024 * 1024:
                    raise HTTPException(413, '附件过大')
                await file.seek(0)
                response = await client.request('POST', '/api/classroom/v1/attachments', principal=identity,
                    body={'filename': file.filename, 'content_base64': base64.b64encode(content).decode('ascii')})
                if response.status_code >= 400:
                    raise HTTPException(response.status_code, response.json().get('error', {}).get('message', '附件未通过课堂校验'))
                attachment = response.json()
                kwargs.update(process=False, process_in_background=False, metadata=None)
                result = await original(**kwargs)
                fid = result.get('id') if isinstance(result, dict) else result.id
                await client.control('identity/file-linked', {'user_id': identity['user_id'], 'native_file_id': fid, 'attachment_id': attachment['id']})
                from open_webui.models.files import Files
                await Files.update_file_data_by_id(fid, {'status': 'completed', 'content': ''}, db=kwargs['db'])
                if isinstance(result, dict):
                    result['data'] = {**(result.get('data') or {}), 'status': 'completed'}
                else:
                    result = result.model_copy(update={'data': {**(result.data or {}), 'status': 'completed'}})
                return result
            route.dependant.call = upload
            return
    raise RuntimeError('native upload endpoint contract changed')
