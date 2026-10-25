$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot '.cache\alerts'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
& "$projectRoot\.cache\alerts-runtime\.venv\Scripts\python.exe" "$projectRoot\alerts\main.py" check 2>&1 |
    Tee-Object -FilePath (Join-Path $logDirectory 'last-run.log')
exit $LASTEXITCODE
