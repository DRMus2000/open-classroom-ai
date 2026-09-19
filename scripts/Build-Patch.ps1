[CmdletBinding()]
param(
  [string]$Runtime = (Join-Path $PSScriptRoot '..\..\_release-build\openwebui-classroom-windows-x64\runtime'),
  [string]$Output = (Join-Path $PSScriptRoot '..\release\openwebui-classroom-2.1.8-audit-patch.zip')
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $Runtime 'python\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Portable runtime Python not found: $python" }
& $python -B (Join-Path $PSScriptRoot '..\app\build_patch.py') --output $Output
if ($LASTEXITCODE -ne 0) { throw 'Classroom patch build failed.' }
