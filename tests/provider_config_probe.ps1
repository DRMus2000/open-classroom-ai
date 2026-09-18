$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\scripts\ProviderConfig.ps1')
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('classroom-provider-test-' + [Guid]::NewGuid().ToString('N'))
$script:answers = New-Object System.Collections.Queue
function Read-Host {
  param([string]$Prompt, [switch]$AsSecureString)
  if ($script:answers.Count -eq 0) { throw 'Unexpected configuration prompt' }
  $value = $script:answers.Dequeue()
  if ($AsSecureString) { return ConvertTo-SecureString $value -AsPlainText -Force }
  return $value
}
function Clear-ProviderEnv {
  $env:CLASSROOM_PROVIDER_URL = $null
  $env:CLASSROOM_MODELS = $null
  $env:CLASSROOM_PROVIDER_API_KEY = $null
}
Clear-ProviderEnv
$script:answers.Enqueue('https://example.invalid/v1')
$script:answers.Enqueue('test-model')
$script:answers.Enqueue('synthetic-secret-one')
Initialize-ClassroomProvider -DataRoot $scratch
$path = Join-Path $scratch 'provider-config.json'
$raw = Get-Content -Raw $path
if ($raw.Contains('synthetic-secret-one')) { throw 'Plaintext secret was saved' }
Clear-ProviderEnv
Initialize-ClassroomProvider -DataRoot $scratch
if ($env:CLASSROOM_PROVIDER_API_KEY -cne 'synthetic-secret-one') { throw 'DPAPI roundtrip failed' }
if ($env:CLASSROOM_MODELS -ne 'test-model') { throw 'Model was not remembered' }
# A copied or damaged DPAPI blob must prompt for just a replacement key.
$config = $raw | ConvertFrom-Json
$config.encrypted_key = 'unreadable-on-another-machine'
$config | ConvertTo-Json | Set-Content $path -Encoding UTF8
Clear-ProviderEnv
$script:answers.Enqueue('synthetic-secret-two')
Initialize-ClassroomProvider -DataRoot $scratch
if ($env:CLASSROOM_PROVIDER_API_KEY -cne 'synthetic-secret-two') { throw 'Key recovery failed' }
# Changing the provider via environment cannot send the saved key to it.
Clear-ProviderEnv
$env:CLASSROOM_PROVIDER_URL = 'https://different.invalid/v1'
$script:answers.Enqueue('synthetic-secret-three')
Initialize-ClassroomProvider -DataRoot $scratch
if ($env:CLASSROOM_PROVIDER_API_KEY -cne 'synthetic-secret-three') { throw 'Endpoint key isolation failed' }
$script:answers.Enqueue('https://replacement.invalid/v1')
$script:answers.Enqueue('replacement-model')
$script:answers.Enqueue('synthetic-secret-four')
Initialize-ClassroomProvider -DataRoot $scratch -Force
Clear-ProviderEnv
Initialize-ClassroomProvider -DataRoot $scratch
if ($env:CLASSROOM_PROVIDER_API_KEY -cne 'synthetic-secret-four' -or $env:CLASSROOM_MODELS -ne 'replacement-model') { throw 'Reconfiguration failed' }
if ($script:answers.Count) { throw 'Not all expected prompts occurred' }
Clear-ProviderEnv
Write-Output 'PROVIDER_CONFIG_DPAPI_FIRST_START_RESTART_RECOVERY_CHANGE_OK'
