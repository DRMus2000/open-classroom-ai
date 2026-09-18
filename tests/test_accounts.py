from classroom.app.classroom_service.accounts import AccountProvisioner, MemoryAccountAdapter
from classroom.app.classroom_service.errors import ValidationError
import pytest


def test_csv_preview_commit_forces_first_change_and_does_not_store_password(service):
    adapter = MemoryAccountAdapter()
    provisioner = AccountProvisioner(service, adapter)
    csv_text = "Name,Email,Password,Role\nAlice,alice@example.test,InitialPass1,user\nBob,bob@example.test,InitialPass2,user\n"
    preview = provisioner.preview("teacher-1", csv_text)
    assert all("password" not in row for row in preview["rows"])
    result = provisioner.commit("teacher-1", preview["batch_id"])
    assert result["status"] == "completed"
    assert len(adapter.users) == 2
    user_id = result["results"][0]["user_id"]
    assert service.db.query_one("SELECT must_change_password FROM security_states WHERE user_id=?", (user_id,))[0] == 1
    changed = provisioner.change_initial_password(user_id, "InitialPass1", "ChangedPass1")
    assert changed["must_change_password"] is False
    reset = provisioner.reset_password("teacher-1", user_id, "Temporary2")
    assert reset["sessions_revoked"]


def test_csv_rejects_admin_role_and_quoted_values_are_parsed(service):
    adapter = MemoryAccountAdapter(); provisioner = AccountProvisioner(service, adapter)
    preview = provisioner.preview("teacher-1", 'Name,Email,Password,Role\n"A, Student",a@example.test,InitialPass1,admin\n')
    assert preview["rows"][0]["error_code"] == "ROLE_NOT_ALLOWED"


def test_import_commit_can_use_request_scoped_native_adapter(service):
    provisioner = AccountProvisioner(service)
    preview = provisioner.preview("teacher-1", "Name,Email,Password,Role\nAlice,alice@example.test,InitialPass1,user\n")
    adapter = MemoryAccountAdapter()
    result = provisioner.commit("teacher-1", preview["batch_id"], adapter=adapter)
    assert result["status"] == "completed"
    assert len(adapter.users) == 1


def test_import_recovers_native_create_with_lost_response(service):
    class LostResponse(MemoryAccountAdapter):
        def create_user(self, **kwargs):
            super().create_user(**kwargs)
            raise TimeoutError('response lost after commit')
    adapter = LostResponse()
    csv_text = 'Name,Email,Password,Role\nAlice,lost@example.test,InitialPass1,user\n'
    first = AccountProvisioner(service, adapter)
    preview = first.preview('teacher-1', csv_text)
    assert first.commit('teacher-1', preview['batch_id'])['status'] == 'partial'
    # Simulate service restart; no password or preview survives in memory.
    retry = AccountProvisioner(service, adapter)
    resumed = retry.preview('teacher-1', csv_text)
    assert resumed['batch_id'] == preview['batch_id']
    assert retry.commit('teacher-1', resumed['batch_id'])['status'] == 'completed'
    assert len(adapter.users) == 1


def test_all_invalid_import_is_not_reported_as_success(service):
    adapter = MemoryAccountAdapter()
    provisioner = AccountProvisioner(service, adapter)
    p = provisioner.preview('teacher-1', 'Name,Email,Password,Role\nAlice,alice@a.b,123456,user\n')
    assert p['rows'][0]['error_code'] == 'WEAK_INITIAL_PASSWORD'
    with pytest.raises(ValidationError) as error:
        provisioner.commit('teacher-1', p['batch_id'])
    assert error.value.code == 'NO_VALID_IMPORT_ROWS'
    assert not adapter.users
    assert service.db.query_one('SELECT status FROM account_imports WHERE id=?', (p['batch_id'],))[0] == 'preview'
    # A package upgraded from the old bug must not replay a false success.
    with service.db.transaction() as db:
        db.execute("UPDATE account_imports SET status='completed',summary_json=? WHERE id=?", ('{"results":[]}',p['batch_id']))
    with pytest.raises(ValidationError):
        provisioner.commit('teacher-1', p['batch_id'])


def test_import_email_preview_matches_native_format_and_valid_rows_still_import(service):
    adapter = MemoryAccountAdapter()
    provisioner = AccountProvisioner(service, adapter)
    p = provisioner.preview('teacher-1', 'Name,Email,Password,Role\nAlice,alice@school,InitialPass1,user\nBob,bob@a.b,InitialPass2,user\n')
    assert p['rows'][0]['error_code'] == 'INVALID_EMAIL'
    assert p['rows'][1]['error_code'] is None
    assert len(provisioner.commit('teacher-1', p['batch_id'])['results']) == 1
    assert len(adapter.users) == 1
