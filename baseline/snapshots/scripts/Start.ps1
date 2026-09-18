param([string]$DataRoot = '')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root 'runtime\python\python.exe'
$App = Join-Path $Root 'app'
$Data = if ($DataRoot) { [IO.Path]::GetFullPath($DataRoot) } else { Join-Path $Root 'data' }
$Logs = if ($DataRoot) { Join-Path $Data 'logs' } else { Join-Path $Root 'logs' }
New-Item -ItemType Directory -Force -Path $Data, $Logs, (Join-Path $Data 'openwebui'), (Join-Path $Data 'review') | Out-Null
function Get-Health($Url) { try { return (Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2).StatusCode } catch { return 0 } }
$existingWeb = Get-Health 'http://127.0.0.1:3000/health'
$existingReview = Get-Health 'http://127.0.0.1:8790/health'
if ($existingWeb -eq 200 -and $existingReview -eq 200) {
  Write-Host 'Services are already running.'
  Write-Host 'Open WebUI: http://127.0.0.1:3000'
  Write-Host 'Teacher review: http://127.0.0.1:8790/'
  Start-Process 'http://127.0.0.1:8790/'
  exit 0
}
if ($existingWeb -ne 0 -or $existingReview -ne 0) { throw 'Port 3000 or 8790 is already used by another service.' }
$env:DATA_DIR = Join-Path $Data 'openwebui'
$env:REVIEW_GATE_DB = Join-Path $Data 'review\review.db'
$env:REVIEW_GATE_PID = Join-Path $Data 'review\review-service.pid'
$keyFile = Join-Path $Root '.webui_secret_key'
if (-not (Test-Path -LiteralPath $keyFile)) {
  $bytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  [Convert]::ToBase64String($bytes) | Set-Content -LiteralPath $keyFile -Encoding ascii
}
$env:WEBUI_SECRET_KEY = (Get-Content -LiteralPath $keyFile -Raw).Trim()
$env:HOST = '0.0.0.0'
$env:PORT = '3000'
$env:WEBUI_URL = 'http://127.0.0.1:3000'
$env:WEBUI_AUTH = 'true'
$env:DEFAULT_USER_ROLE = 'user'
$env:ENABLE_PLUGINS = 'true'
$env:OFFLINE_MODE = 'true'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:ENABLE_OLLAMA_API = 'false'
$env:BYPASS_MODEL_ACCESS_CONTROL = 'true'
$env:ENABLE_DB_MIGRATIONS = 'false'
$env:USER_AGENT = 'OpenWebUI-Classroom/0.11.2'
$reviewLog = Join-Path $Logs 'review-gate.log'
$reviewErr = Join-Path $Logs 'review-gate-error.log'
$webLog = Join-Path $Logs 'openwebui.log'
$webErr = Join-Path $Logs 'openwebui-error.log'
$reviewScript = Join-Path $App 'review_service.py'
$webScript = Join-Path $App 'run_openwebui.py'
$reviewArgs = ('"{0}" --host 127.0.0.1 --port 8790' -f $reviewScript)
$webArgs = ('"{0}"' -f $webScript)
$review = Start-Process -FilePath $Python -ArgumentList $reviewArgs -WorkingDirectory $Root -RedirectStandardOutput $reviewLog -RedirectStandardError $reviewErr -PassThru -WindowStyle Hidden
$web = Start-Process -FilePath $Python -ArgumentList $webArgs -WorkingDirectory $Root -RedirectStandardOutput $webLog -RedirectStandardError $webErr -PassThru -WindowStyle Hidden
$review.Id | Set-Content -LiteralPath (Join-Path $Data 'review\review.pid') -Encoding ascii
$web.Id | Set-Content -LiteralPath (Join-Path $Data 'openwebui\openwebui.pid') -Encoding ascii
$boot = & $Python (Join-Path $App 'bootstrap_openwebui.py') 2>&1
$boot | Tee-Object -FilePath (Join-Path $Logs 'bootstrap.log')
if ($LASTEXITCODE -ne 0) { Write-Host 'BOOTSTRAP_FAILED'; Write-Host 'See logs\bootstrap.log and logs\openwebui.log'; exit 1 }
Write-Host 'Open WebUI: http://127.0.0.1:3000'
Write-Host 'Teacher review: http://127.0.0.1:8790/'
Write-Host 'Students: http://<teacher-ip>:3000'
Start-Process 'http://127.0.0.1:8790/'
