[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Backup,
  [Parameter(Mandatory=$true)][string]$TargetRoot
)
$ErrorActionPreference = 'Stop'
$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$appRoot = Join-Path $bundleRoot 'app'
$python = if ($env:CLASSROOM_PYTHON) { $env:CLASSROOM_PYTHON } else { Join-Path $bundleRoot 'runtime\python\python.exe' }
if (-not (Test-Path $python)) { $python = Join-Path $projectRoot 'dist\openwebui-classroom-review-windows-x64\runtime\python\python.exe' }
$env:PYTHONPATH = $appRoot
& $python (Join-Path $appRoot 'backup_classroom.py') restore --backup $Backup --target-root $TargetRoot
if ($LASTEXITCODE -ne 0) { throw "Classroom restore failed ($LASTEXITCODE)" }
