$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '..\data\classroom\teacher-login.json'
if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
Write-Host 'Saved startup login cleared. Next start will ask for the administrator password again. The website account and its password are unchanged.'
