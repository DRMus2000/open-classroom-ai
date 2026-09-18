[CmdletBinding()]
param([string]$DataRoot = '')
$ErrorActionPreference = 'Stop'
$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $DataRoot) { $DataRoot = Join-Path $bundleRoot 'data\classroom' }
$DataRoot = [IO.Path]::GetFullPath($DataRoot)
$pidPath = Join-Path $DataRoot 'classroom-instance.json'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output 'Classroom service is not running.'; exit 0 }
$record = Get-Content -Raw $pidPath | ConvertFrom-Json
$servicePort = if($record.service_port){[int]$record.service_port}else{8790}
$serviceProcess=Get-Process -Id ([int]$record.service_pid) -ErrorAction SilentlyContinue
if($serviceProcess){
  $recordTime=if($record.service_started_at -is [DateTime]){$record.service_started_at.ToUniversalTime()}else{[DateTimeOffset]::Parse([string]$record.service_started_at).UtcDateTime}
  if((Resolve-Path $serviceProcess.Path).Path -ne (Resolve-Path $record.executable).Path -or [Math]::Abs(($serviceProcess.StartTime.ToUniversalTime()-$recordTime).TotalSeconds) -ge 2){throw 'The service PID belongs to a different process; it was not stopped.'}
  & $record.executable (Join-Path $bundleRoot 'app\drain_classroom.py') --data-root $DataRoot --port $servicePort
  if ($LASTEXITCODE -ne 0) { throw 'Graceful classroom drain failed; processes were not forcibly stopped.' }
}
$unmatched=$false
foreach($field in @('web_pid','service_pid')){
  $id=[int]$record.$field
  if($id -le 0){continue}
  try{
    $proc=Get-Process -Id $id -ErrorAction Stop
    $sameExe = ((Resolve-Path $proc.Path -ErrorAction SilentlyContinue).Path -eq (Resolve-Path $record.executable).Path)
    $startProperty = $field -replace '_pid','_started_at'
    $startValue = $record.$startProperty
    $recordStart = if($startValue){if($startValue -is [DateTime]){$startValue.ToUniversalTime()}else{[DateTimeOffset]::Parse([string]$startValue).UtcDateTime}}else{$null}
    $sameStart = $recordStart -and ([Math]::Abs(($proc.StartTime.ToUniversalTime()-$recordStart).TotalSeconds) -lt 2)
    if($sameExe -and $sameStart){
      Stop-Process -Id $id -ErrorAction SilentlyContinue
    } else { $unmatched=$true;Write-Warning "Recorded $field does not match the classroom executable/start time; it was not stopped." }
  }catch{if(Get-Process -Id $id -ErrorAction SilentlyContinue){$unmatched=$true};Write-Warning $_.Exception.Message}
}
Start-Sleep -Milliseconds 500
if($unmatched){throw 'Unmatched processes remain; the instance record was preserved.'}
Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
Write-Output 'Classroom services stopped.'
