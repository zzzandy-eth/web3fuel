"""
Discord notification module for Polymarket Monitor.
Sends rich embed alerts when spikes are detected.
"""

import json
import logging
from datetime import datetime, timezone
from collections import OrderedDict

import requests

from config import DISCORD_WEBHOOK_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Discord embed color codes
COLOR_ALERT_RED = 16711680      # #FF0000 - for spikes/alerts (A+ grade)
COLOR_WARNING_ORANGE = 16744448  # #FF8C00 - for warnings (A grade)
COLOR_SUCCESS_GREEN = 65280      # #00FF00 - for success/test
COLOR_INFO_BLUE = 3447003        # #3498DB - for info (B+ grade)
COLOR_PURPLE = 10181046          # #9B59B6 - for correlation/arbitrage
COLOR_GREY = 9807270             # #95A5A6 - for B/C grades

# Simple in-memory deduplication cache to prevent double-sends
# Key: "market_id:metric_type", Value: timestamp
_recent_notifications = OrderedDict()
_DEDUP_WINDOW_SECONDS = 60  # Don't send same notification within 60 seconds
_MAX_CACHE_SIZE = 100


def format_currency(value):
    """
    Format a number as currency string.

    Args:
        value: Number to format (int, float, or None)

    Returns:
        Formatted string like "$1,234.56" or "N/A" if None
    """
    if value is None:
        return "N/A"

    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def format_percentage(value):
    """
    Format a decimal as percentage.

    Args:
        value: Decimal value (0.0 to 1.0) or percentage

    Returns:
        Formatted string like "65.5%"
    """
    if value is None:
        return "N/A"

    try:
        # If value is already > 1, assume it's already a percentage
        if value > 1:
            return f"{value:.1f}%"
        # Otherwise convert from decimal
        return f"{value * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def format_metric_name(metric):
    """
    Convert metric column name to human-readable format.

    Args:
        metric: Column name like 'orderbook_bid_depth'

    Returns:
        Human-readable string like 'Bid Depth'
    """
    mapping = {
        'orderbook_bid_depth': 'Bid Depth',
        'orderbook_ask_depth': 'Ask Depth',
        'yes_price': 'Yes Price',
        'no_price': 'No Price',
        'price_momentum': 'Price Momentum',
        'contrarian_whale': 'Contrarian Whale'
    }
    return mapping.get(metric, metric)


def get_pattern_confidence(metric_type):
    """
    Get historical accuracy/confidence for a spike type.
    Returns cached value or fetches from patterns module.

    Args:
        metric_type: The type of spike

    Returns:
        Tuple of (accuracy_pct, sample_count) or (None, None) if unavailable
    """
    try:
        # Try to import and get pattern stats
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))

        from patterns import get_spike_history, get_market_outcomes_from_db, analyze_spike_accuracy

        spikes = get_spike_history(days=30)
        outcomes = get_market_outcomes_from_db()

        if not spikes:
            return None, None

        stats = analyze_spike_accuracy(spikes, outcomes)
        type_stats = stats.get('by_type', {}).get(metric_type, {})

        if type_stats.get('total', 0) >= 5:  # Minimum samples
            accuracy = type_stats['correct'] / type_stats['total'] * 100
            return round(accuracy, 0), type_stats['total']

        return None, None

    except Exception:
        return None, None


def format_confidence_text(accuracy, samples):
    """
    Format confidence score for Discord display.

    Args:
        accuracy: Accuracy percentage
        samples: Number of samples

    Returns:
        Formatted string with emoji
    """
    if accuracy is None:
        return None

    if accuracy >= 70:
        emoji = "🟢"
        label = "High"
    elif accuracy >= 50:
        emoji = "🟡"
        label = "Medium"
    else:
        emoji = "🔴"
        label = "Low"

    return f"{emoji} {label} ({accuracy:.0f}% on {samples} samples)"


def format_signal_quality(signal_quality):
    """
    Format signal quality score for Discord display.

    Args:
        signal_quality: Dict with score, rating, emoji, factors

    Returns:
        Formatted string
    """
    if not signal_quality or signal_quality.get('score') is None:
        return None

    score = signal_quality.get('score', 0)
    rating = signal_quality.get('rating', 'unknown')
    emoji = signal_quality.get('emoji', '⚪')

    return f"{emoji} **{score:.0f}/100** ({rating.title()})"


def format_indicators_text(spike_data):
    """
    Format statistical indicators for Discord display.

    Args:
        spike_data: Dict with indicator data

    Returns:
        Formatted string or None
    """
    lines = []

    # Z-Score
    zscore = spike_data.get('zscore', {})
    if zscore.get('zscore') is not None:
        z = zscore['zscore']
        sig = zscore.get('significance', '')
        if sig in ['extreme', 'highly_significant']:
            lines.append(f"📊 Z-Score: **{z}σ** ({sig.replace('_', ' ')})")

    # Imbalance
    imbalance = spike_data.get('imbalance', {})
    if imbalance.get('strength') in ['strong', 'extreme']:
        ratio = imbalance.get('display_ratio', 0)
        direction = imbalance.get('direction', '')
        lines.append(f"⚖️ Imbalance: **{ratio}:1** {direction}")

    # RSI
    rsi = spike_data.get('rsi', {})
    if rsi.get('condition') in ['overbought', 'oversold']:
        lines.append(f"📈 RSI: **{rsi.get('rsi')}** ({rsi.get('condition')})")

    # Bollinger
    bollinger = spike_data.get('bollinger', {})
    if bollinger.get('breakout'):
        lines.append(f"📉 Bollinger: **{bollinger.get('breakout').replace('_', ' ').title()}**")

    if lines:
        return "\n".join(lines)
    return None


def _grade_color(grade):
    """Return Discord embed color for an AI grade."""
    colors = {
        'A+': COLOR_ALERT_RED,
        'A': COLOR_WARNING_ORANGE,
        'B+': COLOR_INFO_BLUE,
        'B': COLOR_GREY,
        'C': COLOR_GREY,
    }
    return colors.get(grade, COLOR_INFO_BLUE)


def _grade_label(grade):
    """Return human-readable label for a grade."""
    labels = {
        'A+': 'High Conviction',
        'A': 'Strong Setup',
        'B+': 'Moderate-High',
        'B': 'Moderate',
        'C': 'Speculative',
    }
    return labels.get(grade, 'Unknown')


def _signal_icon(sig_type):
    """Return emoji for a signal type."""
    icons = {
        'orderbook_bid_depth': '\U0001f7e2',  # green circle
        'orderbook_ask_depth': '\U0001f534',   # red circle
        'price_momentum': '\U0001f4c8',        # chart increasing
        'contrarian_whale': '\U0001f40b',      # whale
    }
    return icons.get(sig_type, '\U0001f4ca')


def create_unified_embed(unified_alert):
    """
    Create a Discord embed for a unified alert with AI trade suggestion.

    Args:
        unified_alert: Dict with keys: question, market_id, slug, yes_price, no_price,
                      end_date, signals (list), ai_suggestion (dict with play/grade/reasoning/key_signal),
                      signal_quality (dict), detected_at

    Returns:
        Dict formatted as Discord embed
    """
    question = unified_alert.get('question', 'Unknown Market')
    slug = unified_alert.get('slug', '')
    yes_price = unified_alert.get('yes_price')
    no_price = unified_alert.get('no_price')
    end_date = unified_alert.get('end_date')
    signals = unified_alert.get('signals', [])
    ai = unified_alert.get('ai_suggestion') or {}
    signal_quality = unified_alert.get('signal_quality', {})
    detected_at = unified_alert.get('detected_at', datetime.now())

    grade = ai.get('grade', 'C')
    play = ai.get('play', 'NO TRADE')
    reasoning = ai.get('reasoning', '')
    key_signal = ai.get('key_signal', '')

    market_url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

    # Timestamp
    if isinstance(detected_at, datetime):
        timestamp_iso = detected_at.replace(tzinfo=timezone.utc).isoformat()
        timestamp_display = detected_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        timestamp_display = str(detected_at)

    # Color by grade
    color = _grade_color(grade)

    # Title
    title = f"\U0001f3af POLYMARKET SIGNAL: {grade} Setup"

    # Build signal list text with tree formatting
    signal_count = len(signals)
    signal_lines = []
    for i, sig in enumerate(signals):
        connector = "\u2514\u2500" if i == signal_count - 1 else "\u251c\u2500"
        icon = _signal_icon(sig.get('type', ''))
        sig_type = sig.get('type', 'unknown')

        if sig_type in ('orderbook_bid_depth', 'orderbook_ask_depth'):
            side = 'Bid' if 'bid' in sig_type else 'Ask'
            line = (f"{connector} {icon} {side} Spike: {sig.get('ratio', 0):.1f}x baseline "
                    f"(${sig.get('baseline', 0):,.0f} \u2192 ${sig.get('current', 0):,.0f})")
        elif sig_type == 'price_momentum':
            direction = sig.get('direction', 'up')
            change = sig.get('ratio', 0) * 100
            line = (f"{connector} {icon} Price Momentum: "
                    f"{'+' if direction == 'up' else '-'}{change:.1f}pp "
                    f"({sig.get('baseline', 0)*100:.1f}% \u2192 {sig.get('current', 0)*100:.1f}%)")
        elif sig_type == 'contrarian_whale':
            side = sig.get('contrarian_side', '?')
            line = f"{connector} {icon} Contrarian Whale: {sig.get('ratio', 0):.1f}x influx on {side}"
        else:
            line = f"{connector} {icon} {sig_type}: {sig.get('ratio', 0):.1f}x"

        signal_lines.append(line)

    signals_text = "\n".join(signal_lines) if signal_lines else "No specific signals"

    # Format end date
    end_date_text = "Unknown"
    days_remaining = ""
    if end_date:
        try:
            if hasattr(end_date, 'strftime'):
                end_date_text = end_date.strftime("%b %d, %Y")
                remaining = (end_date - datetime.now()).days
                if remaining > 0:
                    days_remaining = f" ({remaining} days)"
                elif remaining == 0:
                    days_remaining = " (Today!)"
            else:
                end_date_text = str(end_date)
        except Exception:
            end_date_text = str(end_date) if end_date else "Unknown"

    # Format prices
    yes_pct = f"{yes_price*100:.1f}%" if yes_price is not None else "N/A"

    # Signal quality
    quality_score = signal_quality.get('score', 0) if signal_quality else 0
    quality_rating = signal_quality.get('rating', 'unknown') if signal_quality else 'unknown'

    # AI suggestion text
    ai_text = f"**{play}** ({grade} {_grade_label(grade)})\n{reasoning}" if reasoning else f"**{play}** ({grade})"

    # Build fields
    fields = [
        {
            "name": "\U0001f916 AI Suggestion",
            "value": ai_text[:1024],
            "inline": False
        },
        {
            "name": f"\U0001f4ca Detected Signals ({signal_count})",
            "value": signals_text[:1024],
            "inline": False
        },
        {
            "name": "\u23f0 Market Ends",
            "value": f"{end_date_text}{days_remaining}",
            "inline": True
        },
        {
            "name": "\U0001f4c8 Current",
            "value": f"{yes_pct} YES",
            "inline": True
        },
        {
            "name": "\U0001f3af Signal Quality",
            "value": f"{quality_score:.0f}/100 ({quality_rating.title()})",
            "inline": True
        },
        {
            "name": "\U0001f517 View on Polymarket",
            "value": f"[Open Market]({market_url})",
            "inline": True
        }
    ]

    embed = {
        "title": title,
        "description": f"**{question}**",
        "color": color,
        "url": market_url,
        "fields": fields,
        "footer": {
            "text": f"Polymarket Monitor \u2022 {grade} Grade \u2022 {timestamp_display}"
        },
        "timestamp": timestamp_iso
    }

    return embed


def send_unified_notification(unified_alert):
    """
    Send a unified alert to Discord.

    Args:
        unified_alert: Dict with unified alert data

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured - skipping notification")
        return False

    market_id = unified_alert.get('market_id', '')
    if _check_and_update_dedup_cache(market_id, 'unified'):
        logger.info(f"Duplicate unified notification suppressed for {market_id}")
        return True

    try:
        embed = create_unified_embed(unified_alert)
        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            logger.info(f"Unified Discord notification sent for market: {market_id}")
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
        logger.error(f"Unexpected error sending unified notification: {e}")
        return False


def create_spike_embed(spike_data):
    """
    Create a Discord embed object for a spike alert.

    Args:
        spike_data: Dict containing spike information from detector

    Returns:
        Dict formatted as Discord embed
    """
    # Extract data with defaults
    question = spike_data.get('question', 'Unknown Market')
    metric = spike_data.get('metric_type', 'unknown')
    spike_ratio = spike_data.get('spike_ratio', 0)
    baseline = spike_data.get('baseline_value', 0)
    current = spike_data.get('current_value', 0)
    yes_price = spike_data.get('yes_price')
    no_price = spike_data.get('no_price')
    slug = spike_data.get('slug', '')
    detected_at = spike_data.get('detected_at', datetime.now())
    direction = spike_data.get('direction')  # For price momentum alerts
    ai_analysis = spike_data.get('ai_analysis')  # AI context analysis

    # Statistical indicators
    signal_quality = spike_data.get('signal_quality', {})
    zscore_data = spike_data.get('zscore', {})
    imbalance_data = spike_data.get('imbalance', {})
    rsi_data = spike_data.get('rsi', {})
    bollinger_data = spike_data.get('bollinger', {})

    # Build market URL
    market_url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

    # Format timestamp for Discord
    if isinstance(detected_at, datetime):
        timestamp_iso = detected_at.replace(tzinfo=timezone.utc).isoformat()
        timestamp_display = detected_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        timestamp_display = str(detected_at)

    # Get confidence score based on historical accuracy
    confidence_accuracy, confidence_samples = get_pattern_confidence(metric)
    confidence_text = format_confidence_text(confidence_accuracy, confidence_samples)

    # Check if this is a contrarian whale alert
    is_contrarian = metric == 'contrarian_whale'
    # Check if this is a price momentum alert
    is_momentum = metric == 'price_momentum'

    if is_contrarian:
        # Contrarian whale alert formatting
        contrarian_side = spike_data.get('contrarian_side', '?')
        influx_ratio = spike_data.get('influx_ratio', spike_ratio)
        prior_ratio = spike_data.get('prior_ratio', 0)
        dominant_side = spike_data.get('dominant_side', '?')
        dominance_flipped = spike_data.get('dominance_flipped', False)
        baseline_bid = spike_data.get('baseline_bid', 0)
        baseline_ask = spike_data.get('baseline_ask', 0)
        current_bid = spike_data.get('current_bid', 0)
        current_ask = spike_data.get('current_ask', 0)
        baseline_price_val = spike_data.get('baseline_price', baseline)
        current_price_val = spike_data.get('current_price', current)
        price_shift = spike_data.get('price_shift', 0)
        timeframe = spike_data.get('timeframe_hours', 2.5)

        bl_pct = (baseline_price_val or 0) * 100
        cur_pct = (current_price_val or 0) * 100
        shift_pp = (price_shift or 0) * 100

        if dominance_flipped:
            title = "CONTRARIAN WHALE: Market Flipped!"
            color = COLOR_ALERT_RED
        else:
            title = "Contrarian Whale Activity Detected"
            color = COLOR_WARNING_ORANGE

        status_text = "FLIPPED majority" if dominance_flipped else "growing"
        prior_dominant_label = "BID(YES)" if dominant_side == 'bid' else "ASK(NO)"

        embed = {
            "title": title,
            "description": f"**{question}**",
            "color": color,
            "url": market_url,
            "fields": [
                {
                    "name": "Contrarian Side",
                    "value": f"**{contrarian_side}** ({status_text})",
                    "inline": True
                },
                {
                    "name": "Influx Ratio",
                    "value": f"**{influx_ratio:.1f}x** on {contrarian_side}",
                    "inline": True
                },
                {
                    "name": "Prior Balance",
                    "value": f"Bid(YES) ${baseline_bid:,.0f} / Ask(NO) ${baseline_ask:,.0f}\n({prior_ratio:.1f}:1 favoring {prior_dominant_label})",
                    "inline": False
                },
                {
                    "name": "Current Balance",
                    "value": f"Bid(YES) ${current_bid:,.0f} / Ask(NO) ${current_ask:,.0f}",
                    "inline": False
                },
                {
                    "name": "Price Impact",
                    "value": f"{bl_pct:.1f}% -> **{cur_pct:.1f}%** ({'+' if shift_pp > 0 else ''}{shift_pp:.1f}pp)",
                    "inline": True
                },
                {
                    "name": "Timeframe",
                    "value": f"{timeframe:.1f} hours",
                    "inline": True
                },
                {
                    "name": "Market Link",
                    "value": f"[View on Polymarket]({market_url})",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Polymarket Monitor \u2022 Contrarian Whale \u2022 {timestamp_display}"
            },
            "timestamp": timestamp_iso
        }

        # Add signal quality score
        signal_quality_text = format_signal_quality(signal_quality)
        if signal_quality_text:
            embed["fields"].insert(0, {
                "name": "Signal Quality",
                "value": signal_quality_text,
                "inline": True
            })

        # Add confidence score if available
        if confidence_text:
            embed["fields"].insert(1, {
                "name": "Historical Accuracy",
                "value": confidence_text,
                "inline": True
            })

        # Add AI analysis if available
        if ai_analysis:
            embed["fields"].append({
                "name": "AI Analysis",
                "value": ai_analysis[:1024],
                "inline": False
            })

    elif is_momentum:
        # Price momentum alert formatting
        change_pct = spike_ratio * 100  # spike_ratio holds the price change for momentum
        baseline_pct = baseline * 100 if baseline else 0
        current_pct = current * 100 if current else 0

        # Determine title and color based on direction and magnitude
        if direction == 'up':
            if change_pct >= 15:
                title = "🚀 MAJOR Price Surge Detected"
                color = COLOR_ALERT_RED
            else:
                title = "📈 Price Momentum Detected (UP)"
                color = COLOR_SUCCESS_GREEN
            direction_text = f"⬆️ UP +{change_pct:.1f}pp"
        else:
            if change_pct >= 15:
                title = "💥 MAJOR Price Drop Detected"
                color = COLOR_ALERT_RED
            else:
                title = "📉 Price Momentum Detected (DOWN)"
                color = COLOR_WARNING_ORANGE
            direction_text = f"⬇️ DOWN -{change_pct:.1f}pp"

        embed = {
            "title": title,
            "description": f"**{question}**",
            "color": color,
            "url": market_url,
            "fields": [
                {
                    "name": "📊 Signal Type",
                    "value": "Price Momentum",
                    "inline": True
                },
                {
                    "name": "🎯 Direction",
                    "value": direction_text,
                    "inline": True
                },
                {
                    "name": "📉 Baseline (3hr avg)",
                    "value": f"{baseline_pct:.1f}%",
                    "inline": True
                },
                {
                    "name": "📈 Current Odds",
                    "value": f"{current_pct:.1f}% Yes",
                    "inline": True
                },
                {
                    "name": "⚡ Change",
                    "value": f"**{'+' if direction == 'up' else '-'}{change_pct:.1f}** percentage points",
                    "inline": True
                },
                {
                    "name": "🔗 Market Link",
                    "value": f"[View on Polymarket]({market_url})",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Polymarket Monitor • Price Momentum • {timestamp_display}"
            },
            "timestamp": timestamp_iso
        }

        # Add signal quality score
        signal_quality_text = format_signal_quality(signal_quality)
        if signal_quality_text:
            embed["fields"].insert(0, {
                "name": "🎯 Signal Quality",
                "value": signal_quality_text,
                "inline": True
            })

        # Add confidence score if available
        if confidence_text:
            embed["fields"].insert(1, {
                "name": "📊 Historical Accuracy",
                "value": confidence_text,
                "inline": True
            })

        # Add statistical indicators
        indicators_text = format_indicators_text(spike_data)
        if indicators_text:
            embed["fields"].append({
                "name": "📐 Technical Indicators",
                "value": indicators_text,
                "inline": False
            })

        # Add AI analysis if available
        if ai_analysis:
            embed["fields"].append({
                "name": "🤖 AI Analysis",
                "value": ai_analysis[:1024],  # Discord field limit
                "inline": False
            })
    else:
        # Orderbook spike alert formatting (original logic)
        # Format odds
        yes_pct = format_percentage(yes_price)
        no_pct = format_percentage(no_price)
        odds_text = f"{yes_pct} Yes / {no_pct} No"

        # Determine alert level based on spike ratio
        if spike_ratio >= 5.0:
            title = "🚨 MAJOR Orderbook Spike Detected"
            color = COLOR_ALERT_RED
        elif spike_ratio >= 3.0:
            title = "⚠️ Orderbook Spike Detected"
            color = COLOR_WARNING_ORANGE
        else:
            title = "📊 Orderbook Activity Alert"
            color = COLOR_INFO_BLUE

        embed = {
            "title": title,
            "description": f"**{question}**",
            "color": color,
            "url": market_url,
            "fields": [
                {
                    "name": "📈 Metric",
                    "value": format_metric_name(metric),
                    "inline": True
                },
                {
                    "name": "⚡ Spike Ratio",
                    "value": f"**{spike_ratio:.1f}x** baseline",
                    "inline": True
                },
                {
                    "name": "📊 Baseline (6hr avg)",
                    "value": format_currency(baseline),
                    "inline": True
                },
                {
                    "name": "💰 Current Value",
                    "value": format_currency(current),
                    "inline": True
                },
                {
                    "name": "🎯 Current Odds",
                    "value": odds_text,
                    "inline": True
                },
                {
                    "name": "🔗 Market Link",
                    "value": f"[View on Polymarket]({market_url})",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Polymarket Monitor • Orderbook Spike • {timestamp_display}"
            },
            "timestamp": timestamp_iso
        }

        # Add signal quality score
        signal_quality_text = format_signal_quality(signal_quality)
        if signal_quality_text:
            embed["fields"].insert(0, {
                "name": "🎯 Signal Quality",
                "value": signal_quality_text,
                "inline": True
            })

        # Add confidence score if available
        if confidence_text:
            embed["fields"].insert(1, {
                "name": "📊 Historical Accuracy",
                "value": confidence_text,
                "inline": True
            })

        # Add statistical indicators
        indicators_text = format_indicators_text(spike_data)
        if indicators_text:
            embed["fields"].append({
                "name": "📐 Technical Indicators",
                "value": indicators_text,
                "inline": False
            })

        # Add AI analysis if available
        if ai_analysis:
            embed["fields"].append({
                "name": "🤖 AI Analysis",
                "value": ai_analysis[:1024],  # Discord field limit
                "inline": False
            })

    return embed


def create_correlation_embed(divergence_data):
    """
    Create a Discord embed for a correlation/arbitrage alert.

    Args:
        divergence_data: Dict containing correlation divergence information

    Returns:
        Dict formatted as Discord embed
    """
    correlation_name = divergence_data.get('correlation_name', 'Unknown Correlation')
    correlation_type = divergence_data.get('correlation_type', 'positive')
    divergence = divergence_data.get('divergence', 0)
    arbitrage_signal = divergence_data.get('arbitrage_signal', '')
    detected_at = divergence_data.get('detected_at', datetime.now())

    market_a = divergence_data.get('market_a', {})
    market_b = divergence_data.get('market_b', {})

    # Format timestamp
    if isinstance(detected_at, datetime):
        timestamp_iso = detected_at.replace(tzinfo=timezone.utc).isoformat()
        timestamp_display = detected_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        timestamp_display = str(detected_at)

    # Build market URLs
    url_a = f"https://polymarket.com/event/{market_a.get('slug', '')}" if market_a.get('slug') else "https://polymarket.com"
    url_b = f"https://polymarket.com/event/{market_b.get('slug', '')}" if market_b.get('slug') else "https://polymarket.com"

    # Format price changes
    change_a = market_a.get('change', 0)
    change_b = market_b.get('change', 0)
    expected_b = market_b.get('expected_change', 0)

    change_a_str = f"{'+' if change_a > 0 else ''}{change_a*100:.1f}pp"
    change_b_str = f"{'+' if change_b > 0 else ''}{change_b*100:.1f}pp"
    expected_b_str = f"{'+' if expected_b > 0 else ''}{expected_b*100:.1f}pp"

    # Determine alert severity
    if divergence >= 0.20:
        title = "🚨 MAJOR Arbitrage Opportunity"
        color = COLOR_ALERT_RED
    elif divergence >= 0.15:
        title = "⚠️ Correlation Divergence Detected"
        color = COLOR_WARNING_ORANGE
    else:
        title = "🔗 Market Correlation Alert"
        color = COLOR_PURPLE

    # Truncate questions if too long
    question_a = market_a.get('question', 'Unknown')[:80]
    question_b = market_b.get('question', 'Unknown')[:80]
    if len(market_a.get('question', '')) > 80:
        question_a += "..."
    if len(market_b.get('question', '')) > 80:
        question_b += "..."

    embed = {
        "title": title,
        "description": f"**{correlation_name}** ({correlation_type.upper()} correlation)",
        "color": color,
        "fields": [
            {
                "name": "📊 Market A",
                "value": f"[{question_a}]({url_a})\n{market_a.get('baseline_price', 0)*100:.1f}% → **{market_a.get('current_price', 0)*100:.1f}%** ({change_a_str})",
                "inline": False
            },
            {
                "name": "📊 Market B",
                "value": f"[{question_b}]({url_b})\n{market_b.get('baseline_price', 0)*100:.1f}% → **{market_b.get('current_price', 0)*100:.1f}%** ({change_b_str})\nExpected: {expected_b_str}",
                "inline": False
            },
            {
                "name": "📏 Divergence",
                "value": f"**{divergence*100:.1f}** percentage points",
                "inline": True
            },
            {
                "name": "🔀 Correlation Type",
                "value": correlation_type.upper(),
                "inline": True
            },
            {
                "name": "💡 Arbitrage Signal",
                "value": arbitrage_signal or "Analysis pending",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Polymarket Monitor • Correlation Analysis • {timestamp_display}"
        },
        "timestamp": timestamp_iso
    }

    return embed


def send_correlation_notification(divergence_data):
    """
    Send a correlation/arbitrage alert to Discord.

    Args:
        divergence_data: Dict containing divergence information

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured")
        return False

    # Check for duplicate
    correlation_name = divergence_data.get('correlation_name', '')
    if _check_and_update_dedup_cache(correlation_name, 'correlation'):
        logger.info(f"Duplicate correlation notification suppressed for {correlation_name}")
        return True

    try:
        embed = create_correlation_embed(divergence_data)
        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            logger.info(f"Correlation notification sent: {correlation_name}")
            return True
        else:
            logger.error(f"Discord webhook failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error sending correlation notification: {e}")
        return False


def _check_and_update_dedup_cache(market_id, metric_type):
    """
    Check if we've recently sent a notification for this market/metric.
    Returns True if this is a duplicate (should skip), False if new.
    """
    global _recent_notifications

    cache_key = f"{market_id}:{metric_type}"
    now = datetime.now()

    # Clean old entries from cache
    cutoff = now.timestamp() - _DEDUP_WINDOW_SECONDS
    keys_to_remove = [k for k, v in _recent_notifications.items() if v < cutoff]
    for k in keys_to_remove:
        del _recent_notifications[k]

    # Trim cache size if needed
    while len(_recent_notifications) > _MAX_CACHE_SIZE:
        _recent_notifications.popitem(last=False)

    # Check if this is a duplicate
    if cache_key in _recent_notifications:
        logger.debug(f"Skipping duplicate notification for {cache_key}")
        return True

    # Mark as sent
    _recent_notifications[cache_key] = now.timestamp()
    return False


def send_discord_notification(spike_data):
    """
    Send a spike alert to Discord via webhook.

    Args:
        spike_data: Dict containing spike information

    Returns:
        True if sent successfully, False otherwise
    """
    # Check if webhook is configured
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured - skipping notification")
        return False

    # Check for duplicate notification (prevent double-sends)
    market_id = spike_data.get('market_id', '')
    metric_type = spike_data.get('metric_type', '')
    if _check_and_update_dedup_cache(market_id, metric_type):
        logger.info(f"Duplicate notification suppressed for {market_id}/{metric_type}")
        return True  # Return True so caller doesn't treat it as failure

    try:
        # Create the embed
        embed = create_spike_embed(spike_data)

        # Build the payload
        payload = {
            "embeds": [embed]
        }

        # Send to Discord
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        # Check response
        if response.status_code == 204:
            logger.info(f"Discord notification sent for market: {spike_data.get('market_id')}")
            return True
        elif response.status_code == 429:
            # Rate limited
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
        logger.error(f"Unexpected error sending Discord notification: {e}")
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

    # Create fake spike data for testing
    test_spike = {
        'alert_id': 0,
        'market_id': 'test-123',
        'question': 'Test Alert - Polymarket Monitor is working!',
        'metric_type': 'orderbook_bid_depth',
        'spike_ratio': 3.5,
        'baseline_value': 10000.00,
        'current_value': 35000.00,
        'yes_price': 0.65,
        'no_price': 0.35,
        'slug': '',
        'detected_at': datetime.now()
    }

    # Create test embed with different styling
    embed = create_spike_embed(test_spike)
    embed['title'] = "✅ Polymarket Monitor - Test Notification"
    embed['color'] = COLOR_SUCCESS_GREEN
    embed['description'] = "**This is a test notification.**\n\nIf you see this, your Discord webhook is configured correctly!"

    payload = {
        "embeds": [embed]
    }

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


def send_pattern_report_notification(report):
    """
    Send a pattern analysis report to Discord.
    Useful for periodic (e.g., weekly) summaries.

    Args:
        report: Pattern analysis report dict from patterns.py

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        return False

    if 'error' in report:
        return False

    try:
        summary = report.get('summary', {})
        overall_accuracy = summary.get('overall_accuracy', 0)

        # Determine color based on accuracy
        if overall_accuracy >= 70:
            color = COLOR_SUCCESS_GREEN
            title = "📊 Pattern Report: Strong Performance"
        elif overall_accuracy >= 50:
            color = COLOR_INFO_BLUE
            title = "📊 Pattern Analysis Report"
        else:
            color = COLOR_WARNING_ORANGE
            title = "📊 Pattern Report: Review Needed"

        # Build fields
        fields = [
            {
                "name": "📈 Overall Accuracy",
                "value": f"**{overall_accuracy}%** ({summary.get('correct_predictions', 0)}/{summary.get('total_predictions', 0)})",
                "inline": True
            },
            {
                "name": "🔍 Spikes Analyzed",
                "value": str(summary.get('total_spikes', 0)),
                "inline": True
            },
            {
                "name": "✅ Markets Resolved",
                "value": str(summary.get('resolved_markets', 0)),
                "inline": True
            }
        ]

        # Add type-specific accuracy
        for spike_type, stats in report.get('by_spike_type', {}).items():
            type_name = spike_type.replace('orderbook_', '').replace('_', ' ').title()
            fields.append({
                "name": f"📊 {type_name}",
                "value": f"{stats['accuracy']}% ({stats['correct']}/{stats['total']})",
                "inline": True
            })

        # Add best pattern if available
        best_patterns = report.get('best_patterns', [])
        if best_patterns:
            best = best_patterns[0]
            fields.append({
                "name": "🏆 Best Pattern",
                "value": f"**{best['pattern']}**\n{best['accuracy']:.0f}% accuracy ({best['samples']} samples)",
                "inline": False
            })

        # Add insights
        insights = report.get('insights', [])
        if insights:
            insight_text = "\n".join([f"• {i}" for i in insights[:3]])
            fields.append({
                "name": "💡 Key Insights",
                "value": insight_text,
                "inline": False
            })

        embed = {
            "title": title,
            "description": f"Pattern analysis for the last **{report.get('days_analyzed', 30)} days**",
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"Polymarket Monitor • Generated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            logger.info("Pattern report notification sent")
            return True
        else:
            logger.error(f"Failed to send pattern report: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error sending pattern report notification: {e}")
        return False


def send_daily_digest():
    """
    Send a daily digest of all alerts from the past 24 hours.
    Summarizes activity by type and highlights top signals.

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        return False

    try:
        # Get alerts from last 24 hours
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))

        from database import get_connection

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                sa.metric_type,
                sa.spike_ratio,
                sa.detected_at,
                m.question,
                m.slug
            FROM spike_alerts sa
            LEFT JOIN markets m ON sa.market_id = m.market_id
            WHERE sa.detected_at >= NOW() - INTERVAL 24 HOUR
            ORDER BY sa.detected_at DESC
        """)

        alerts = cursor.fetchall()
        cursor.close()
        connection.close()

        if not alerts:
            # No alerts - send a quiet day message
            embed = {
                "title": "📊 Daily Digest: Quiet Day",
                "description": "No significant alerts detected in the past 24 hours.",
                "color": COLOR_INFO_BLUE,
                "footer": {
                    "text": f"Polymarket Monitor • {datetime.now().strftime('%Y-%m-%d')}"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            # Count by type
            type_counts = {}
            for alert in alerts:
                t = alert.get('metric_type', 'unknown')
                type_counts[t] = type_counts.get(t, 0) + 1

            # Find top signals (highest spike ratios)
            sorted_alerts = sorted(alerts, key=lambda x: x.get('spike_ratio', 0) or 0, reverse=True)
            top_alerts = sorted_alerts[:3]

            # Build embed
            fields = [
                {
                    "name": "📈 Total Alerts",
                    "value": f"**{len(alerts)}** in 24 hours",
                    "inline": True
                }
            ]

            # Add type breakdown
            type_emojis = {
                'orderbook_bid_depth': '💰 Bid',
                'orderbook_ask_depth': '📉 Ask',
                'price_momentum': '📈 Momentum',
                'correlation': '🔗 Arbitrage',
                'contrarian_whale': '🐋 Whale'
            }

            breakdown_text = ""
            for t, count in type_counts.items():
                name = type_emojis.get(t, t)
                breakdown_text += f"{name}: **{count}**\n"

            fields.append({
                "name": "📊 By Type",
                "value": breakdown_text or "None",
                "inline": True
            })

            # Add top signals
            if top_alerts:
                top_text = ""
                for i, alert in enumerate(top_alerts, 1):
                    question = (alert.get('question') or 'Unknown')[:40]
                    ratio = alert.get('spike_ratio', 0)
                    if alert.get('metric_type') == 'price_momentum':
                        ratio_str = f"{ratio*100:.0f}pp"
                    else:
                        ratio_str = f"{ratio:.1f}x"
                    top_text += f"{i}. {question}... ({ratio_str})\n"

                fields.append({
                    "name": "🔥 Top Signals",
                    "value": top_text,
                    "inline": False
                })

            # Determine color based on activity level
            if len(alerts) >= 10:
                color = COLOR_ALERT_RED
                title = "📊 Daily Digest: High Activity"
            elif len(alerts) >= 5:
                color = COLOR_WARNING_ORANGE
                title = "📊 Daily Digest: Moderate Activity"
            else:
                color = COLOR_SUCCESS_GREEN
                title = "📊 Daily Digest: Normal Activity"

            embed = {
                "title": title,
                "description": f"Summary of Polymarket alerts for the past 24 hours",
                "color": color,
                "fields": fields,
                "footer": {
                    "text": f"Polymarket Monitor • {datetime.now().strftime('%Y-%m-%d')}"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 204:
            logger.info("Daily digest sent to Discord")
            return True
        else:
            logger.error(f"Failed to send daily digest: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error sending daily digest: {e}")
        return False


def send_batch_notification(spikes):
    """
    Send a summary notification for multiple spikes.
    Useful if many spikes detected at once.

    Args:
        spikes: List of spike data dicts

    Returns:
        True if successful, False otherwise
    """
    if not DISCORD_WEBHOOK_URL or not spikes:
        return False

    try:
        # Create summary embed
        embed = {
            "title": f"🚨 {len(spikes)} Polymarket Spikes Detected",
            "description": "Multiple markets showing unusual activity:",
            "color": COLOR_ALERT_RED,
            "fields": [],
            "footer": {
                "text": f"Polymarket Monitor • {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Add field for each spike (up to 10 to stay within Discord limits)
        for spike in spikes[:10]:
            question = spike.get('question', 'Unknown')[:50]
            ratio = spike.get('spike_ratio', 0)
            metric = format_metric_name(spike.get('metric_type', ''))

            embed['fields'].append({
                "name": f"{question}...",
                "value": f"{metric}: **{ratio:.1f}x** spike",
                "inline": False
            })

        if len(spikes) > 10:
            embed['fields'].append({
                "name": "...",
                "value": f"And {len(spikes) - 10} more spikes",
                "inline": False
            })

        payload = {"embeds": [embed]}

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        return response.status_code == 204

    except Exception as e:
        logger.error(f"Error sending batch notification: {e}")
        return False


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Discord Webhook Test")
    print("=" * 60)

    if not DISCORD_WEBHOOK_URL:
        print("\n[ERROR] DISCORD_WEBHOOK_URL is not set!")
        print("        Add it to your .env file:")
        print("        DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
    else:
        print(f"\nWebhook URL configured: {DISCORD_WEBHOOK_URL[:50]}...")
        print("\nSending test notification...")
        success = send_test_notification()

        if success:
            print("\n[OK] Discord integration is working!")
        else:
            print("\n[FAIL] Discord integration failed. Check the errors above.")
