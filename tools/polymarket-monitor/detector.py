"""
Spike detection module for Polymarket Monitor.
Detects unusual orderbook activity and price momentum that may indicate informed trading.
"""

import logging
from datetime import datetime
from decimal import Decimal

import mysql.connector
from mysql.connector import Error

from config import (
    SPIKE_THRESHOLD_RATIO,
    BASELINE_HOURS,
    MIN_ORDERBOOK_DEPTH,
    CONTRARIAN_INFLUX_THRESHOLD,
    CONTRARIAN_MIN_PRIOR_RATIO,
    CONTRARIAN_BASELINE_SNAPSHOTS,
    CONTRARIAN_MIN_PRICE_SHIFT
)
from database import get_connection, insert_alert, mark_alert_notified, insert_prediction

logger = logging.getLogger(__name__)

# Minimum snapshots needed to establish baseline (6 hours at 30min intervals)
MIN_SNAPSHOTS_FOR_BASELINE = 12

# Hours to suppress duplicate alerts for same market/metric
DUPLICATE_ALERT_HOURS = 6

# Metrics to check for orderbook spikes
MONITORED_METRICS = ['orderbook_bid_depth', 'orderbook_ask_depth']

# Minimum signal quality score to send a Discord notification (0-100)
# 65 = "good" quality, 80 = "excellent" quality
# Only signals rated "good" or above will trigger notifications
MIN_SIGNAL_QUALITY_SCORE = 50

# =============================================================================
# Price Momentum Detection Configuration
# =============================================================================

# Minimum price change (in percentage points) to trigger momentum alert
# 0.20 = 20 percentage points (e.g., 40% -> 60% or 65% -> 45%)
PRICE_MOMENTUM_THRESHOLD = 0.15

# Number of snapshots for price baseline
# 12 snapshots = 6 hours at 30min intervals (more robust baseline)
PRICE_BASELINE_SNAPSHOTS = 12

# Minimum baseline price to avoid alerts on very low probability markets
# Markets with baseline price < 0.10 or > 0.90 are often noise
MIN_BASELINE_PRICE = 0.08
MAX_BASELINE_PRICE = 0.92

# Price metrics (used for validation)
PRICE_METRICS = ['yes_price']


def get_markets_with_sufficient_history():
    """
    Get list of market_ids that have enough historical data for baseline calculation.

    Returns:
        List of market_id strings with >= MIN_SNAPSHOTS_FOR_BASELINE snapshots
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            SELECT market_id, COUNT(*) as snapshot_count
            FROM market_snapshots
            GROUP BY market_id
            HAVING COUNT(*) >= %s
        """

        cursor.execute(query, (MIN_SNAPSHOTS_FOR_BASELINE,))
        results = cursor.fetchall()

        market_ids = [row[0] for row in results]
        logger.debug(f"Found {len(market_ids)} markets with sufficient history")

        return market_ids

    except Error as e:
        logger.error(f"Error getting markets with history: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def calculate_baseline(market_id, metric='orderbook_bid_depth'):
    """
    Calculate baseline average for a metric using recent historical data.

    Args:
        market_id: The market identifier
        metric: Column name to calculate baseline for

    Returns:
        Float baseline value, or None if insufficient data
    """
    connection = None
    cursor = None

    # Validate metric to prevent SQL injection
    if metric not in MONITORED_METRICS:
        logger.error(f"Invalid metric: {metric}")
        return None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get average of last N snapshots (excluding the most recent one)
        # We exclude the most recent so we're comparing current vs historical
        query = f"""
            SELECT AVG({metric}) as baseline
            FROM (
                SELECT {metric}
                FROM market_snapshots
                WHERE market_id = %s
                  AND {metric} IS NOT NULL
                  AND {metric} > 0
                ORDER BY timestamp DESC
                LIMIT %s OFFSET 1
            ) as recent_snapshots
        """

        cursor.execute(query, (market_id, MIN_SNAPSHOTS_FOR_BASELINE))
        result = cursor.fetchone()

        if result and result[0]:
            baseline = float(result[0])
            logger.debug(f"Baseline for {market_id}/{metric}: {baseline:.2f}")
            return baseline

        return None

    except Error as e:
        logger.error(f"Error calculating baseline for {market_id}/{metric}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_current_value(market_id, metric='orderbook_bid_depth'):
    """
    Get the most recent value for a metric.

    Args:
        market_id: The market identifier
        metric: Column name to get current value for

    Returns:
        Float current value, or None if not available
    """
    connection = None
    cursor = None

    if metric not in MONITORED_METRICS:
        logger.error(f"Invalid metric: {metric}")
        return None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = f"""
            SELECT {metric}
            FROM market_snapshots
            WHERE market_id = %s
              AND {metric} IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """

        cursor.execute(query, (market_id,))
        result = cursor.fetchone()

        if result and result[0]:
            return float(result[0])

        return None

    except Error as e:
        logger.error(f"Error getting current value for {market_id}/{metric}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def detect_spike(market_id, metric='orderbook_bid_depth', threshold=None):
    """
    Detect if a spike has occurred for a given market and metric.

    Args:
        market_id: The market identifier
        metric: Metric to check ('orderbook_bid_depth' or 'orderbook_ask_depth')
        threshold: Spike ratio threshold (default from config)

    Returns:
        Tuple of (is_spike, spike_ratio, baseline_value, current_value)
    """
    if threshold is None:
        threshold = SPIKE_THRESHOLD_RATIO

    # Get current value
    current_value = get_current_value(market_id, metric)
    if current_value is None or current_value == 0:
        return False, None, None, None

    # Skip low-liquidity markets
    if current_value < MIN_ORDERBOOK_DEPTH:
        return False, None, None, None

    # Get baseline
    baseline_value = calculate_baseline(market_id, metric)
    if baseline_value is None or baseline_value == 0:
        return False, None, None, None

    # Calculate spike ratio
    spike_ratio = current_value / baseline_value

    if spike_ratio >= threshold:
        logger.info(
            f"Spike detected for {market_id}/{metric}: "
            f"{spike_ratio:.2f}x (current={current_value:.2f}, baseline={baseline_value:.2f})"
        )
        return True, spike_ratio, baseline_value, current_value

    return False, None, None, None


# =============================================================================
# Price Momentum Detection Functions
# =============================================================================

def calculate_price_baseline(market_id, num_snapshots=None):
    """
    Calculate baseline average price using recent historical data.
    Uses a shorter window than orderbook to catch rapid price movements.

    Args:
        market_id: The market identifier
        num_snapshots: Number of snapshots for baseline (default PRICE_BASELINE_SNAPSHOTS)

    Returns:
        Float baseline price (0.0 to 1.0), or None if insufficient data
    """
    if num_snapshots is None:
        num_snapshots = PRICE_BASELINE_SNAPSHOTS

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get average yes_price of last N snapshots (excluding the most recent)
        query = """
            SELECT AVG(yes_price) as baseline
            FROM (
                SELECT yes_price
                FROM market_snapshots
                WHERE market_id = %s
                  AND yes_price IS NOT NULL
                  AND yes_price > 0
                  AND yes_price < 1
                ORDER BY timestamp DESC
                LIMIT %s OFFSET 1
            ) as recent_snapshots
        """

        cursor.execute(query, (market_id, num_snapshots))
        result = cursor.fetchone()

        if result and result[0]:
            baseline = float(result[0])
            logger.debug(f"Price baseline for {market_id}: {baseline:.4f}")
            return baseline

        return None

    except Error as e:
        logger.error(f"Error calculating price baseline for {market_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_current_price(market_id):
    """
    Get the most recent yes_price for a market.

    Args:
        market_id: The market identifier

    Returns:
        Float price (0.0 to 1.0), or None if not available
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            SELECT yes_price
            FROM market_snapshots
            WHERE market_id = %s
              AND yes_price IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """

        cursor.execute(query, (market_id,))
        result = cursor.fetchone()

        if result and result[0]:
            return float(result[0])

        return None

    except Error as e:
        logger.error(f"Error getting current price for {market_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def detect_price_momentum(market_id, threshold=None):
    """
    Detect if significant price momentum has occurred for a market.
    Uses absolute price change rather than ratio (unlike orderbook spikes).

    Args:
        market_id: The market identifier
        threshold: Minimum price change to trigger (default PRICE_MOMENTUM_THRESHOLD)

    Returns:
        Tuple of (is_momentum, price_change, direction, baseline_price, current_price)
        - is_momentum: True if momentum detected
        - price_change: Absolute change in price (always positive)
        - direction: 'up' or 'down'
        - baseline_price: Historical average price
        - current_price: Current price
    """
    if threshold is None:
        threshold = PRICE_MOMENTUM_THRESHOLD

    # Get current price
    current_price = get_current_price(market_id)
    if current_price is None:
        return False, None, None, None, None

    # Get baseline price
    baseline_price = calculate_price_baseline(market_id)
    if baseline_price is None:
        return False, None, None, None, None

    # Filter out extreme markets (very low or very high probability)
    # These markets are often noise or already resolved
    if baseline_price < MIN_BASELINE_PRICE or baseline_price > MAX_BASELINE_PRICE:
        return False, None, None, None, None

    # Calculate price change (absolute difference)
    price_change = current_price - baseline_price
    abs_change = abs(price_change)
    direction = 'up' if price_change > 0 else 'down'

    if abs_change >= threshold:
        logger.info(
            f"Price momentum detected for {market_id}: "
            f"{direction} {abs_change:.1%} (baseline={baseline_price:.1%}, current={current_price:.1%})"
        )
        return True, abs_change, direction, baseline_price, current_price

    return False, None, None, None, None


def format_momentum_output(momentum_data):
    """
    Format a price momentum alert for console output.

    Args:
        momentum_data: Dict with momentum details

    Returns:
        Formatted string
    """
    baseline_pct = (momentum_data.get('baseline_value', 0) or 0) * 100
    current_pct = (momentum_data.get('current_value', 0) or 0) * 100
    change_pct = (momentum_data.get('spike_ratio', 0) or 0) * 100  # reusing spike_ratio for change
    direction = momentum_data.get('direction', 'unknown')

    arrow = "📈" if direction == 'up' else "📉"

    output = f"""
================================================================================
{arrow} PRICE MOMENTUM DETECTED
================================================================================
Market: {momentum_data.get('question', 'Unknown')}
Direction: {direction.upper()}
Baseline (3hr avg): {baseline_pct:.1f}%
Current: {current_pct:.1f}%
Change: {'+' if direction == 'up' else '-'}{change_pct:.1f} percentage points
URL: https://polymarket.com/event/{momentum_data.get('slug', '')}
Detected: {momentum_data.get('detected_at', datetime.now())}
================================================================================
"""
    return output


def check_duplicate_alert(market_id, metric, hours=None):
    """
    Check if we've already alerted for this market/metric.

    Two checks are performed:
    1. If any previous alert for this market/metric was successfully notified
       (notified=TRUE), always treat as duplicate (permanent suppression).
    2. Otherwise, check for recent alerts within the time window to prevent
       rapid-fire alerts before notification is sent.

    Args:
        market_id: The market identifier
        metric: The metric type
        hours: Hours to look back for non-notified duplicates (default DUPLICATE_ALERT_HOURS)

    Returns:
        True if duplicate exists, False if this is new
    """
    if hours is None:
        hours = DUPLICATE_ALERT_HOURS

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Check 1: Has a notification already been sent for this market/metric?
        cursor.execute("""
            SELECT COUNT(*)
            FROM spike_alerts
            WHERE market_id = %s
              AND metric_type = %s
              AND notified = TRUE
        """, (market_id, metric))
        result = cursor.fetchone()

        if result and result[0] > 0:
            logger.debug(f"Already notified for {market_id}/{metric} - permanent suppression")
            return True

        # Check 2: Recent non-notified alert within time window (prevents rapid-fire)
        cursor.execute("""
            SELECT COUNT(*)
            FROM spike_alerts
            WHERE market_id = %s
              AND metric_type = %s
              AND detected_at > NOW() - INTERVAL %s HOUR
        """, (market_id, metric, hours))
        result = cursor.fetchone()

        return result[0] > 0 if result else False

    except Error as e:
        logger.error(f"Error checking duplicate alert: {e}")
        return True  # Assume duplicate on error to avoid spam
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def check_recent_alert_exists(market_id, metric, minutes=5):
    """
    Check if an alert was just created for this market/metric (short window).
    Used as a final check before sending Discord notification to prevent
    race conditions when multiple detector processes run simultaneously.

    Args:
        market_id: The market identifier
        metric: The metric type
        minutes: Minutes to look back (default 5)

    Returns:
        True if recent alert exists (skip notification), False if safe to send
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Check for alerts in the last N minutes (excluding very recent ones from this run)
        # We look for alerts older than 10 seconds but within the window
        query = """
            SELECT COUNT(*)
            FROM spike_alerts
            WHERE market_id = %s
              AND metric_type = %s
              AND detected_at > NOW() - INTERVAL %s MINUTE
              AND detected_at < NOW() - INTERVAL 10 SECOND
        """

        cursor.execute(query, (market_id, metric, minutes))
        result = cursor.fetchone()

        return result[0] > 0 if result else False

    except Error as e:
        logger.error(f"Error checking recent alert: {e}")
        return True  # Assume exists on error to avoid spam
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_market_details(market_id):
    """
    Get market details for enriching spike alerts.

    Args:
        market_id: The market identifier

    Returns:
        Dict with market details or None
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Get market info
        cursor.execute(
            "SELECT * FROM markets WHERE market_id = %s",
            (market_id,)
        )
        market = cursor.fetchone()

        if not market:
            return None

        # Get latest snapshot for current prices
        cursor.execute("""
            SELECT yes_price, no_price
            FROM market_snapshots
            WHERE market_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (market_id,))
        snapshot = cursor.fetchone()

        if snapshot:
            market['yes_price'] = snapshot['yes_price']
            market['no_price'] = snapshot['no_price']

        return market

    except Error as e:
        logger.error(f"Error getting market details for {market_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def log_spike(market_id, metric, spike_ratio, baseline_value, current_value):
    """
    Log a spike alert to the database.

    Args:
        market_id: The market identifier
        metric: The metric that spiked
        spike_ratio: The ratio of current to baseline
        baseline_value: The historical baseline value
        current_value: The current value

    Returns:
        Alert ID or None on failure
    """
    alert_data = {
        'market_id': market_id,
        'metric_type': metric,
        'spike_ratio': spike_ratio,
        'baseline_value': baseline_value,
        'current_value': current_value
    }

    try:
        return insert_alert(alert_data)
    except Exception as e:
        logger.error(f"Error logging spike for {market_id}: {e}")
        return None


def format_spike_output(spike):
    """
    Format a spike for console output.

    Args:
        spike: Spike dict with all details

    Returns:
        Formatted string
    """
    yes_pct = spike.get('yes_price', 0) or 0
    no_pct = spike.get('no_price', 0) or 0

    # Convert to percentage if it's decimal
    if yes_pct <= 1:
        yes_pct = yes_pct * 100
    if no_pct <= 1:
        no_pct = no_pct * 100

    output = f"""
================================================================================
ORDERBOOK SPIKE DETECTED
================================================================================
Market: {spike.get('question', 'Unknown')}
Metric: {spike.get('metric_type', 'Unknown')}
Baseline (6hr avg): ${spike.get('baseline_value', 0):,.2f}
Current: ${spike.get('current_value', 0):,.2f} ({spike.get('spike_ratio', 0):.1f}x)
Odds: {yes_pct:.1f}% Yes / {no_pct:.1f}% No
URL: https://polymarket.com/event/{spike.get('slug', '')}
Detected: {spike.get('detected_at', datetime.now())}
================================================================================
"""
    return output


def detect_contrarian_whale(market_id):
    """
    Detect contrarian whale activity: large bets placed against the previous majority.
    Compares the most recent snapshot against a baseline window to find sudden
    influx on the minority side with price confirmation.

    Args:
        market_id: The market identifier

    Returns:
        Dict with contrarian whale details if detected, or None
    """
    connection = None
    cursor = None
    num_snapshots = CONTRARIAN_BASELINE_SNAPSHOTS + 1  # baseline + current

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Get last N+1 snapshots (current + baseline window)
        cursor.execute("""
            SELECT orderbook_bid_depth, orderbook_ask_depth, yes_price, timestamp
            FROM market_snapshots
            WHERE market_id = %s
              AND orderbook_bid_depth IS NOT NULL
              AND orderbook_ask_depth IS NOT NULL
              AND yes_price IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT %s
        """, (market_id, num_snapshots))

        rows = cursor.fetchall()

        if len(rows) < num_snapshots:
            return None

        # Current snapshot is first row; baseline is the rest
        current = rows[0]
        baseline_rows = rows[1:]

        current_bid = float(current['orderbook_bid_depth'])
        current_ask = float(current['orderbook_ask_depth'])
        current_price = float(current['yes_price'])

        # Calculate baseline averages
        avg_bid = sum(float(r['orderbook_bid_depth']) for r in baseline_rows) / len(baseline_rows)
        avg_ask = sum(float(r['orderbook_ask_depth']) for r in baseline_rows) / len(baseline_rows)
        avg_price = sum(float(r['yes_price']) for r in baseline_rows) / len(baseline_rows)

        # Skip low-liquidity markets
        if max(current_bid, current_ask) < MIN_ORDERBOOK_DEPTH:
            return None

        # Determine which side was dominant in the baseline
        if avg_bid == 0 or avg_ask == 0:
            return None

        if avg_bid >= avg_ask:
            dominant_side = 'bid'
            prior_ratio = avg_bid / avg_ask
            minority_baseline = avg_ask
            minority_current = current_ask
            contrarian_side = 'NO'
        else:
            dominant_side = 'ask'
            prior_ratio = avg_ask / avg_bid
            minority_baseline = avg_bid
            minority_current = current_bid
            contrarian_side = 'YES'

        # Check 1: Market must have been at least CONTRARIAN_MIN_PRIOR_RATIO dominant
        if prior_ratio < CONTRARIAN_MIN_PRIOR_RATIO:
            return None

        # Check 2: Minority side must have grown by CONTRARIAN_INFLUX_THRESHOLD
        if minority_baseline <= 0:
            return None
        influx_ratio = minority_current / minority_baseline
        if influx_ratio < CONTRARIAN_INFLUX_THRESHOLD:
            return None

        # Check 3: Price must confirm the contrarian move
        price_shift = current_price - avg_price
        if contrarian_side == 'YES':
            # Contrarian is YES, so price should go up
            if price_shift < CONTRARIAN_MIN_PRICE_SHIFT:
                return None
        else:
            # Contrarian is NO, so price should go down
            if price_shift > -CONTRARIAN_MIN_PRICE_SHIFT:
                return None

        # Check if dominance actually flipped
        if contrarian_side == 'YES':
            dominance_flipped = current_bid > current_ask
        else:
            dominance_flipped = current_ask > current_bid

        timeframe_hours = len(baseline_rows) * 0.5  # 30min intervals

        result = {
            'contrarian_side': contrarian_side,
            'influx_ratio': influx_ratio,
            'prior_ratio': prior_ratio,
            'dominant_side': dominant_side,
            'dominance_flipped': dominance_flipped,
            'baseline_bid': avg_bid,
            'baseline_ask': avg_ask,
            'current_bid': current_bid,
            'current_ask': current_ask,
            'baseline_price': avg_price,
            'current_price': current_price,
            'price_shift': price_shift,
            'timeframe_hours': timeframe_hours
        }

        logger.info(
            f"Contrarian whale detected for {market_id}: "
            f"{contrarian_side} side, {influx_ratio:.1f}x influx, "
            f"price {avg_price:.1%} -> {current_price:.1%}, "
            f"{'FLIPPED' if dominance_flipped else 'growing'}"
        )

        return result

    except Error as e:
        logger.error(f"Error detecting contrarian whale for {market_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def format_contrarian_output(whale_data):
    """
    Format a contrarian whale alert for console output.

    Args:
        whale_data: Dict with contrarian whale details

    Returns:
        Formatted string
    """
    side = whale_data.get('contrarian_side', '?')
    flipped = whale_data.get('dominance_flipped', False)
    influx = whale_data.get('influx_ratio', 0)
    prior_ratio = whale_data.get('prior_ratio', 0)
    dominant = whale_data.get('dominant_side', '?')
    bl_bid = whale_data.get('baseline_bid', 0)
    bl_ask = whale_data.get('baseline_ask', 0)
    cur_bid = whale_data.get('current_bid', 0)
    cur_ask = whale_data.get('current_ask', 0)
    bl_price = (whale_data.get('baseline_price', 0) or 0) * 100
    cur_price = (whale_data.get('current_price', 0) or 0) * 100
    shift = (whale_data.get('price_shift', 0) or 0) * 100
    hours = whale_data.get('timeframe_hours', 0)

    status = "FLIPPED majority" if flipped else "growing"

    output = f"""
================================================================================
CONTRARIAN WHALE {'MARKET FLIPPED' if flipped else 'ACTIVITY DETECTED'}
================================================================================
Market: {whale_data.get('question', 'Unknown')}
Contrarian Side: {side} ({status})
Influx Ratio: {influx:.1f}x on {side}
Prior Balance: Bid(YES) ${bl_bid:,.0f} / Ask(NO) ${bl_ask:,.0f} ({prior_ratio:.1f}:1 favoring {dominant.upper()})
Current Balance: Bid(YES) ${cur_bid:,.0f} / Ask(NO) ${cur_ask:,.0f}
Price Impact: {bl_price:.1f}% -> {cur_price:.1f}% ({'+' if shift > 0 else ''}{shift:.1f}pp)
Timeframe: {hours:.1f} hours
URL: https://polymarket.com/event/{whale_data.get('slug', '')}
Detected: {whale_data.get('detected_at', datetime.now())}
================================================================================
"""
    return output


def check_duplicate_market_alert(market_id):
    """
    Check if ANY signal type has already been notified for this market.
    Used for unified alerts where we send one notification per market.

    Args:
        market_id: The market identifier

    Returns:
        True if any signal for this market was already notified
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM spike_alerts
            WHERE market_id = %s
              AND notified = TRUE
        """, (market_id,))
        result = cursor.fetchone()

        if result and result[0] > 0:
            logger.debug(f"Already notified for market {market_id} - permanent suppression")
            return True

        return False

    except Error as e:
        logger.error(f"Error checking market duplicate: {e}")
        return True
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def format_unified_output(unified_alert):
    """
    Format a unified alert for console output.

    Args:
        unified_alert: Dict with unified alert data

    Returns:
        Formatted string
    """
    question = unified_alert.get('question', 'Unknown')
    signals = unified_alert.get('signals', [])
    ai = unified_alert.get('ai_suggestion') or {}
    yes_price = unified_alert.get('yes_price')
    slug = unified_alert.get('slug', '')

    grade = ai.get('grade', '?')
    play = ai.get('play', 'NO TRADE')
    reasoning = ai.get('reasoning', '')

    signal_lines = []
    for sig in signals:
        sig_type = sig.get('type', 'unknown')
        if sig_type in ('orderbook_bid_depth', 'orderbook_ask_depth'):
            side = 'Bid' if 'bid' in sig_type else 'Ask'
            signal_lines.append(f"  - {side} Spike: {sig.get('ratio', 0):.1f}x (${sig.get('baseline', 0):,.0f} -> ${sig.get('current', 0):,.0f})")
        elif sig_type == 'price_momentum':
            direction = sig.get('direction', 'up')
            change = sig.get('ratio', 0) * 100
            signal_lines.append(f"  - Price Momentum: {'+' if direction == 'up' else '-'}{change:.1f}pp")
        elif sig_type == 'contrarian_whale':
            signal_lines.append(f"  - Contrarian Whale: {sig.get('ratio', 0):.1f}x on {sig.get('contrarian_side', '?')}")

    signals_text = "\n".join(signal_lines)
    yes_pct = f"{yes_price*100:.1f}%" if yes_price else "N/A"

    output = f"""
================================================================================
UNIFIED ALERT: {grade} Grade | {play}
================================================================================
Market: {question}
Current: {yes_pct} YES
Signals ({len(signals)}):
{signals_text}
AI: {reasoning[:200]}
URL: https://polymarket.com/event/{slug}
Detected: {unified_alert.get('detected_at', datetime.now())}
================================================================================
"""
    return output


def detect_all_spikes(threshold=None, price_threshold=None):
    """
    Main function to detect spikes and price momentum across all eligible markets.
    Uses a two-pass approach: collect signals first, then process per market.

    Args:
        threshold: Override orderbook spike threshold (default from config)
        price_threshold: Override price momentum threshold (default PRICE_MOMENTUM_THRESHOLD)

    Returns:
        List of spike/momentum dicts with full details
    """
    if threshold is None:
        threshold = SPIKE_THRESHOLD_RATIO
    if price_threshold is None:
        price_threshold = PRICE_MOMENTUM_THRESHOLD

    logger.info(f"Starting detection (orderbook: {threshold}x, price momentum: {price_threshold:.0%})...")

    market_ids = get_markets_with_sufficient_history()

    if not market_ids:
        logger.info("No markets with sufficient history for spike detection")
        return []

    logger.info(f"Checking {len(market_ids)} markets for spikes and momentum...")

    # =====================================================================
    # PASS 1: Collect all raw signals per market
    # =====================================================================
    market_signals = {}  # market_id -> list of signal dicts

    for market_id in market_ids:
        try:
            # Check orderbook depth spikes
            for metric in MONITORED_METRICS:
                is_spike, spike_ratio, baseline, current = detect_spike(
                    market_id, metric, threshold
                )
                if is_spike:
                    if market_id not in market_signals:
                        market_signals[market_id] = []
                    market_signals[market_id].append({
                        'type': metric,
                        'ratio': spike_ratio,
                        'baseline': baseline,
                        'current': current,
                        'direction': 'bid' if 'bid' in metric else 'ask',
                    })

            # Check price momentum
            is_momentum, price_change, direction, baseline_price, current_price = detect_price_momentum(
                market_id, price_threshold
            )
            if is_momentum:
                if market_id not in market_signals:
                    market_signals[market_id] = []
                market_signals[market_id].append({
                    'type': 'price_momentum',
                    'ratio': price_change,
                    'baseline': baseline_price,
                    'current': current_price,
                    'direction': direction,
                })

            # Check contrarian whale activity
            contrarian = detect_contrarian_whale(market_id)
            if contrarian:
                if market_id not in market_signals:
                    market_signals[market_id] = []
                market_signals[market_id].append({
                    'type': 'contrarian_whale',
                    'ratio': contrarian['influx_ratio'],
                    'baseline': contrarian['baseline_price'],
                    'current': contrarian['current_price'],
                    'direction': contrarian['contrarian_side'],
                    'contrarian_side': contrarian['contrarian_side'],
                    'dominance_flipped': contrarian.get('dominance_flipped', False),
                })

        except Exception as e:
            logger.error(f"Error collecting signals for market {market_id}: {e}")
            continue

    if not market_signals:
        logger.info("No spikes or momentum detected")
        return []

    logger.info(f"Pass 1 complete: {sum(len(v) for v in market_signals.values())} signals across {len(market_signals)} markets")

    # =====================================================================
    # PASS 2: Process each market with signals
    # =====================================================================
    all_spikes = []

    for market_id, signals in market_signals.items():
        try:
            # Check dedup per market (has ANY signal been notified?)
            if check_duplicate_market_alert(market_id):
                logger.debug(f"Skipping duplicate unified alert for market {market_id}")
                continue

            # Also check per-signal dedup to avoid re-logging
            new_signals = []
            for sig in signals:
                if not check_duplicate_alert(market_id, sig['type']):
                    new_signals.append(sig)
                else:
                    logger.debug(f"Skipping duplicate signal {market_id}/{sig['type']}")

            if not new_signals:
                logger.debug(f"All signals for {market_id} are duplicates")
                continue

            # Get market details
            market = get_market_details(market_id)
            if not market:
                logger.warning(f"Could not get market details for {market_id}")
                continue

            question = market.get('question', 'Unknown')
            yes_price = market.get('yes_price')
            no_price = market.get('no_price')
            slug = market.get('slug', '')
            end_date = market.get('end_date')

            # Log each individual signal to spike_alerts (preserves granular data)
            alert_ids = []
            for sig in new_signals:
                alert_id = log_spike(market_id, sig['type'], sig['ratio'], sig['baseline'], sig['current'])
                if alert_id:
                    alert_ids.append(alert_id)
                    # Build individual spike object for the return list
                    spike_obj = {
                        'alert_id': alert_id,
                        'market_id': market_id,
                        'question': question,
                        'metric_type': sig['type'],
                        'spike_ratio': sig['ratio'],
                        'baseline_value': sig['baseline'],
                        'current_value': sig['current'],
                        'yes_price': yes_price,
                        'no_price': no_price,
                        'slug': slug,
                        'detected_at': datetime.now(),
                        'direction': sig.get('direction'),
                    }
                    if sig['type'] == 'contrarian_whale':
                        spike_obj['contrarian_side'] = sig.get('contrarian_side')
                        spike_obj['dominance_flipped'] = sig.get('dominance_flipped', False)
                    all_spikes.append(spike_obj)

            if not alert_ids:
                continue

            # Calculate signal quality (use highest score among signals)
            best_signal_quality = {}
            for spike_obj in all_spikes:
                if spike_obj.get('market_id') == market_id and spike_obj.get('alert_id') in alert_ids:
                    try:
                        from indicators import calculate_signal_quality
                        sq = calculate_signal_quality(market_id, spike_obj)
                        if sq.get('score', 0) > best_signal_quality.get('score', 0):
                            best_signal_quality = sq
                    except Exception:
                        pass

            # Build unified alert object
            unified_alert = {
                'market_id': market_id,
                'question': question,
                'yes_price': yes_price,
                'no_price': no_price,
                'slug': slug,
                'end_date': end_date,
                'signals': new_signals,
                'signal_quality': best_signal_quality,
                'alert_ids': alert_ids,
                'detected_at': datetime.now(),
            }

            # Call enhanced AI analysis
            try:
                from analyzer import analyze_unified_signal, search_news, extract_search_keywords
                search_query = extract_search_keywords(question)
                news_results = search_news(search_query)
                ai_result = analyze_unified_signal(unified_alert, news_results)
                if ai_result:
                    unified_alert['ai_suggestion'] = ai_result
                    logger.info(f"AI unified analysis: {market_id} -> {ai_result.get('grade')} {ai_result.get('play')}")
            except Exception as ai_error:
                logger.error(f"Failed to generate unified AI analysis: {ai_error}")

            # Log AI prediction to ai_predictions table
            ai = unified_alert.get('ai_suggestion')
            if ai and ai.get('play') != 'NO TRADE':
                try:
                    import json as _json
                    prediction_data = {
                        'market_id': market_id,
                        'suggested_play': ai.get('play'),
                        'grade': ai.get('grade'),
                        'reasoning': ai.get('reasoning'),
                        'key_signal': ai.get('key_signal'),
                        'signals_json': _json.dumps([{
                            'type': s['type'],
                            'ratio': s['ratio'],
                            'direction': s.get('direction')
                        } for s in new_signals]),
                        'market_price_at_prediction': yes_price,
                        'market_end_date': end_date,
                        'alert_ids': ','.join(str(a) for a in alert_ids),
                    }
                    pred_id = insert_prediction(prediction_data)
                    if pred_id:
                        logger.info(f"Logged prediction {pred_id} for {market_id}")
                except Exception as pred_error:
                    logger.error(f"Failed to log prediction: {pred_error}")

            # Print unified console output
            print(format_unified_output(unified_alert))

            # Send ONE unified Discord notification
            signal_score = best_signal_quality.get('score', 0)
            if signal_score < MIN_SIGNAL_QUALITY_SCORE:
                logger.info(f"Signal quality too low ({signal_score}) for {market_id} - skipping Discord notification")
            else:
                try:
                    from notifier import send_unified_notification
                    if send_unified_notification(unified_alert):
                        logger.info(f"Unified Discord alert sent for {market_id} (quality: {signal_score})")
                        for aid in alert_ids:
                            mark_alert_notified(aid)
                    else:
                        logger.debug(f"Unified Discord notification skipped or failed for {market_id}")
                except Exception as notif_error:
                    logger.error(f"Failed to send unified notification: {notif_error}")

        except Exception as e:
            logger.error(f"Error processing unified alert for market {market_id}: {e}")
            continue

    if all_spikes:
        logger.info(f"Detected {len(all_spikes)} alert(s) across {len(market_signals)} markets (unified)")
    else:
        logger.info("No spikes or momentum detected")

    return all_spikes


def detect_correlations():
    """
    Detect correlation divergences across configured market pairs.

    Returns:
        List of divergence dicts
    """
    try:
        from correlator import detect_correlation_divergences, format_correlation_output
        from notifier import send_correlation_notification

        logger.info("Starting correlation divergence detection...")

        divergences = detect_correlation_divergences()

        for div in divergences:
            # Print to console
            print(format_correlation_output(div))

            # Generate AI analysis for correlation
            try:
                from analyzer import analyze_spike
                # Create a pseudo-spike object for AI analysis
                analysis_data = {
                    'question': f"Correlation: {div['market_a']['question']} vs {div['market_b']['question']}",
                    'metric_type': 'correlation',
                    'spike_ratio': div['divergence'],
                    'baseline_value': div['market_a']['current_price'],
                    'current_value': div['market_b']['current_price'],
                    'yes_price': div['market_b']['current_price']
                }
                ai_analysis = analyze_spike(analysis_data)
                if ai_analysis:
                    div['ai_analysis'] = ai_analysis
            except Exception as e:
                logger.debug(f"Could not generate AI analysis for correlation: {e}")

            # Send Discord notification
            try:
                if send_correlation_notification(div):
                    logger.info(f"Correlation alert sent: {div['correlation_name']}")
                    if div.get('alert_id'):
                        mark_alert_notified(div['alert_id'])
            except Exception as e:
                logger.error(f"Failed to send correlation notification: {e}")

        return divergences

    except ImportError as e:
        logger.debug(f"Correlator module not available: {e}")
        return []
    except Exception as e:
        logger.error(f"Error in correlation detection: {e}")
        return []


def run_all_detections(spike_threshold=None, price_threshold=None):
    """
    Run all detection types: orderbook spikes, price momentum, and correlations.

    Args:
        spike_threshold: Override orderbook spike threshold
        price_threshold: Override price momentum threshold

    Returns:
        Dict with 'spikes' and 'correlations' lists
    """
    results = {
        'spikes': [],
        'correlations': [],
        'total_alerts': 0
    }

    # Run spike and momentum detection
    spikes = detect_all_spikes(spike_threshold, price_threshold)
    results['spikes'] = spikes

    # Run correlation detection
    correlations = detect_correlations()
    results['correlations'] = correlations

    results['total_alerts'] = len(spikes) + len(correlations)

    logger.info(f"Detection complete: {len(spikes)} spike(s), {len(correlations)} correlation(s)")

    return results


def run_pattern_analysis(days=30, send_discord=False):
    """
    Run pattern analysis and optionally send report to Discord.

    Args:
        days: Days of history to analyze
        send_discord: Whether to send report to Discord

    Returns:
        Pattern analysis report dict
    """
    try:
        from patterns import generate_pattern_report, format_pattern_report, save_pattern_report
        from notifier import send_pattern_report_notification

        logger.info(f"Running pattern analysis for last {days} days...")

        report = generate_pattern_report(days)

        if 'error' not in report:
            # Print report
            print(format_pattern_report(report))

            # Save to database
            save_pattern_report(report)

            # Send to Discord if requested
            if send_discord:
                if send_pattern_report_notification(report):
                    logger.info("Pattern report sent to Discord")
                else:
                    logger.warning("Failed to send pattern report to Discord")

        return report

    except ImportError as e:
        logger.error(f"Pattern analysis module not available: {e}")
        return {'error': str(e)}
    except Exception as e:
        logger.error(f"Error in pattern analysis: {e}")
        return {'error': str(e)}


if __name__ == "__main__":
    import sys

    # Setup logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Check for command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'patterns':
            # Run pattern analysis only
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            send_discord = '--discord' in sys.argv
            run_pattern_analysis(days, send_discord)

        elif command == 'correlations':
            # Run correlation detection only
            detect_correlations()

        elif command == 'spikes':
            # Run spike/momentum detection only
            detect_all_spikes()

        elif command == 'digest':
            # Send daily digest to Discord
            from notifier import send_daily_digest
            print("Sending daily digest to Discord...")
            if send_daily_digest():
                print("[OK] Daily digest sent successfully")
            else:
                print("[FAIL] Could not send daily digest")

        elif command == 'resolve':
            # Run resolution checker for AI predictions
            from resolver import check_resolutions
            print("Checking AI prediction resolutions...")
            resolved_count = check_resolutions()
            print(f"[OK] Resolved {resolved_count} prediction(s)")

        elif command == 'help':
            print("""
Polymarket Monitor - Spike Detection

Usage:
  python detector.py              Run all detections
  python detector.py spikes       Run spike/momentum detection only
  python detector.py correlations Run correlation detection only
  python detector.py patterns     Run pattern analysis (30 days)
  python detector.py patterns 60  Run pattern analysis (60 days)
  python detector.py patterns 30 --discord  Send pattern report to Discord
  python detector.py digest       Send daily digest to Discord
  python detector.py resolve      Check AI prediction resolutions

Scheduled Commands (for cron):
  # Every 30 minutes - run detection
  */30 * * * * cd /path && python detector.py

  # Daily at 9am - send digest + resolve predictions
  0 9 * * * cd /path && python detector.py digest
  0 9 * * * cd /path && python detector.py resolve

  # Weekly Sunday - send pattern report
  0 10 * * 0 cd /path && python detector.py patterns 7 --discord

Examples:
  python detector.py patterns 30 --discord
  python detector.py digest
  python detector.py spikes
  python detector.py resolve
            """)
        else:
            print(f"Unknown command: {command}")
            print("Use 'python detector.py help' for usage")
    else:
        # Default: run all detections
        print("Running all detections (spikes, momentum, correlations)...")
        results = run_all_detections()
        print(f"\nTotal alerts: {results['total_alerts']}")
        print(f"  - Spikes/Momentum: {len(results['spikes'])}")
        print(f"  - Correlations: {len(results['correlations'])}")
