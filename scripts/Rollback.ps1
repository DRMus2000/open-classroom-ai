[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$BeforeBackup,
  [Parameter(Mandatory=$true)][string]$DataRoot,
  [Parameter(Mandatory=$true)][string]$NativeRoot,
  [Parameter(Mandatory=$true)][string]$PreservedBackup,
  [Parameter(Mandatory=$true)][string]$TargetRoot
)
$ErrorActionPreference='Stop'
if(-not (Test-Path -LiteralPath $BeforeBackup -PathType Leaf)){throw 'The pre-change backup is required.'}
if(Test-Path -LiteralPath $TargetRoot){throw 'Rollback destination must be a new directory.'}
if(Test-Path -LiteralPath $PreservedBackup){throw 'Choose a new filename for the post-change backup.'}
if(Test-Path -LiteralPath (Join-Path $DataRoot 'classroom-instance.json')){
  & (Join-Path $PSScriptRoot 'Stop.ps1') -DataRoot $DataRoot
}
& (Join-Path $PSScriptRoot 'Backup.ps1') -DataRoot $DataRoot -NativeRoot $NativeRoot -Output $PreservedBackup
& (Join-Path $PSScriptRoot 'Restore.ps1') -Backup $BeforeBackup -TargetRoot $TargetRoot
Write-Output "Rollback copy verified at $TargetRoot. Post-change records preserved at $PreservedBackup."
Write-Output 'Start the verified copy with Start.ps1 using its data root and openwebui subdirectory.'
