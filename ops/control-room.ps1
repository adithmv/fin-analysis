param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'enable', 'disable')]
    [string]$Operation,

    [ValidateSet('alerts', 'news', 'backup')]
    [string]$ProcessName
)

$ErrorActionPreference = 'Stop'
$definitions = [ordered]@{
    alerts = @{
        task = 'Fin Analysis Alert Checks'
        label = 'Telegram health alerts'
        schedule = 'Every 15 minutes'
        description = 'Checks project health and sends private Telegram incident alerts.'
    }
    news = @{
        task = 'Fin Analysis News Updates'
        label = 'News updates'
        schedule = 'Every 30 minutes'
        description = 'Collects and processes the enabled personal RSS feeds.'
    }
    backup = @{
        task = 'Fin Analysis Daily Backup'
        label = 'Daily backup'
        schedule = 'Daily at 8:30 PM IST'
        description = 'Copies the database backup to the configured local and Google Drive folders.'
    }
}

function Get-ProcessStatus([string]$id, [hashtable]$definition) {
    $task = Get-ScheduledTask -TaskName $definition.task -ErrorAction SilentlyContinue
    if (!$task) {
        return [pscustomobject]@{
            id = $id; label = $definition.label; schedule = $definition.schedule
            description = $definition.description; available = $false; enabled = $false
            state = 'Missing'; lastRun = $null; lastResult = $null
        }
    }
    $info = Get-ScheduledTaskInfo -TaskName $definition.task -ErrorAction SilentlyContinue
    [pscustomobject]@{
        id = $id
        label = $definition.label
        schedule = $definition.schedule
        description = $definition.description
        available = $true
        enabled = ($task.State -ne 'Disabled')
        state = [string]$task.State
        lastRun = if ($info -and $info.LastRunTime -gt [datetime]::MinValue) { $info.LastRunTime.ToString('o') } else { $null }
        lastResult = if ($info) { [int]$info.LastTaskResult } else { $null }
    }
}

if ($Operation -eq 'status') {
    $result = foreach ($entry in $definitions.GetEnumerator()) {
        Get-ProcessStatus $entry.Key $entry.Value
    }
    ConvertTo-Json -InputObject @($result) -Compress -Depth 4
    exit 0
}

if (!$ProcessName -or !$definitions.Contains($ProcessName)) {
    throw 'Select a supported process.'
}
$definition = $definitions[$ProcessName]
if (!(Get-ScheduledTask -TaskName $definition.task -ErrorAction SilentlyContinue)) {
    throw 'The selected scheduled process is not installed.'
}
if ($Operation -eq 'enable') {
    Enable-ScheduledTask -TaskName $definition.task | Out-Null
} else {
    Disable-ScheduledTask -TaskName $definition.task | Out-Null
}
Get-ProcessStatus $ProcessName $definition | ConvertTo-Json -Compress -Depth 4
