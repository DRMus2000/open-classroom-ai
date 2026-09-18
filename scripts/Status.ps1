[CmdletBinding()]
param([string]$DataRoot = '', [string]$BindHost = '127.0.0.1', [int]$ServicePort = 8790, [int]$WebPort = 3000)
$ErrorActionPreference = 'SilentlyContinue'
$bundleRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if(-not $DataRoot){$DataRoot=Join-Path $bundleRoot 'data\classroom'}
$pidPath=Join-Path $DataRoot 'classroom-instance.json'
$result=[ordered]@{pid_record=Test-Path $pidPath;service_process=$false;web_process=$false;service_health=$null;web_health=$null}
if($result.pid_record){
  $record=Get-Content -Raw $pidPath|ConvertFrom-Json
  if(-not $PSBoundParameters.ContainsKey('ServicePort')){$ServicePort=[int]$record.service_port}
  if(-not $PSBoundParameters.ContainsKey('WebPort')){$WebPort=[int]$record.web_port}
  $expectedExe=(Resolve-Path $record.executable -ErrorAction SilentlyContinue).Path
  $service=Get-Process -Id ([int]$record.service_pid) -ErrorAction SilentlyContinue
  $web=if([int]$record.web_pid -gt 0){Get-Process -Id ([int]$record.web_pid) -ErrorAction SilentlyContinue}else{$null}
  $sameInstance = { param($proc,$field) if(-not $proc -or (Resolve-Path $proc.Path -ErrorAction SilentlyContinue).Path -ne $expectedExe){return $false};$value=$record.$field;if(-not $value){return $true};try{$recordStart=if($value -is [DateTime]){$value.ToUniversalTime()}else{[DateTimeOffset]::Parse([string]$value).UtcDateTime};$delta=($proc.StartTime.ToUniversalTime()-$recordStart).TotalSeconds;return [Math]::Abs($delta) -lt 30}catch{return $false} }
  $result.service_process=[bool](& $sameInstance $service 'service_started_at')
  $result.web_process=[bool](& $sameInstance $web 'web_started_at')
}
try{$result.service_health=Invoke-RestMethod -Uri ('http://{0}:{1}/health' -f $BindHost,$ServicePort) -TimeoutSec 3}catch{$result.service_health=@{ready=$false;error='unreachable'}}
try{$result.web_health=Invoke-WebRequest -UseBasicParsing -Uri ('http://{0}:{1}/health' -f $BindHost,$WebPort) -TimeoutSec 3|Select-Object -ExpandProperty StatusCode}catch{$result.web_health=0}
$result|ConvertTo-Json -Depth 8
