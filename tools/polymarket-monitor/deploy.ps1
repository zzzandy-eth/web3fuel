# Polymarket Monitor - Deploy to Linux Server
# Run this from PowerShell on your Windows machine

param(
    [string]$Server = "159.203.22.107",
    [string]$User = "root",
    [string]$RemoteDir = "/root/polymarket-monitor"
)

$LocalDir = $PSScriptRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Polymarket Monitor - Server Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server: $User@$Server"
Write-Host "Remote directory: $RemoteDir"
Write-Host "Local directory: $LocalDir"
Write-Host ""

# Files to deploy (exclude Windows-specific and cache)
$FilesToDeploy = @(
    "collector.py",
    "detector.py",
    "notifier.py",
    "database.py",
    "config.py",
    "monitor.py",
    "analyzer.py",
    "correlator.py",
    "patterns.py",
    "indicators.py",
    "correlations.json",
    "requirements.txt",
    ".env",
    ".env.example",
    "setup_cron.sh",
    "README.md",
    "__init__.py"
)

Write-Host "[1/4] Creating remote directory..." -ForegroundColor Yellow
ssh "$User@$Server" "mkdir -p $RemoteDir/logs"

Write-Host "[2/4] Copying files to server..." -ForegroundColor Yellow
foreach ($file in $FilesToDeploy) {
    $localPath = Join-Path $LocalDir $file
    if (Test-Path $localPath) {
        Write-Host "  Copying $file..."
        scp "$localPath" "${User}@${Server}:${RemoteDir}/"
    }
}

Write-Host "[3/4] Setting up Python environment on server..." -ForegroundColor Yellow
$setupCommands = @"
cd $RemoteDir

# Install pip if needed
which pip3 || apt-get update && apt-get install -y python3-pip

# Install dependencies
pip3 install -r requirements.txt

# Make setup script executable
chmod +x setup_cron.sh

# Test database connection
python3 -c "from database import get_connection; c = get_connection(); print('Database OK'); c.close()"

echo ""
echo "Setup complete!"
"@

ssh "$User@$Server" $setupCommands

Write-Host ""
Write-Host "[4/4] Installing cron job..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Run these commands on the server to finish setup:" -ForegroundColor Green
Write-Host ""
Write-Host "  ssh $User@$Server"
Write-Host "  cd $RemoteDir"
Write-Host "  ./setup_cron.sh"
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
