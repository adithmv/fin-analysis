$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot '.cache\news-task'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$pythonPath = Join-Path $projectRoot 'news\.venv\Scripts\python.exe'
$env:HF_HOME = Join-Path $projectRoot '.cache\huggingface'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
# Model loaders write progress to stderr; native exit codes determine failure.
$ErrorActionPreference = 'Continue'
& $pythonPath "$projectRoot\news\main.py" fetch 2>&1 |
    Tee-Object -FilePath (Join-Path $logDirectory 'fetch.log')
$fetchExit = $LASTEXITCODE
# A failed feed must not stop processing items supplied by healthy feeds.
& $pythonPath "$projectRoot\news\main.py" process 2>&1 |
    Tee-Object -FilePath (Join-Path $logDirectory 'process.log')
$processExit = $LASTEXITCODE
if ($fetchExit -ne 0 -or $processExit -ne 0) { exit 1 }
exit 0
