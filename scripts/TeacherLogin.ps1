function Initialize-ClassroomTeacherLogin {
  param([string]$DataRoot, [string]$NativeRoot, [string]$Python)
  $path = Join-Path $DataRoot 'teacher-login.json'
  $saved = $null
  if (Test-Path -LiteralPath $path) {
    try {
      $saved = Get-Content -Raw -LiteralPath $path -Encoding UTF8 | ConvertFrom-Json
      if (-not $env:WEBUI_ADMIN_EMAIL -and $saved.version -eq 1 -and $saved.email -is [string]) { $env:WEBUI_ADMIN_EMAIL = $saved.email.Trim() }
    } catch { Write-Host 'Saved teacher email could not be read.' }
  }
  if (-not $env:WEBUI_ADMIN_EMAIL) {
    # Existing installations with one administrator need no repeat prompt.
    $lookup = Join-Path $PSScriptRoot '..\app\teacher_email.py'
    $existing = & $Python -B $lookup --native-root $NativeRoot
    if ($LASTEXITCODE -eq 0 -and $existing) { $env:WEBUI_ADMIN_EMAIL = ([string]$existing).Trim() }
  }
  if (-not $env:WEBUI_ADMIN_EMAIL) { $env:WEBUI_ADMIN_EMAIL = (Read-Host 'Teacher administrator email (remembered on this installation)').Trim() }
  if (-not $env:WEBUI_ADMIN_EMAIL) { throw 'A teacher administrator email is required.' }
  if (-not $env:WEBUI_ADMIN_PASSWORD -and $saved -and $saved.email -eq $env:WEBUI_ADMIN_EMAIL -and $saved.encrypted_password) {
    try {
      $secure = ConvertTo-SecureString $saved.encrypted_password -ErrorAction Stop
      $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
      try { $env:WEBUI_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
      finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secure.Dispose() }
    } catch { Write-Host 'Saved administrator password cannot be unlocked here. Enter it once on this computer.' }
  }
}

function Save-ClassroomTeacherLogin {
  param([string]$DataRoot)
  # Called only after successful administrator authentication/bootstrap.
  $secure = ConvertTo-SecureString $env:WEBUI_ADMIN_PASSWORD -AsPlainText -Force
  try { $encrypted = ConvertFrom-SecureString $secure -ErrorAction Stop }
  finally { $secure.Dispose() }
  @{version=1; email=$env:WEBUI_ADMIN_EMAIL; encrypted_password=$encrypted} | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $DataRoot 'teacher-login.json') -Encoding UTF8
}
