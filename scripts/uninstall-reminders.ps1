<#
  uninstall-reminders.ps1
  Turns Athena's reminders off: removes its scheduled tasks and the Startup shortcut.
  Your study progress is not touched.

  Run from the Athena folder:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-reminders.ps1
#>
$ErrorActionPreference = 'Stop'
$TaskFolder = '\Athena\'

$tasks = @(Get-ScheduledTask -TaskPath $TaskFolder -ErrorAction SilentlyContinue)
if ($tasks.Count -gt 0) {
    $tasks | Unregister-ScheduledTask -Confirm:$false
    Write-Host ('Removed ' + $tasks.Count + ' reminder(s).')
} else {
    Write-Host 'No Athena reminders were set.'
}

$lnkPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Athena.lnk'
if (Test-Path $lnkPath) {
    Remove-Item $lnkPath
    Write-Host 'Athena will no longer start at login.'
}
Write-Host 'Done.' -ForegroundColor Green
