"""
Configuration management for Polymarket Monitor.
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Database Configuration
# =============================================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "polymarket_monitor")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

# =============================================================================
# Polymarket API Configuration
# =============================================================================

# Gamma API - Market discovery and event data
GAMMA_API_BASE = os.getenv("GAMMA_API_BASE", "https://gamma-api.polymarket.com")

# CLOB API - Orderbook and price data
CLOB_API_BASE = os.getenv("CLOB_API_BASE", "https://clob.polymarket.com")

# =============================================================================
# API Rate Limiting
# =============================================================================

# Delay between CLOB API calls (seconds)
# Polymarket CLOB API can be sensitive to rapid requests
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "0.3"))

# Request timeout (seconds)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Maximum events to fetch per collection run
# Note: Each event can have multiple markets. 50 events typically yields 100-300 active markets
MAX_EVENTS_PER_FETCH = int(os.getenv("MAX_EVENTS_PER_FETCH", "50"))

# =============================================================================
# Polling Configuration
# =============================================================================

# How often to run collection (minutes) - used if running as daemon
POLLING_INTERVAL_MINUTES = int(os.getenv("POLLING_INTERVAL_MINUTES", "30"))

# =============================================================================
# Discord Webhook (for Part 2 - spike alerts)
# =============================================================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# =============================================================================
# Spike Detection Configuration (for Part 2)
# =============================================================================

# Minimum spike ratio to trigger alert (e.g., 3.0 = 3x baseline)
SPIKE_THRESHOLD_RATIO = float(os.getenv("SPIKE_THRESHOLD_RATIO", "3.0"))

# Hours of historical data to use for baseline calculation
BASELINE_HOURS = int(os.getenv("BASELINE_HOURS", "24"))

# Minimum orderbook depth to consider (filter out low-liquidity markets)
MIN_ORDERBOOK_DEPTH = float(os.getenv("MIN_ORDERBOOK_DEPTH", "500.0"))

# =============================================================================
# Data Retention / Cleanup
# =============================================================================

# Days to retain snapshot data (older data is deleted)
SNAPSHOT_RETENTION_DAYS = int(os.getenv("SNAPSHOT_RETENTION_DAYS", "7"))

# Days to retain alert records
ALERT_RETENTION_DAYS = int(os.getenv("ALERT_RETENTION_DAYS", "30"))

# Days of inactivity before removing a market from tracking
MARKET_RETENTION_DAYS = int(os.getenv("MARKET_RETENTION_DAYS", "30"))

# =============================================================================
# Logging Configuration
# =============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "")  # Empty = console only


def print_config():
    """Print current configuration (for debugging). Masks sensitive values."""
    print("=" * 60)
    print("Polymarket Monitor Configuration")
    print("=" * 60)
    print(f"DB_HOST: {DB_HOST}")
    print(f"DB_USER: {DB_USER}")
    print(f"DB_PASSWORD: {'*' * len(DB_PASSWORD) if DB_PASSWORD else '(not set)'}")
    print(f"DB_NAME: {DB_NAME}")
    print(f"DB_PORT: {DB_PORT}")
    print("-" * 60)
    print(f"GAMMA_API_BASE: {GAMMA_API_BASE}")
    print(f"CLOB_API_BASE: {CLOB_API_BASE}")
    print("-" * 60)
    print(f"RATE_LIMIT_DELAY: {RATE_LIMIT_DELAY}s")
    print(f"REQUEST_TIMEOUT: {REQUEST_TIMEOUT}s")
    print(f"MAX_EVENTS_PER_FETCH: {MAX_EVENTS_PER_FETCH}")
    print(f"POLLING_INTERVAL_MINUTES: {POLLING_INTERVAL_MINUTES}")
    print("-" * 60)
    print(f"DISCORD_WEBHOOK_URL: {'(set)' if DISCORD_WEBHOOK_URL else '(not set)'}")
    print(f"SPIKE_THRESHOLD_RATIO: {SPIKE_THRESHOLD_RATIO}")
    print(f"BASELINE_HOURS: {BASELINE_HOURS}")
    print(f"MIN_ORDERBOOK_DEPTH: {MIN_ORDERBOOK_DEPTH}")
    print("-" * 60)
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print(f"LOG_FILE: {LOG_FILE if LOG_FILE else '(console only)'}")
    print("=" * 60)


if __name__ == "__main__":
    print_config()
