[CmdletBinding()]
param(
  [string]$DataRoot = (Join-Path $PSScriptRoot '..\data\classroom'),
  [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$appRoot = Join-Path $bundleRoot 'app'
$python = if ($env:CLASSROOM_PYTHON) { $env:CLASSROOM_PYTHON } else { Join-Path $bundleRoot 'runtime\python\python.exe' }
if (-not (Test-Path $python)) { $python = Join-Path $projectRoot 'dist\openwebui-classroom-review-windows-x64\runtime\python\python.exe' }
$db = Join-Path $DataRoot 'classroom.db'
if (-not (Test-Path $python)) { throw "Portable Python not found: $python" }
if (-not (Test-Path $db)) { throw "Classroom database not found: $db" }
$arguments = @((Join-Path $appRoot 'repair_v5_identities.py'),'--db',$db)
if ($Apply) { $arguments += '--apply' }
$env:PYTHONPATH = $appRoot
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "Classroom v5 identity repair failed ($LASTEXITCODE)" }
