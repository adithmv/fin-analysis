$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot 'start-fin-analysis-app.ps1'
$shellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Fin Analysis.lnk'
$taskName = 'Fin Analysis Handbook App'

# Remove the old sign-in trigger so the app only starts when its shortcut is clicked.
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $shellPath
$shortcut.Arguments = '-NoProfile -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "' + $scriptPath + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Start Fin Analysis and open its handbook'
$shortcut.IconLocation = Join-Path $env:SystemRoot 'System32\shell32.dll,220'
$shortcut.Save()

Write-Output ('Created desktop shortcut: ' + $shortcutPath)
