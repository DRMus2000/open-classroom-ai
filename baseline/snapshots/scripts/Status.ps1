$Root = Split-Path -Parent $PSScriptRoot
function Test-Endpoint($url) { try { $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3; return $r.StatusCode } catch { return 0 } }
$web = Test-Endpoint 'http://127.0.0.1:3000/health'
$review = Test-Endpoint 'http://127.0.0.1:8790/health'
Write-Host ("Open WebUI health: {0}" -f $web)
Write-Host ("Review service health: {0}" -f $review)
if ($web -eq 200 -and $review -eq 200) { exit 0 } else { exit 1 }
