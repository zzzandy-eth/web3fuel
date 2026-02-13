#!/bin/bash
# =============================================================================
# Macro Scanner - Cron Job Setup
# =============================================================================
# Installs cron jobs for optimized scanning schedule:
#   - 13:30 UTC (8:30 AM EST) daily - Morning data releases
#   - 18:00 UTC (1:00 PM EST) weekdays - Midday/Fed announcements
#   - 22:30 UTC (5:30 PM EST) weekdays - End-of-day wrap
#
# Cost: ~$0.13/weekday + ~$0.05/weekend = ~$3/month
#
# Usage:
#   chmod +x setup_cron.sh
#   ./setup_cron.sh
# =============================================================================

set -e

# Determine the project directory (where this script lives)
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_FILE="${PROJECT_DIR}/logs/scanner.log"

echo "============================================"
echo "Macro Scanner - Cron Setup"
echo "============================================"
echo "Project dir: ${PROJECT_DIR}"
echo "Python:      ${PYTHON_BIN}"
echo "Log file:    ${LOG_FILE}"
echo ""

# Ensure logs directory exists
mkdir -p "${PROJECT_DIR}/logs"

# Define the cron jobs
# 8:30 AM EST daily - morning data releases (CPI, NFP, GDP, jobless claims)
CRON_JOB_1="30 13 * * * cd ${PROJECT_DIR} && ${PYTHON_BIN} scanner.py >> ${LOG_FILE} 2>&1"
# 1:00 PM EST weekdays - midday catch-up, Fed announcements
CRON_JOB_2="0 18 * * 1-5 cd ${PROJECT_DIR} && ${PYTHON_BIN} scanner.py >> ${LOG_FILE} 2>&1"
# 5:30 PM EST weekdays - end-of-day wrap, after-hours moves
CRON_JOB_3="30 22 * * 1-5 cd ${PROJECT_DIR} && ${PYTHON_BIN} scanner.py >> ${LOG_FILE} 2>&1"

# Check if any macro-scanner cron jobs already exist
EXISTING=$(crontab -l 2>/dev/null | grep -F "macro-scanner/scanner.py" || true)

if [ -n "$EXISTING" ]; then
    echo "[INFO] Existing macro-scanner cron job(s) found:"
    echo "$EXISTING" | while read -r line; do
        echo "       ${line}"
    done
    echo ""
    read -p "Replace existing cron job(s)? (y/N): " CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo "[SKIP] Cron jobs not modified."
        exit 0
    fi
    # Remove all existing macro-scanner entries
    crontab -l 2>/dev/null | grep -v "macro-scanner/scanner.py" | crontab -
    echo "[OK]   Removed old cron job(s)."
fi

# Add all three cron jobs
(crontab -l 2>/dev/null; echo "${CRON_JOB_1}"; echo "${CRON_JOB_2}"; echo "${CRON_JOB_3}") | crontab -

echo "[OK]   Cron jobs installed:"
echo "       ${CRON_JOB_1}"
echo "       ${CRON_JOB_2}"
echo "       ${CRON_JOB_3}"
echo ""
echo "Schedule (UTC -> EST):"
echo "  13:30 daily    (8:30 AM)  - Morning data releases"
echo "  18:00 Mon-Fri  (1:00 PM)  - Midday/Fed announcements"
echo "  22:30 Mon-Fri  (5:30 PM)  - End-of-day wrap"
echo ""
echo "Verify with: crontab -l"
echo "Test run:    cd ${PROJECT_DIR} && ${PYTHON_BIN} scanner.py --test"
