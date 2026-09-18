[CmdletBinding()]
param([string]$DataRoot = '')
$ErrorActionPreference = 'Stop'
if (-not $DataRoot) { $DataRoot = Join-Path $PSScriptRoot '..\data\classroom' }
. (Join-Path $PSScriptRoot 'ProviderConfig.ps1')
try {
  Initialize-ClassroomProvider -DataRoot ([IO.Path]::GetFullPath($DataRoot)) -Force
  Write-Host 'Configuration updated. Restart the classroom to apply it.'
} finally { $env:CLASSROOM_PROVIDER_API_KEY = $null }
