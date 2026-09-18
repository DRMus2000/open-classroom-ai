[CmdletBinding()]
param(
  [string]$DataRoot = '',
  [string]$NativeRoot = '',
  [string]$Python = $env:CLASSROOM_PYTHON,
  [string]$BindHost = '127.0.0.1',
  [int]$WebPort = 3000,
  [int]$ServicePort = 8790,
  [switch]$NoOpenWebUI,
  [switch]$Lan
)
$ErrorActionPreference = 'Stop'
if ($Lan) {
  if ($PSBoundParameters.ContainsKey('BindHost') -and $BindHost -ne '0.0.0.0' -and $BindHost -ne '127.0.0.1') {
    # Keep an explicit custom bind host when the caller already set one with -Lan.
  } elseif (-not $PSBoundParameters.ContainsKey('BindHost') -or $BindHost -eq '127.0.0.1') {
    $BindHost = '0.0.0.0'
  }
  Write-Warning 'LAN mode binds Open WebUI on all interfaces without TLS. Session tokens and chat content travel in cleartext on the local network.'
}
function Format-NativeArguments([object[]]$Values) {
  ($Values | ForEach-Object {
    $value = [string]$_
    if ($value.Contains('"')) { throw 'Unexpected quote in process argument.' }
    '"' + ($value -replace '(\\+)$','$1$1') + '"'
  }) -join ' '
}
$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$appRoot = Join-Path $bundleRoot 'app'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $DataRoot) { $DataRoot = Join-Path $bundleRoot 'data\classroom' }
$DataRoot = [IO.Path]::GetFullPath($DataRoot)
if (-not $NativeRoot) { $NativeRoot = Join-Path $bundleRoot 'data\openwebui' }
$NativeRoot = [IO.Path]::GetFullPath($NativeRoot)
if (-not $Python) {
  $candidate = Join-Path $bundleRoot 'runtime\python\python.exe'
  if (Test-Path $candidate) { $Python = $candidate } else { $Python = Join-Path $repoRoot 'dist\openwebui-classroom-review-windows-x64\runtime\python\python.exe' }
}
if (-not (Test-Path -LiteralPath $Python)) { throw "Portable Python not found: $Python" }
New-Item -ItemType Directory -Force -Path $DataRoot,(Join-Path $DataRoot 'logs') | Out-Null
$env:PYTHONPATH = $appRoot
$db = Join-Path $DataRoot 'classroom.db'
$env:CLASSROOM_DB = $db
$env:CLASSROOM_DATA = $DataRoot
$env:CLASSROOM_OPENWEBUI_INTERNAL_URL = ('http://127.0.0.1:{0}' -f $WebPort)
$env:ENABLE_SIGNUP = 'false'
$pidPath = Join-Path $DataRoot 'classroom-instance.json'
if (Test-Path $pidPath) {
  try {
    $old = Get-Content -Raw $pidPath | ConvertFrom-Json
    $oldProc = Get-Process -Id ([int]$old.service_pid) -ErrorAction SilentlyContinue
    $expectedExe = (Resolve-Path $old.executable -ErrorAction SilentlyContinue).Path
    $actualExe = if($oldProc){(Resolve-Path $oldProc.Path -ErrorAction SilentlyContinue).Path}else{$null}
    $oldStart = $old.service_started_at
    $recordStart = if($oldStart -is [DateTime]){$oldStart.ToUniversalTime()}elseif($oldStart){[DateTimeOffset]::Parse([string]$oldStart).UtcDateTime}else{$null}
    $sameStart = $oldProc -and $recordStart -and ([Math]::Abs(($oldProc.StartTime.ToUniversalTime()-$recordStart).TotalSeconds) -lt 30)
    if ($oldProc -and $actualExe -eq $expectedExe -and $sameStart) {
      $oldHealth = Invoke-RestMethod -Uri ('http://127.0.0.1:{0}/health' -f $old.service_port) -TimeoutSec 2
      $oldWeb = if([int]$old.web_pid -gt 0){Get-Process -Id ([int]$old.web_pid) -ErrorAction SilentlyContinue}else{$null}
      if(-not $oldHealth.ready -or (-not $NoOpenWebUI -and -not $oldWeb)){throw 'The recorded installation is only partly running. Run Stop.ps1 for this data root before restarting.'}
      if(-not $NoOpenWebUI){$null=Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:{0}/health' -f $old.web_port) -TimeoutSec 2}
      Write-Output "Classroom services are already running (service PID $($old.service_pid))."; exit 0
    }
    if([int]$old.web_pid -gt 0 -and (Get-Process -Id ([int]$old.web_pid) -ErrorAction SilentlyContinue)){throw 'A recorded WebUI process remains. Run Stop.ps1 for this data root before restarting.'}
  } catch { throw "Cannot safely reuse the existing instance record: $($_.Exception.Message)" }
}
$existingHealth=$null
try {
  $existingHealth = Invoke-RestMethod -Uri ('http://127.0.0.1:{0}/health' -f $ServicePort) -TimeoutSec 2
} catch {}
if($existingHealth){throw "Port $ServicePort belongs to another service; choose an unused port."}
$serviceOut = Join-Path $DataRoot 'logs\classroom-service.out.log'; $serviceErr = Join-Path $DataRoot 'logs\classroom-service.err.log'
. (Join-Path $PSScriptRoot 'ProviderConfig.ps1')
Initialize-ClassroomProvider -DataRoot $DataRoot
$serviceArgs = @((Join-Path $appRoot 'api_classroom.py'),'--db',$db,'--data-root',$DataRoot,'--host','127.0.0.1','--port',$ServicePort,'--native-url',$env:CLASSROOM_OPENWEBUI_INTERNAL_URL)
try {
  $service = Start-Process -FilePath $Python -ArgumentList (Format-NativeArguments $serviceArgs) -WorkingDirectory $appRoot -RedirectStandardOutput $serviceOut -RedirectStandardError $serviceErr -PassThru -WindowStyle Hidden
} finally { $env:CLASSROOM_PROVIDER_API_KEY = $null }
try {
  $ready = $false
  for($i=0;$i -lt 30;$i++){ try{$health=Invoke-RestMethod -Uri ('http://127.0.0.1:{0}/health' -f $ServicePort) -TimeoutSec 2;if($health.ready){$ready=$true;break}}catch{};Start-Sleep -Milliseconds 500 }
  if(-not $ready){throw "Classroom service did not become ready. See $serviceErr"}
  $web = $null
  if(-not $NoOpenWebUI){
    if(-not (Test-Path -LiteralPath (Join-Path $NativeRoot 'classroom-baseline.json'))){throw 'Run prepare_installation.py into a new directory and select its classroom and openwebui directories.'}
    . (Join-Path $PSScriptRoot 'TeacherLogin.ps1')
    Initialize-ClassroomTeacherLogin -DataRoot $DataRoot -NativeRoot $NativeRoot -Python $Python
    if(-not $env:WEBUI_ADMIN_PASSWORD){$secure=Read-Host '教师管理员密码（在本机加密保存）' -AsSecureString;$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);try{$env:WEBUI_ADMIN_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
    if(-not $env:WEBUI_ADMIN_NAME){$env:WEBUI_ADMIN_NAME='Teacher'}
    $env:HOST=$BindHost; $env:PORT="$WebPort"; $env:DATA_DIR=$NativeRoot; $env:CLASSROOM_OPENWEBUI_URL=('http://127.0.0.1:{0}' -f $WebPort)
    $webOut=Join-Path $DataRoot 'logs\openwebui.out.log';$webErr=Join-Path $DataRoot 'logs\openwebui.err.log'
    $webArgs=@((Join-Path $appRoot 'run_openwebui.py'),'--data-dir',$env:DATA_DIR,'--classroom-db',$db,'--classroom-data',$DataRoot,'--host',$BindHost,'--port',$WebPort,'--classroom-health-url',('http://127.0.0.1:{0}/health' -f $ServicePort))
    $web=Start-Process -FilePath $Python -ArgumentList (Format-NativeArguments $webArgs) -WorkingDirectory $appRoot -RedirectStandardOutput $webOut -RedirectStandardError $webErr -PassThru -WindowStyle Hidden
    $webReady=$false
    for($i=0;$i -lt 180;$i++){$web.Refresh();if($web.HasExited){throw "Open WebUI exited during startup. See $webErr"};try{$status=Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:{0}/health' -f $WebPort) -TimeoutSec 2;if($status.StatusCode -eq 200){$webReady=$true;break}}catch{};Start-Sleep -Seconds 1}
    if(-not $webReady){throw "Open WebUI did not become ready. See $webErr"}
    $bootOut=Join-Path $DataRoot 'logs\bootstrap.out.log'; & $Python (Join-Path $appRoot 'bootstrap_openwebui.py') 2>&1 | Tee-Object -FilePath $bootOut
    if($LASTEXITCODE -ne 0){throw 'Bootstrap failed. If the administrator password changed, run Reset-SavedTeacherLogin.cmd and start again.'}
    Save-ClassroomTeacherLogin -DataRoot $DataRoot
  }
  $webPid = if($web){$web.Id}else{0}
  $serviceStarted = $service.StartTime.ToUniversalTime().ToString('o')
  $webStarted = if($web){$web.StartTime.ToUniversalTime().ToString('o')}else{''}
  @{service_pid=$service.Id;web_pid=$webPid;service_port=$ServicePort;web_port=$WebPort;native_root=$NativeRoot;service_started_at=$serviceStarted;web_started_at=$webStarted;executable=(Resolve-Path $Python).Path;data_root=$DataRoot;started_at=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding UTF8
  Write-Output "Classroom service ready; data root $DataRoot"
  if($web){
    if($BindHost -eq '127.0.0.1' -or $BindHost -eq 'localhost'){
      Write-Output "Open WebUI (loopback): http://127.0.0.1:$WebPort"
      Write-Output "Student LAN access requires Start.ps1 -Lan (cleartext HTTP)."
    } else {
      Write-Output "Open WebUI: http://<teacher-ip>:$WebPort (cleartext; prefer a reverse proxy with TLS)"
    }
    Write-Output "Teacher classroom page: http://127.0.0.1:$WebPort/classroom/teacher/"
  }
} catch {
  if($web){Stop-Process -Id $web.Id -Force -ErrorAction SilentlyContinue};if($service){Stop-Process -Id $service.Id -Force -ErrorAction SilentlyContinue};throw
} finally { $env:WEBUI_ADMIN_PASSWORD = $null }
