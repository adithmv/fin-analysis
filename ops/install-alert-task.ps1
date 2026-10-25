$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.cache\alerts-runtime\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Host alert environment is missing; follow alerts/README.md' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$shellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$scriptPath = Join-Path $PSScriptRoot 'alerts.ps1'
$action = New-ScheduledTaskAction -Execute $shellPath -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "' + $scriptPath + '"') -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName 'Fin Analysis Alert Checks' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Check project health every 15 minutes and deliver private Telegram incident batches; requires signed-in user and internet.' -Force | Select-Object TaskName,State
