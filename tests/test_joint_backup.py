import sqlite3
import zipfile
import json
import pytest

from classroom.app.classroom_service.joint_backup import joint_backup
from classroom.app.classroom_service.backup import restore
from classroom.app.classroom_service.database import ClassroomDB
from classroom.app.classroom_service.runtime import InstanceLock


def test_joint_backup_restores_native_accounts_and_files(tmp_path):
    classroom = tmp_path / 'classroom'
    classroom.mkdir()
    db = ClassroomDB(classroom / 'classroom.db')
    db.close()
    native = tmp_path / 'native'
    native.mkdir()
    with sqlite3.connect(native / 'webui.db') as db:
        db.execute('CREATE TABLE user(id TEXT PRIMARY KEY,name TEXT)')
        db.execute("INSERT INTO user VALUES('unchanged-id','Student')")
        db.execute('CREATE TABLE file(id TEXT PRIMARY KEY,path TEXT)')
        db.execute('INSERT INTO file VALUES(?,?)', ('original', str(native / 'uploads/original.txt')))
    (native / 'uploads').mkdir()
    (native / 'uploads' / 'original.txt').write_text('original file')
    (native / '.webui_secret_key').write_text('fixture secret')
    output = tmp_path / 'backup.zip'
    joint_backup(classroom / 'classroom.db', classroom, native, output)
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['contains_secrets'] is True
        assert 'openwebui/webui.db' in manifest['files']
    recovered = tmp_path / 'restored'
    restore(output, recovered)
    with sqlite3.connect(recovered / 'openwebui' / 'webui.db') as db:
        assert db.execute('SELECT id FROM user').fetchone()[0] == 'unchanged-id'
        assert db.execute('SELECT path FROM file').fetchone()[0] == str(recovered / 'openwebui/uploads/original.txt')
    assert (recovered / 'openwebui/uploads/original.txt').read_text() == 'original file'
    assert (recovered / 'openwebui/.webui_secret_key').read_text() == 'fixture secret'
    lock = InstanceLock(native / 'webui.lock').acquire()
    before = output.read_bytes()
    try:
        with pytest.raises(RuntimeError):
            joint_backup(classroom / 'classroom.db', classroom, native, output)
        assert output.read_bytes() == before
    finally:
        lock.close()
