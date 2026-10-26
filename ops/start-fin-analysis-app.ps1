$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$dashboardRoot = Join-Path $projectRoot 'dashboard'
$url = 'http://127.0.0.1:3000/handbook'
$logDirectory = Join-Path $projectRoot '.cache\dashboard'
$logPath = Join-Path $logDirectory 'startup.log'
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$nextPath = Join-Path $dashboardRoot 'node_modules\next\dist\bin\next'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

try {
    $response = Invoke-WebRequest -Uri $url -TimeoutSec 4 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Start-Process $url
        exit 0
    }
} catch {
    # Start the local production server if the handbook is not responding yet.
}

if (!(Test-Path -LiteralPath (Join-Path $dashboardRoot '.next'))) {
    throw 'Dashboard production build is missing. Build the dashboard before starting the app.'
}
Start-Process -FilePath $nodePath `
    -ArgumentList @("`"$nextPath`"", 'start', '--hostname', '127.0.0.1') `
    -WorkingDirectory $dashboardRoot -WindowStyle Hidden `
    -RedirectStandardOutput $logPath -RedirectStandardError (Join-Path $logDirectory 'startup-error.log')

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (!$ready) { throw "Fin Analysis did not become ready. Check $logDirectory" }
Start-Process $url
Add-Content -LiteralPath $logPath -Value ("{0:o} Handbook app opened at {1}" -f (Get-Date), $url)
