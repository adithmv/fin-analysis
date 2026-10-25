$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$scriptPath = Join-Path $PSScriptRoot 'backup.ps1'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Project Python environment is missing' }
if ((Get-TimeZone).Id -ne 'India Standard Time') { throw 'Set Windows timezone to India Standard Time before installing the 20:30 schedule' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$shellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction -Execute $shellPath -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "' + $scriptPath + '"') -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '20:30'
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName 'Fin Analysis Daily Backup' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Daily private database backup at 20:30 IST to local storage and the Google Drive folder; requires the signed-in user and Drive desktop.' -Force | Select-Object TaskName,State
