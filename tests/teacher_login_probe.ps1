$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\scripts\TeacherLogin.ps1')
$python = (Resolve-Path (Join-Path $PSScriptRoot '..\release\openwebui-classroom-windows-x64\runtime\python\python.exe')).Path
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('classroom-login-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
$setup = Join-Path $scratch 'setup.py'
@'
import sqlite3, sys, pathlib
c = sqlite3.connect(str(pathlib.Path(sys.argv[1]) / 'webui.db'))
c.execute('CREATE TABLE user(email TEXT,role TEXT)')
c.execute('INSERT INTO user VALUES(?,?)', ('synthetic@example.invalid', 'admin'))
c.commit()
c.close()
'@ | Set-Content $setup -Encoding UTF8
& $python -B $setup $scratch
if($LASTEXITCODE -ne 0){throw 'Test setup failed'}
function Read-Host { throw 'Unexpected email prompt' }
$env:WEBUI_ADMIN_EMAIL=$null
$env:WEBUI_ADMIN_PASSWORD=$null
Initialize-ClassroomTeacherLogin -DataRoot $scratch -NativeRoot $scratch -Python $python
if($env:WEBUI_ADMIN_EMAIL -ne 'synthetic@example.invalid'){throw 'Existing administrator lookup failed'}
$env:WEBUI_ADMIN_PASSWORD='synthetic-password-test'
Save-ClassroomTeacherLogin -DataRoot $scratch
$path=Join-Path $scratch 'teacher-login.json'
$raw=Get-Content -Raw $path
if($raw.Contains('synthetic-password-test')){throw 'Plaintext password persisted'}
$env:WEBUI_ADMIN_EMAIL=$null
$env:WEBUI_ADMIN_PASSWORD=$null
Initialize-ClassroomTeacherLogin -DataRoot $scratch -NativeRoot $scratch -Python $python
if($env:WEBUI_ADMIN_PASSWORD -cne 'synthetic-password-test'){throw 'Password roundtrip failed'}
$env:WEBUI_ADMIN_EMAIL='other@example.invalid'
$env:WEBUI_ADMIN_PASSWORD=$null
Initialize-ClassroomTeacherLogin -DataRoot $scratch -NativeRoot $scratch -Python $python
if($env:WEBUI_ADMIN_PASSWORD){throw 'Saved password reused for another identity'}
$saved=$raw | ConvertFrom-Json
$saved.encrypted_password='unreadable-copied-blob'
$saved | ConvertTo-Json | Set-Content $path -Encoding UTF8
$env:WEBUI_ADMIN_EMAIL=$null
$env:WEBUI_ADMIN_PASSWORD=$null
Initialize-ClassroomTeacherLogin -DataRoot $scratch -NativeRoot $scratch -Python $python
if($env:WEBUI_ADMIN_PASSWORD){throw 'Invalid encrypted password accepted'}
$env:WEBUI_ADMIN_EMAIL=$null
$env:WEBUI_ADMIN_PASSWORD=$null
Write-Output 'TEACHER_EMAIL_DISCOVERY_DPAPI_RESTART_IDENTITY_RECOVERY_OK'
