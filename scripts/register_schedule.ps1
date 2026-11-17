# Register the nightly pipeline refresh in Windows Task Scheduler.
#
#   powershell -ExecutionPolicy Bypass -File scripts\register_schedule.ps1            # daily at 00:05
#   powershell -ExecutionPolicy Bypass -File scripts\register_schedule.ps1 -At 00:30
#   Unregister-ScheduledTask -TaskName PressureIndexNightly -Confirm:$false             # remove it
#
# The task runs as the current user while logged on (Docker Desktop needs a user
# session). If the PC is off or asleep at that time, it runs as soon as it can.
param(
    [string]$At = "00:05",
    [string]$TaskName = "PressureIndexNightly"
)

$root   = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\update_pipeline.py"
if (-not (Test-Path $python)) { throw "Python venv not found at $python - create it first (see README)." }

$action   = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root
$trigger  = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Pressure Index: refresh data, rerun pipeline, rebuild + push Docker image, commit to git" -Force | Out-Null

Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
