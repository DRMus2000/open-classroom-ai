[CmdletBinding()]
param(
  [string]$DataRoot = (Join-Path $PSScriptRoot '..\data\classroom'),
  [string]$NativeRoot = (Join-Path $PSScriptRoot '..\data\openwebui'),
  [string]$Output = (Join-Path $PSScriptRoot '..\backups\classroom-backup.zip')
)
$ErrorActionPreference = 'Stop'
$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$appRoot = Join-Path $bundleRoot 'app'
$python = if ($env:CLASSROOM_PYTHON) { $env:CLASSROOM_PYTHON } else { Join-Path $bundleRoot 'runtime\python\python.exe' }
if (-not (Test-Path $python)) { $python = Join-Path $projectRoot 'dist\openwebui-classroom-review-windows-x64\runtime\python\python.exe' }
$env:PYTHONPATH = $appRoot
New-Item -ItemType Directory -Force -Path (Split-Path $Output) | Out-Null
& $python (Join-Path $appRoot 'backup_classroom.py') backup --db (Join-Path $DataRoot 'classroom.db') --data-root $DataRoot --native-root $NativeRoot --output $Output
if ($LASTEXITCODE -ne 0) { throw "Classroom backup failed ($LASTEXITCODE)" }
