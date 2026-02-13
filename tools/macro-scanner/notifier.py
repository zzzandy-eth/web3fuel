"""
Discord notification module for Macro Scanner.
Sends rich embed alerts with macro analysis and trade ideas.
"""

import logging
from datetime import datetime, timezone
from collections import OrderedDict

import requests

from config import DISCORD_WEBHOOK_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Discord embed color codes by confidence level
CONFIDENCE_COLORS = {
    5: 16711680,    # #FF0000 - Red (high conviction)
    4: 16744448,    # #FF8C00 - Orange
    3: 16776960,    # #FFFF00 - Yellow
    2: 3447003,     # #3498DB - Blue
    1: 9807270,     # #95A5A6 - Grey (speculative)
}

COLOR_SUCCESS_GREEN = 65280  # #00FF00

# Direction emojis
DIRECTION_EMOJI = {
    "bullish": "\U0001f7e2",   # green circle
    "bearish": "\U0001f534",   # red circle
    "mixed": "\U0001f7e1",     # yellow circle
}

# In-memory dedup cache
_recent_notifications = OrderedDict()
_DEDUP_WINDOW_SECONDS = 300  # 5 minute window
_MAX_CACHE_SIZE = 50


def _check_dedup(cache_key):
    """
    Check if a notification was recently sent. Returns True if duplicate.
    """
    global _recent_notifications
    now = datetime.now().timestamp()

    # Clean old entries
    cutoff = now - _DEDUP_WINDOW_SECONDS
    keys_to_remove = [k for k, v in _recent_notifications.items() if v < cutoff]
    for k in keys_to_remove:
        del _recent_notifications[k]

    while len(_recent_notifications) > _MAX_CACHE_SIZE:
        _recent_notifications.popitem(last=False)

    if cache_key in _recent_notifications:
        return True

    _recent_notifications[cache_key] = now
    return False


def send_macro_alert(analysis, indicators=None):
    """
    Send a succinct macro trade alert to Discord.

    Only sends if confidence >= 2 (skip noise). One embed per scan with:
    - Narrative (1-2 sentences)
    - Trade setup: tickers, entry, target, stop, timeline

    Args:
        analysis: Dict with narrative, trade, confidence, market_regime
        indicators: Unused (kept for interface compatibility)

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured - skipping notification")
        return False

    if not analysis:
        logger.warning("No analysis data to send")
        return False

    confidence = analysis.get('confidence', 0)

    # Only notify if there's a real trade worth taking
    if confidence < 2:
        logger.info(f"Confidence {confidence}/5 too low for notification — skipping")
        return True  # Not an error, just nothing worth alerting

    # Dedup check based on narrative hash
    narrative = analysis.get('narrative', '')
    dedup_key = f"macro:{hash(narrative)}"
    if _check_dedup(dedup_key):
        logger.info("Duplicate macro notification suppressed")
        return True

    try:
        color = CONFIDENCE_COLORS.get(confidence, CONFIDENCE_COLORS[1])
        now = datetime.now(timezone.utc)
        timestamp_display = now.strftime("%Y-%m-%d %H:%M UTC")

        # Build trade setup field
        trade = analysis.get('trade', {})
        fields = []

        if trade and trade.get('tickers'):
            direction = trade.get('direction', 'long').upper()
            tickers = ', '.join(trade.get('tickers', []))
            regime = analysis.get('market_regime', 'neutral').upper()

            # Direction emoji
            dir_emoji = "\U0001f7e2" if direction == "LONG" else "\U0001f534"

            # Sector impact line
            sector_impact = analysis.get('sector_impact', '')

            # Trade setup
            setup_lines = [f"{dir_emoji} **{direction} {tickers}**"]

            if sector_impact:
                setup_lines.append(f"Sector: {sector_impact}")

            thesis = trade.get('thesis', '')
            if thesis:
                setup_lines.append(thesis)

            entry = trade.get('entry', '')
            target = trade.get('target', '')
            stop = trade.get('stop_loss', '')
            timeline = trade.get('timeline', '')

            if entry:
                setup_lines.append(f"Entry: {entry}")
            if target:
                setup_lines.append(f"Target: {target}")
            if stop:
                setup_lines.append(f"Stop: {stop}")
            if timeline:
                setup_lines.append(f"Timeline: {timeline}")

            position_note = trade.get('position_note', '')
            if position_note:
                setup_lines.append(f"_{position_note}_")

            fields.append({
                "name": f"\U0001f4b0 Trade Setup | Regime: {regime}",
                "value": '\n'.join(setup_lines)[:1024],
                "inline": False
            })

        embed = {
            "title": f"\U0001f3db\ufe0f {narrative[:200]}",
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"Macro Scanner \u2022 Conf {confidence}/5 \u2022 {timestamp_display}"
            },
            "timestamp": now.isoformat()
        }

        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            logger.info(f"Macro alert sent to Discord (confidence: {confidence}/5)")
            return True
        elif response.status_code == 429:
            logger.warning(f"Discord rate limited. Retry after: {response.headers.get('Retry-After', 'unknown')}s")
            return False
        else:
            logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error("Discord webhook timed out")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord webhook error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending macro alert: {e}")
        return False


COLOR_DEEP_DIVE_PURPLE = 0x9B59B6


def send_deep_dive_alert(results):
    """
    Send a deep-dive research report to Discord as a purple embed.

    Args:
        results: List of dicts with keys: headline, deep_research

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured - skipping deep-dive notification")
        return False

    if not results:
        logger.warning("No deep-dive results to send")
        return False

    try:
        now = datetime.now(timezone.utc)
        timestamp_display = now.strftime("%Y-%m-%d %H:%M UTC")

        fields = []
        for item in results[:5]:  # Max 5 to stay within embed limits
            headline = item.get('headline', 'Unknown')
            research = item.get('deep_research', 'No research available')
            # Truncate research to fit Discord field limit
            if len(research) > 900:
                research = research[:900] + "..."

            fields.append({
                "name": f"\U0001f52c {headline}",
                "value": research[:1024],
                "inline": False
            })

        embed = {
            "title": "\U0001f52d Deep Dive Research Report",
            "color": COLOR_DEEP_DIVE_PURPLE,
            "fields": fields,
            "footer": {
                "text": f"Deep Dive \u2022 {len(results)} topic{'s' if len(results) != 1 else ''} \u2022 {timestamp_display}"
            },
            "timestamp": now.isoformat()
        }

        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            logger.info(f"Deep-dive alert sent to Discord ({len(results)} topics)")
            return True
        elif response.status_code == 429:
            logger.warning(f"Discord rate limited. Retry after: {response.headers.get('Retry-After', 'unknown')}s")
            return False
        else:
            logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error("Discord webhook timed out")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord webhook error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending deep-dive alert: {e}")
        return False


def send_test_notification():
    """
    Send a test notification to verify webhook configuration.

    Returns:
        True if successful, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL not configured in .env file")
        return False

    embed = {
        "title": "\u2705 Macro Scanner - Test Notification",
        "description": (
            "**This is a test notification.**\n\n"
            "If you see this, your Discord webhook is configured correctly!\n"
            "The scanner will send macro alerts every 6 hours."
        ),
        "color": COLOR_SUCCESS_GREEN,
        "fields": [
            {
                "name": "1. Sample Story",
                "value": "\U0001f7e2 **BULLISH** | tech, financials\nFed signals dovish pivot",
                "inline": False
            },
            {
                "name": "\U0001f4ca Market Tape",
                "value": "DXY: 104.52 (+0.3%) | VIX: 18.2 (-2.1%) | SPY: 502.30 (+0.8%)",
                "inline": False
            },
            {
                "name": "\U0001f4b0 Trade Idea",
                "value": "CONFIDENCE: 3/5 - This is a test trade idea.",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Macro Scanner \u2022 TEST \u2022 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {"embeds": [embed]}

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            print("[SUCCESS] Test notification sent to Discord!")
            return True
        else:
            print(f"[ERROR] Discord webhook failed: {response.status_code}")
            print(f"        Response: {response.text}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to send test notification: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Macro Scanner - Discord Webhook Test")
    print("=" * 60)

    if not DISCORD_WEBHOOK_URL:
        print("\n[ERROR] DISCORD_WEBHOOK_URL is not set!")
        print("        Add it to your .env file")
    else:
        print(f"\nWebhook URL configured: {DISCORD_WEBHOOK_URL[:50]}...")
        print("\nSending test notification...")
        success = send_test_notification()

        if success:
            print("\n[OK] Discord integration is working!")
        else:
            print("\n[FAIL] Discord integration failed. Check the errors above.")
