[CmdletBinding()]
param(
  [string]$DataRoot = (Join-Path $PSScriptRoot '..\data\classroom'),
  [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$appRoot = Join-Path $bundleRoot 'app'
$python = if ($env:CLASSROOM_PYTHON) { $env:CLASSROOM_PYTHON } else { Join-Path $bundleRoot 'runtime\python\python.exe' }
if (-not (Test-Path $python)) { $python = Join-Path $projectRoot 'dist\openwebui-classroom-review-windows-x64\runtime\python\python.exe' }
$db = Join-Path $DataRoot 'classroom.db'
if (-not (Test-Path $python)) { throw "Portable Python not found: $python" }
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
$arguments = @((Join-Path $appRoot 'migrate_classroom.py'),'--db',$db)
if ($VerifyOnly) { $arguments += '--verify-only' }
$env:PYTHONPATH = $appRoot
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "Classroom migration failed ($LASTEXITCODE)" }
