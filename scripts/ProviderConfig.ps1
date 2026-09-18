function Initialize-ClassroomProvider {
  param([Parameter(Mandatory=$true)][string]$DataRoot, [switch]$Force)
  $configPath = Join-Path $DataRoot 'provider-config.json'
  $saved = $null
  if (Test-Path -LiteralPath $configPath) {
    try {
      $saved = Get-Content -Raw -LiteralPath $configPath -Encoding UTF8 | ConvertFrom-Json
      if ($saved.version -ne 1) { throw 'Unsupported version' }
    } catch {
      Write-Host 'Saved API configuration is invalid. Please enter it again.'
      $saved = $null
    }
  }
  $url = $env:CLASSROOM_PROVIDER_URL
  $models = $env:CLASSROOM_MODELS
  $key = $null
  if (-not $Force) {
    if (-not $url -and $saved) { $url = $saved.url }
    if (-not $models -and $saved) { $models = $saved.models }
    if ($env:CLASSROOM_PROVIDER_API_KEY) {
      $key = ConvertTo-SecureString $env:CLASSROOM_PROVIDER_API_KEY -AsPlainText -Force
    } elseif ($saved -and $url -ceq $saved.url) {
      try {
        $key = ConvertTo-SecureString $saved.encrypted_key -ErrorAction Stop
      } catch {
        Write-Host 'The saved API key cannot be unlocked by this Windows account. Enter the key once on this computer.'
      }
    }
  } else {
    $url = $null
    $models = $null
  }
  if (-not $url) { $url = Read-Host 'OpenAI-compatible HTTPS base URL (ending in /v1)' }
  if (-not $models) { $models = Read-Host 'Upstream model ID (or comma-separated IDs)' }
  $url = ([string]$url).Trim().TrimEnd('/')
  $models = ([string]$models).Trim()
  $parsed = $null
  if (-not [Uri]::TryCreate($url, [UriKind]::Absolute, [ref]$parsed) -or $parsed.Scheme -ne 'https' -or $parsed.UserInfo -or $parsed.Query -or $parsed.Fragment) {
    throw 'Enter an HTTPS API base URL without credentials, query or fragment.'
  }
  if (-not $models) { throw 'A model ID is required.' }
  if (-not $key) { $key = Read-Host 'API key (saved encrypted for this Windows account)' -AsSecureString }
  if ($key.Length -eq 0) { throw 'An API key is required.' }
  # Windows PowerShell uses DPAPI CurrentUser when no explicit key is given.
  # Never serialize the plaintext secret or print it in error messages.
  $encrypted = ConvertFrom-SecureString $key -ErrorAction Stop
  $config = @{ version = 1; url = $url; models = $models; encrypted_key = $encrypted }
  New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
  $tempPath = Join-Path $DataRoot ('provider-config-' + [Guid]::NewGuid().ToString('N') + '.tmp')
  try {
    $config | ConvertTo-Json | Set-Content -LiteralPath $tempPath -Encoding UTF8
    if (Test-Path -LiteralPath $configPath) {
      $previousPath = $tempPath + '.previous'
      [IO.File]::Replace($tempPath, $configPath, $previousPath)
      Remove-Item -LiteralPath $previousPath
    } else {
      [IO.File]::Move($tempPath, $configPath)
    }
  } finally {
    if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath }
  }
  $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($key)
  try { $env:CLASSROOM_PROVIDER_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $key.Dispose() }
  $env:CLASSROOM_PROVIDER_URL = $url
  $env:CLASSROOM_MODELS = $models
  Write-Host 'API configuration saved locally; future starts will reuse it.'
}
