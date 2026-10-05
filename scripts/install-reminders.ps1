<#
  install-reminders.ps1
  Turns on Athena's study reminders for your Windows account (no admin needed):
    - one scheduled task per reminder time (from Athena's Settings page),
      each showing a Windows notification that opens Athena when clicked;
    - a Startup shortcut so Athena's server runs quietly in the background after you log in.
  It also makes a private random topic name for optional phone reminders (ntfy app),
  which stay OFF until you switch them on in Settings.

  Run from the Athena folder:  powershell -ExecutionPolicy Bypass -File scripts\install-reminders.ps1
  Run it again after changing reminder times in Settings. Undo with uninstall-reminders.ps1.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$PythonW = Join-Path $Root '.venv\Scripts\pythonw.exe'
$NudgeScript = Join-Path $Root 'scripts\run_nudge.pyw'
$ServerScript = Join-Path $Root 'scripts\run_server.pyw'
$TaskFolder = '\Athena\'

if (-not (Test-Path $PythonW)) {
    Write-Host 'Athena is not set up yet. Run scripts\install-athena.bat first.' -ForegroundColor Red
    exit 1
}

# Reminder times and the phone topic come from Athena's own settings.
Push-Location $Root
try {
    $json = & $Python -c "import json; from athena import db, services, progress; c = db.connect(); s = services.settings(c); t = s.get('ntfy_topic') or ''; import secrets, string; t = t or 'athena-' + ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12)); progress.put_setting(c, 'ntfy_topic', t); c.commit(); print(json.dumps({'times': s['nudge_times'], 'topic': t}))"
} finally {
    Pop-Location
}
$info = $json | ConvertFrom-Json
$times = @($info.times | Where-Object { $_ -match '^\d{1,2}:\d{2}$' })
if ($times.Count -eq 0) { $times = @('08:30', '13:30', '19:30', '21:45') }

# Replace any earlier Athena reminder tasks.
Get-ScheduledTask -TaskPath $TaskFolder -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$action = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$NudgeScript`"" -WorkingDirectory $Root
foreach ($t in $times) {
    $at = [datetime]::ParseExact($t.PadLeft(5, '0'), 'HH:mm', $null)
    $trigger = New-ScheduledTaskTrigger -Daily -At $at
    $name = 'Reminder ' + $at.ToString('HH-mm')
    Register-ScheduledTask -TaskPath $TaskFolder -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Athena study reminder' | Out-Null
    Write-Host ('Reminder set for ' + $at.ToString('HH:mm'))
}

# Start Athena quietly at login (a shortcut in your Startup folder).
$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'Athena.lnk'
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $PythonW
$lnk.Arguments = "`"$ServerScript`""
$lnk.WorkingDirectory = $Root
$lnk.Description = 'Athena study tutor (runs in the background)'
$lnk.Save()
Write-Host 'Athena will start in the background when you log in.'

Write-Host ''
Write-Host 'Optional phone reminders: install the free "ntfy" app, add a subscription to this topic name:' -ForegroundColor Cyan
Write-Host ('    ' + $info.topic) -ForegroundColor White
Write-Host 'then switch on "Also send reminders to my phone" in Athena Settings.' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Done. Undo any time with scripts\uninstall-reminders.ps1' -ForegroundColor Green
