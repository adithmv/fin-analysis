$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot '.cache\backup'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\backup.py" @args 2>&1 | Tee-Object -FilePath (Join-Path $logDirectory 'last-run.log')
exit $LASTEXITCODE
