[CmdletBinding()]
param(
  [string]$Runtime = (Join-Path $PSScriptRoot '..\..\_release-build\openwebui-classroom-windows-x64\runtime'),
  [string]$Output = (Join-Path $PSScriptRoot '..\release\openwebui-classroom-2.1.7-windows-x64.zip')
)
$ErrorActionPreference = 'Stop'
$builder = Join-Path $PSScriptRoot '..\app\build_release.py'
$python = Join-Path $Runtime 'python\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Portable runtime Python not found: $python" }
& $python -B $builder --runtime $Runtime --output $Output
if ($LASTEXITCODE -ne 0) { throw 'Portable release build failed.' }
