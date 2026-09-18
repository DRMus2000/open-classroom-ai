[CmdletBinding(SupportsShouldProcess=$true)]
param([string]$RuleName = 'Classroom Open WebUI', [int]$Port = 3000)
if ($PSCmdlet.ShouldProcess("Windows Firewall rule $RuleName", "allow TCP $Port on the teacher LAN profile")) {
  netsh advfirewall firewall add rule name="$RuleName" dir=in action=allow protocol=TCP localport=$Port profile=Private
  if ($LASTEXITCODE -ne 0) { throw "Firewall rule failed ($LASTEXITCODE)" }
}
