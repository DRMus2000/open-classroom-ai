$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
foreach ($file in @('data\openwebui\openwebui.pid','data\review\review.pid')) {
  $path = Join-Path $Root $file
  if (Test-Path -LiteralPath $path) {
    $id = [int](Get-Content -LiteralPath $path | Select-Object -First 1)
    Stop-Process -Id $id -Force
    Remove-Item -LiteralPath $path -Force
  }
}
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*$Root*open_webui*" -or $_.CommandLine -like "*$Root*review_service.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host 'Services stopped.'
