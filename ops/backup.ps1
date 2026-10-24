$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
& "$projectRoot\.venv\Scripts\python.exe" "$PSScriptRoot\backup.py" @args
exit $LASTEXITCODE
