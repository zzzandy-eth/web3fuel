# Polymarket Spike Monitor

Automated monitoring tool for detecting unusual trading activity (orderbook spikes) on Polymarket prediction markets. Sends Discord alerts when significant activity is detected.

## What It Does

- **Collects data** every 30 minutes from Polymarket APIs
- **Detects spikes** when orderbook depth exceeds 3x baseline
- **Sends Discord alerts** with market details and links
- **Stores time-series data** in MySQL for analysis
- **Auto-cleans** old data to prevent database bloat

## Use Case

Orderbook spikes can indicate:
- Large positions being entered
- Insider information leaking before news breaks
- Market makers adjusting for expected volatility
- Breaking news not yet public

## Quick Start

### 1. Install Dependencies

```bash
cd tools/polymarket-monitor
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

Required settings:
- `DB_HOST`, `DB_USER`, `DB_PASSWORD` - MySQL connection
- `DISCORD_WEBHOOK_URL` - Discord webhook for alerts

### 3. Initialize Database

```bash
python database.py
```

### 4. Test Everything

```bash
# Test API connectivity
python test_api.py

# Test Discord webhook
python notifier.py

# Run collector manually
python collector.py
```

### 5. Set Up Automation

**Windows (Task Scheduler):**
```powershell
# Run as Administrator
.\setup_task.ps1
```

**Linux/Mac (Cron):**
```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## Project Structure

```
polymarket-monitor/
├── collector.py      # Main data collection script
├── detector.py       # Spike detection algorithm
├── notifier.py       # Discord webhook notifications
├── database.py       # MySQL schema and operations
├── config.py         # Configuration management
├── monitor.py        # Status and health monitoring
├── setup_task.ps1    # Windows Task Scheduler setup
├── setup_cron.sh     # Linux/Mac cron setup
├── test_api.py       # API connectivity test
├── requirements.txt  # Python dependencies
├── .env.example      # Configuration template
└── logs/             # Log files (created automatically)
```

## Usage

### Check System Status

```bash
python monitor.py
```

Shows:
- Health status and issues
- Data collection statistics
- Spike detection summary
- Recent alerts
- Database size

### View Logs

**Windows:**
```powershell
Get-Content logs\collector.log -Tail 50
```

**Linux/Mac:**
```bash
tail -f logs/collector.log
```

### Manual Commands

```bash
# Collect data now
python collector.py

# Run spike detection only
python detector.py

# Send test Discord notification
python notifier.py

# Clean up old data
python database.py cleanup
```

## Configuration

### Environment Variables (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | MySQL server hostname | localhost |
| `DB_USER` | MySQL username | root |
| `DB_PASSWORD` | MySQL password | (required) |
| `DB_NAME` | Database name | polymarket_monitor |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL | (required for alerts) |
| `SPIKE_THRESHOLD_RATIO` | Spike detection threshold | 2.0 |
| `SNAPSHOT_RETENTION_DAYS` | Days to keep snapshot data | 7 |
| `ALERT_RETENTION_DAYS` | Days to keep alert records | 30 |

### Detection Parameters

Edit in `config.py` or via environment variables:

- **Threshold**: `SPIKE_THRESHOLD_RATIO=3.0` - Alert when 3x baseline
- **History**: 12 snapshots required (6 hours at 30-min intervals)
- **Duplicate window**: 2 hours - Won't re-alert same market

## Database Schema

### markets
Stores market metadata from Polymarket.

| Column | Type | Description |
|--------|------|-------------|
| market_id | VARCHAR(255) | Primary key |
| question | TEXT | Market question |
| slug | VARCHAR(255) | URL-friendly identifier |
| outcomes | TEXT | JSON array of outcomes |
| clob_token_ids | TEXT | JSON array of token IDs |

### market_snapshots
Time-series data collected every 30 minutes.

| Column | Type | Description |
|--------|------|-------------|
| market_id | VARCHAR(255) | Foreign key |
| timestamp | TIMESTAMP | Collection time |
| yes_price | DECIMAL(5,4) | Implied probability |
| orderbook_bid_depth | DECIMAL(18,2) | Total bid liquidity |
| orderbook_ask_depth | DECIMAL(18,2) | Total ask liquidity |

### spike_alerts
Records of detected spikes.

| Column | Type | Description |
|--------|------|-------------|
| market_id | VARCHAR(255) | Foreign key |
| detected_at | TIMESTAMP | Detection time |
| metric_type | VARCHAR(50) | bid_depth or ask_depth |
| spike_ratio | DECIMAL(6,2) | Current / baseline |
| baseline_value | DECIMAL(18,2) | Historical average |
| current_value | DECIMAL(18,2) | Current value |

## Troubleshooting

### No Data Being Collected

1. Check logs: `tail -50 logs/collector.log`
2. Test APIs: `python test_api.py`
3. Test database: `python -c "from database import get_connection; get_connection()"`
4. Run manually: `python collector.py`

### Discord Alerts Not Sending

1. Check webhook URL in `.env`
2. Test webhook: `python notifier.py`
3. Check for errors in logs
4. Verify Discord channel permissions

### No Spikes Detected

This is normal! Spikes are rare events. The system needs:
- 6+ hours of data collection (12 snapshots per market)
- Actual market volatility to occur
- Sufficient orderbook activity (>$100 depth)

### Database Connection Errors

1. Verify MySQL is running
2. Check credentials in `.env`
3. Ensure remote connections allowed (if using remote DB)
4. Test: `mysql -h HOST -u USER -p DATABASE_NAME`

## Maintenance

### Stop Automation

**Windows:**
```powershell
Disable-ScheduledTask -TaskName "PolymarketMonitor"
```

**Linux:**
```bash
crontab -l | grep -v collector.py | crontab -
```

### Clear Data

```bash
# Run automatic cleanup
python database.py cleanup

# Or manually via MySQL
mysql -u user -p polymarket_monitor
DELETE FROM market_snapshots WHERE timestamp < DATE_SUB(NOW(), INTERVAL 30 DAY);
DELETE FROM spike_alerts WHERE detected_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
```

### Update Detection Threshold

Edit `.env`:
```
SPIKE_THRESHOLD_RATIO=2.5
```

Lower = more sensitive (more alerts)
Higher = less sensitive (fewer alerts)

## API Reference

### Polymarket APIs Used

- **Gamma API**: `https://gamma-api.polymarket.com/events`
  - Market discovery, event data, current prices

- **CLOB API**: `https://clob.polymarket.com/book`
  - Orderbook depth (bid/ask liquidity)

### Rate Limits

- 0.3 second delay between CLOB API calls
- ~300 active markets processed per run
- ~5-8 minutes per collection cycle

## License

MIT License - Use at your own risk. This tool is for informational purposes only and does not constitute financial advice.
