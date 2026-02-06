#!/bin/bash
# Polymarket Monitor - Cron Setup Script (Linux/Mac)
# Run this on your server to set up automated collection

set -e

# Configuration - UPDATE THESE PATHS
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
# Use venv python if it exists, otherwise system python
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_DIR/venv/bin/python"
else
    PYTHON_CMD="${PYTHON_CMD:-python3}"
fi
COLLECTOR_SCRIPT="$PROJECT_DIR/collector.py"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/collector.log"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Polymarket Monitor - Cron Setup"
echo "=========================================="
echo
echo "Project directory: $PROJECT_DIR"
echo "Python command: $PYTHON_CMD"
echo

# 1. Verify files exist
echo "[1/5] Verifying project files..."
if [ ! -f "$COLLECTOR_SCRIPT" ]; then
    echo -e "${RED}ERROR: collector.py not found at $COLLECTOR_SCRIPT${NC}"
    echo "Make sure you're running this from the project directory"
    exit 1
fi
echo -e "${GREEN}OK${NC} - collector.py found"

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}WARNING: .env file not found${NC}"
    echo "Make sure to configure .env before running"
fi
echo

# 2. Create logs directory
echo "[2/5] Creating logs directory..."
mkdir -p "$LOG_DIR"
echo -e "${GREEN}OK${NC} - Logs directory: $LOG_DIR"
echo

# 3. Test Python and dependencies
echo "[3/5] Testing Python environment..."
if ! $PYTHON_CMD -c "import requests, mysql.connector, dotenv" 2>/dev/null; then
    echo -e "${RED}ERROR: Missing Python dependencies${NC}"
    echo "Run: pip install -r requirements.txt"
    exit 1
fi
echo -e "${GREEN}OK${NC} - Python dependencies installed"
echo

# 4. Check existing cron job
echo "[4/5] Checking existing cron jobs..."
CRON_CMD="*/30 * * * * cd $PROJECT_DIR && $PYTHON_CMD $COLLECTOR_SCRIPT >> $LOG_FILE 2>&1"
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "collector.py" || true)

if [ -n "$EXISTING_CRON" ]; then
    echo -e "${YELLOW}Existing cron job found:${NC}"
    echo "  $EXISTING_CRON"
    echo
    read -p "Remove existing and reinstall? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        crontab -l 2>/dev/null | grep -v -F "collector.py" | crontab -
        echo -e "${GREEN}OK${NC} - Old cron job removed"
    else
        echo "Keeping existing cron job. Exiting."
        exit 0
    fi
fi
echo

# 5. Install cron job
echo "[5/5] Installing cron job..."
(crontab -l 2>/dev/null || true; echo "$CRON_CMD") | crontab -

# Verify
if crontab -l | grep -q -F "collector.py"; then
    echo -e "${GREEN}OK${NC} - Cron job installed successfully"
else
    echo -e "${RED}ERROR: Cron job installation failed${NC}"
    exit 1
fi

echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "Schedule: Every 30 minutes"
echo "Log file: $LOG_FILE"
echo
echo "Useful commands:"
echo "  View logs:     tail -f $LOG_FILE"
echo "  Check status:  python monitor.py"
echo "  List cron:     crontab -l"
echo "  Remove cron:   crontab -l | grep -v collector.py | crontab -"
echo
echo "The first automated run will occur at the next :00 or :30 mark."
echo

# Optional: Run now
read -p "Run collector now to verify? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running collector..."
    cd "$PROJECT_DIR"
    $PYTHON_CMD "$COLLECTOR_SCRIPT"
    echo -e "${GREEN}OK${NC} - Test run complete"
fi
