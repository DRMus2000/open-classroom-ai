import subprocess

from classroom.app import prepare_installation as installation


def test_native_import_failure_is_logged_and_secrets_are_redacted(tmp_path, monkeypatch, capsys):
    secret = 'diagnostic-private-test-key'
    monkeypatch.setenv('CLASSROOM_PROVIDER_API_KEY', secret)
    def failed(command, **kwargs):
        assert kwargs['env']['PYTHONIOENCODING'] == 'utf-8'
        return subprocess.CompletedProcess(command, 1, b'',
            ('ImportError: DLL load failed while importing example\n' + secret).encode())
    monkeypatch.setattr(installation.subprocess, 'run', failed)
    destination = tmp_path / 'data'
    assert installation.main(['--new', '--destination', str(destination), '--friendly']) == 1
    assert not destination.exists()
    logs = list((tmp_path / 'initialization-logs').glob('*.log'))
    assert len(logs) == 1
    details = logs[0].read_text(encoding='utf-8')
    assert 'DLL load failed' in details and 'exit code 1' in details
    assert secret not in details and '[REDACTED]' in details
    assert '初始化未完成' in capsys.readouterr().out


def test_existing_data_is_not_overwritten(tmp_path, capsys):
    destination = tmp_path / 'data'
    destination.mkdir()
    marker = destination / 'keep.txt'
    marker.write_bytes(b'keep existing data')
    assert installation.main(['--new', '--destination', str(destination), '--friendly']) == 1
    assert marker.read_bytes() == b'keep existing data'
    assert '目标数据目录已存在' in capsys.readouterr().out


def test_friendly_success_is_explicit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(installation, 'prepare', lambda *args: {'format_version': 1})
    assert installation.main(['--new', '--destination', str(tmp_path/'data'), '--friendly']) == 0
    message = capsys.readouterr().out
    assert '初始化成功' in message and '启动课堂.cmd' in message
    assert 'format_version' not in message
