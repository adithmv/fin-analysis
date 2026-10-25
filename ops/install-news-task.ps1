$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'news\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'News Python environment is missing' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$shellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$scriptPath = Join-Path $PSScriptRoot 'news.ps1'
$action = New-ScheduledTaskAction -Execute $shellPath -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "' + $scriptPath + '"') -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 55) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'Fin Analysis News Updates' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Fetch enabled personal RSS feeds and process new headlines locally every 30 minutes. Requires a signed-in user and internet.' -Force | Select-Object TaskName,State
