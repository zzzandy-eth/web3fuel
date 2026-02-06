# Polymarket Monitor - Windows Task Scheduler Setup
# Run this script as Administrator in PowerShell

param(
    [string]$ProjectDir = $PSScriptRoot,
    [string]$PythonPath = "python",
    [int]$IntervalMinutes = 30
)

$TaskName = "PolymarketMonitor"
$CollectorScript = Join-Path $ProjectDir "collector.py"
$LogDir = Join-Path $ProjectDir "logs"
$LogFile = Join-Path $LogDir "collector.log"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Polymarket Monitor - Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project directory: $ProjectDir"
Write-Host "Python path: $PythonPath"
Write-Host "Interval: Every $IntervalMinutes minutes"
Write-Host ""

# 1. Verify files exist
Write-Host "[1/5] Verifying project files..." -ForegroundColor Yellow
if (-not (Test-Path $CollectorScript)) {
    Write-Host "ERROR: collector.py not found at $CollectorScript" -ForegroundColor Red
    exit 1
}
Write-Host "OK - collector.py found" -ForegroundColor Green
Write-Host ""

# 2. Create logs directory
Write-Host "[2/5] Creating logs directory..." -ForegroundColor Yellow
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
Write-Host "OK - Logs directory: $LogDir" -ForegroundColor Green
Write-Host ""

# 3. Check if task exists
Write-Host "[3/5] Checking existing scheduled task..." -ForegroundColor Yellow
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Existing task found: $TaskName" -ForegroundColor Yellow
    $response = Read-Host "Remove existing and reinstall? (y/n)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "OK - Old task removed" -ForegroundColor Green
    } else {
        Write-Host "Keeping existing task. Exiting."
        exit 0
    }
}
Write-Host ""

# 4. Create the scheduled task
Write-Host "[4/5] Creating scheduled task..." -ForegroundColor Yellow

# Create the action - run Python with collector.py, output to log
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$CollectorScript`"" `
    -WorkingDirectory $ProjectDir

# Create trigger - every N minutes
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Polymarket spike monitor - collects data every $IntervalMinutes minutes" `
        -Force | Out-Null

    Write-Host "OK - Scheduled task created" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to create scheduled task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Try running PowerShell as Administrator" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# 5. Verify task
Write-Host "[5/5] Verifying task..." -ForegroundColor Yellow
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "OK - Task verified successfully" -ForegroundColor Green
} else {
    Write-Host "ERROR: Task verification failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Schedule: Every $IntervalMinutes minutes"
Write-Host "Log file: $LogFile"
Write-Host ""
Write-Host "Useful commands (PowerShell):"
Write-Host "  View task:     Get-ScheduledTask -TaskName $TaskName"
Write-Host "  Run now:       Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Disable:       Disable-ScheduledTask -TaskName $TaskName"
Write-Host "  Enable:        Enable-ScheduledTask -TaskName $TaskName"
Write-Host "  Remove:        Unregister-ScheduledTask -TaskName $TaskName"
Write-Host ""
Write-Host "View logs:"
Write-Host "  Get-Content $LogFile -Tail 50"
Write-Host ""

# Optional: Run now
$response = Read-Host "Run collector now to verify? (y/n)"
if ($response -eq 'y' -or $response -eq 'Y') {
    Write-Host "Running collector..." -ForegroundColor Yellow
    Set-Location $ProjectDir
    & $PythonPath $CollectorScript
    Write-Host "OK - Test run complete" -ForegroundColor Green
}
