import hashlib
import io
import json
import sqlite3
import zipfile

import pytest

from classroom.app.classroom_service.backup import restore
from classroom.app.classroom_service.errors import ValidationError, ForbiddenError, ConflictError
from classroom.app.classroom_service.migrate import migrate
from classroom.app.classroom_service.worker import HttpUpstream, ClassroomWorker


def test_bridge_reuses_http_client_and_closes_on_shutdown(monkeypatch):
    import asyncio, httpx
    from classroom.app.openwebui_bridge.client import BridgeClient
    original = httpx.AsyncClient
    clients = []
    def construct(**kwargs):
        value = original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'ready':True})), **kwargs)
        clients.append(value)
        return value
    monkeypatch.setattr(httpx, 'AsyncClient', construct)
    async def run():
        bridge = BridgeClient('http://127.0.0.1:8790', b'x'*32)
        for _ in range(3):
            response = await bridge.request('GET','/health',principal={'role':'bridge'})
            assert response.status_code == 200
        assert len(clients) == 1
        await bridge.aclose()
        assert clients[0].is_closed
    asyncio.run(run())


def test_temporary_gc_preserves_submitted_attachments(service):
    from datetime import timedelta
    unused = service.attachments.add('student-1', 'unused.py', b'print(1)')
    kept = service.attachments.add('student-1', 'kept.py', b'print(2)')
    row = service.submit('student-1', 'gc', {'model':'classroom-default','messages':[{'role':'user','content':'review'}], 'attachments':[{'id':kept['id'],'sha256':kept['sha256']}]}, attachment_ids=[kept['id']])
    service.clock.set(service.now() + timedelta(hours=25))
    assert service.attachments.cleanup_temporary() == 1
    assert service.attachments.get(kept['id'])['content'] == b'print(2)'
    assert service.db.query_one('SELECT id FROM attachments WHERE id=?', (unused['id'],)) is None


def test_provider_restart_configuration_invalidates_old_approval(service):
    service.configure_provider('provider-a')
    request = approved(service, 'provider-change')
    version = service.provider_profile_version
    service.configure_provider('provider-a')
    assert service.provider_profile_version == version
    assert service.get_request(request['id'])['status'] == 'approved_queued'
    service.configure_provider('provider-b')
    assert service.provider_profile_version > version
    assert service.get_request(request['id'])['status'] == 'pending'


def test_pipe_drains_all_terminal_event_pages():
    import asyncio
    from types import SimpleNamespace
    from classroom.app.openwebui_classroom_pipe import Pipe
    class Response:
        status_code = 200
        def __init__(self, value): self.value = value
        def json(self): return self.value
    class Client:
        async def control(self, *args): return {'attachments': []}
        async def request(self, method, path, **kwargs):
            if path.endswith('/me'): return Response({'allowed_models': ['test']})
            if method == 'POST': return Response({'id': 'r1'})
            if '/events?' in path:
                after = int(path.split('=')[-1])
                return Response({'events': [{'seq': n, 'event_type': 'delta', 'payload': {'text': 'x'}} for n in range(after+1, min(after+1000, 1501)+1)]})
            return Response({'status': 'completed', 'output_seq': 1501})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(classroom_client=Client())), state=SimpleNamespace(classroom_identity={'user_id': 'student'}, classroom_operation_id='op'))
    async def run():
        response = await Pipe().pipe({'messages': [{'role':'user','content':'question'}]}, {'id':'student'}, {}, request)
        return ''.join([part async for part in response.body_iterator])
    result = asyncio.run(run())
    assert result.count('"content": "x"') == 1501
    assert result.endswith('data: [DONE]\n\n')


def test_http_cancel_keeps_reservation_until_transport_closes(service):
    import asyncio
    import threading
    import time
    import httpx
    closing = threading.Event()
    permit_close = threading.Event()
    closed = threading.Event()
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"visible"}}]}\n\n'
            await asyncio.Event().wait()
        async def aclose(self):
            closing.set()
            await asyncio.to_thread(permit_close.wait)
            closed.set()
    async def respond(request):
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, stream=Stream())
    request = approved(service, 'cancel-transport')
    upstream = HttpUpstream('https://provider.test/v1', lambda: 'test', transport=httpx.MockTransport(respond))
    worker = ClassroomWorker(service, upstream)
    thread = threading.Thread(target=worker.run_one)
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while not service.get_request(request['id']).get('output_text') and time.monotonic() < deadline:
            time.sleep(0.01)
        assert service.get_request(request['id'])['output_text'] == 'visible'
        service.cancel(request['id'], 'student-1')
        assert closing.wait(2)
        assert not closed.is_set()
        assert service.quota.read('student-1')['reserved'] == 1
        assert service.get_request(request['id'])['status'] == 'generating'
    finally:
        permit_close.set()
        thread.join(3)
    assert not thread.is_alive() and closed.is_set()
    assert service.quota.read('student-1')['reserved'] == 0
    assert service.get_request(request['id'])['charge_units'] == 0


def payload():
    return {"model": "classroom-default", "messages": [{"role": "user", "content": "hello"}]}


def approved(service, operation="test"):
    request = service.submit("student-1", operation, payload())
    return service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])


def test_bad_restore_never_replaces_existing_data(tmp_path):
    target = tmp_path / "original"
    target.mkdir()
    original = target / "classroom.db"
    original.write_bytes(b"only original copy")
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("classroom.db", b"damaged")
        z.writestr("manifest.json", json.dumps({"format_version": 1, "files": {"classroom.db": "0" * 64}}))
    with pytest.raises(ValueError):
        restore(archive, target)
    assert original.read_bytes() == b"only original copy"
    empty_target = tmp_path / "empty"
    with pytest.raises(ValueError):
        restore(archive, empty_target)
    assert not empty_target.exists()


def test_verify_only_never_creates_database(tmp_path):
    path = tmp_path / "does-not-exist.db"
    with pytest.raises(sqlite3.OperationalError):
        migrate(str(path), verify_only=True)
    assert not path.exists()


def test_corrupt_schema_record_is_rejected_before_ddl(tmp_path):
    path = tmp_path / "schema.db"
    migrate(str(path))
    with sqlite3.connect(path) as db:
        db.execute("DROP INDEX uq_request_operation")
        db.execute("UPDATE schema_migrations SET checksum='wrong' WHERE version=1")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError):
        migrate(str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_real_image_decode_rejects_header_and_accepts_lossless_webp(service):
    from PIL import Image
    fake_png = bytes.fromhex("89504e470d0a1a0a0000000d494844520000000100000001")
    with pytest.raises(ValidationError):
        service.attachments.add("student-1", "fake.png", fake_png)
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, "WEBP", lossless=True)
    result = service.attachments.add("student-1", "valid.webp", buffer.getvalue())
    assert (result["width"], result["height"]) == (2, 2)


@pytest.mark.parametrize("body", [b"", b'data: {"error":{"message":"failed"}}\n\n',
    b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'])
def test_bad_provider_stream_never_charges(service, body):
    import httpx
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=body))
    upstream = HttpUpstream("https://provider.invalid/v1", lambda: "test-only", transport=transport)
    request = approved(service)
    result = ClassroomWorker(service, upstream).run_one()
    assert result["status"] == "interrupted"
    assert result["charge_units"] == 0
    assert service.quota.read("student-1")["reserved"] == 0


def test_written_but_not_delivered_output_does_not_charge_stop(service):
    request = approved(service)
    claim = service.claim_next()
    service.mark_dispatched(request["id"], claim["claim_token"])
    service.append_event(request["id"], "delta", {"text": "not delivered"})
    stopped = service.cancel(request["id"], "student-1")
    assert stopped["status"] == "generating"
    assert service.quota.read("student-1")["reserved"] == 1
    result = service.finalize(request["id"], outcome="interrupted", reason="executor closed")
    assert result["status"] == "cancelled_before_output" and result["charge_units"] == 0


def test_pause_and_model_removal_prevent_dispatch(service):
    request = approved(service)
    service.set_student_state("teacher-1", "student-1", ai_enabled=False)
    assert service.claim_next() is None
    service.set_student_state("teacher-1", "student-1", ai_enabled=True)
    service.set_allowed_models("teacher-1", {"new-model"})
    request = service.get_request(request["id"])
    with pytest.raises(ForbiddenError):
        service.decide(request["id"], "teacher-1", "approve", expected_version=request["version"])


def test_operation_digest_includes_chat_branch(service):
    service.submit("student-1", "same-op", payload(), chat_id="chat-a")
    with pytest.raises(ConflictError):
        service.submit("student-1", "same-op", payload(), chat_id="chat-b")
