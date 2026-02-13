"""
Configuration management for Macro Scanner.
Loads settings from tool-local .env file with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from tool-local .env file
_env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(_env_path)

# =============================================================================
# Database Configuration
# =============================================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "macro_scanner")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

# =============================================================================
# Perplexity API (fallback for automated cron when no Comet scan available)
# =============================================================================

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar")

# =============================================================================
# Claude API Configuration
# =============================================================================

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# =============================================================================
# Discord Configuration
# =============================================================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# =============================================================================
# Timeouts
# =============================================================================

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# =============================================================================
# Data Retention / Cleanup
# =============================================================================

SCAN_RETENTION_DAYS = int(os.getenv("SCAN_RETENTION_DAYS", "30"))
ALERT_RETENTION_DAYS = int(os.getenv("ALERT_RETENTION_DAYS", "90"))

# =============================================================================
# Deep-Dive Queue
# =============================================================================

DEEP_RESEARCH_THRESHOLD = int(os.getenv("DEEP_RESEARCH_THRESHOLD", "8"))
DEEP_RESEARCH_TIMEOUT = int(os.getenv("DEEP_RESEARCH_TIMEOUT", "180"))
DEEP_DIVE_EXPIRY_HOURS = int(os.getenv("DEEP_DIVE_EXPIRY_HOURS", "48"))

# =============================================================================
# Logging Configuration
# =============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def print_config():
    """Print current configuration (for debugging). Masks sensitive values."""
    print("=" * 60)
    print("Macro Scanner Configuration")
    print("=" * 60)
    print(f"DB_HOST: {DB_HOST}")
    print(f"DB_USER: {DB_USER}")
    print(f"DB_PASSWORD: {'*' * len(DB_PASSWORD) if DB_PASSWORD else '(not set)'}")
    print(f"DB_NAME: {DB_NAME}")
    print(f"DB_PORT: {DB_PORT}")
    print("-" * 60)
    print(f"PERPLEXITY_API_KEY: {'(set)' if PERPLEXITY_API_KEY else '(not set)'}")
    print(f"PERPLEXITY_MODEL: {PERPLEXITY_MODEL}")
    print("-" * 60)
    print(f"CLAUDE_API_KEY: {'(set)' if CLAUDE_API_KEY else '(not set)'}")
    print(f"CLAUDE_MODEL: {CLAUDE_MODEL}")
    print("-" * 60)
    print(f"DISCORD_WEBHOOK_URL: {'(set)' if DISCORD_WEBHOOK_URL else '(not set)'}")
    print("-" * 60)
    print(f"REQUEST_TIMEOUT: {REQUEST_TIMEOUT}s")
    print(f"SCAN_RETENTION_DAYS: {SCAN_RETENTION_DAYS}")
    print(f"ALERT_RETENTION_DAYS: {ALERT_RETENTION_DAYS}")
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print("-" * 60)
    print(f"DEEP_RESEARCH_THRESHOLD: {DEEP_RESEARCH_THRESHOLD}")
    print(f"DEEP_RESEARCH_TIMEOUT: {DEEP_RESEARCH_TIMEOUT}s")
    print(f"DEEP_DIVE_EXPIRY_HOURS: {DEEP_DIVE_EXPIRY_HOURS}h")
    print("=" * 60)


if __name__ == "__main__":
    print_config()
