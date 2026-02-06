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
    MIN_ORDERBOOK_DEPTH
)
from database import get_connection, insert_alert

logger = logging.getLogger(__name__)

# Minimum snapshots needed to establish baseline (6 hours at 30min intervals)
MIN_SNAPSHOTS_FOR_BASELINE = 12

# Hours to suppress duplicate alerts for same market/metric
DUPLICATE_ALERT_HOURS = 6

# Metrics to check for orderbook spikes
MONITORED_METRICS = ['orderbook_bid_depth', 'orderbook_ask_depth']

# =============================================================================
# Price Momentum Detection Configuration
# =============================================================================

# Minimum price change (in percentage points) to trigger momentum alert
# 0.10 = 10 percentage points (e.g., 45% -> 55% or 60% -> 50%)
PRICE_MOMENTUM_THRESHOLD = 0.10

# Number of snapshots for price baseline (shorter window for faster detection)
# 6 snapshots = 3 hours at 30min intervals
PRICE_BASELINE_SNAPSHOTS = 6

# Minimum baseline price to avoid alerts on very low probability markets
# Markets with baseline price < 0.05 or > 0.95 are often noise
MIN_BASELINE_PRICE = 0.05
MAX_BASELINE_PRICE = 0.95

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
    Check if we've already alerted for this market/metric recently.

    Args:
        market_id: The market identifier
        metric: The metric type
        hours: Hours to look back for duplicates (default DUPLICATE_ALERT_HOURS)

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

        query = """
            SELECT COUNT(*)
            FROM spike_alerts
            WHERE market_id = %s
              AND metric_type = %s
              AND detected_at > NOW() - INTERVAL %s HOUR
        """

        cursor.execute(query, (market_id, metric, hours))
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


def detect_all_spikes(threshold=None, price_threshold=None):
    """
    Main function to detect spikes and price momentum across all eligible markets.

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

    # Get markets with sufficient history
    market_ids = get_markets_with_sufficient_history()

    if not market_ids:
        logger.info("No markets with sufficient history for spike detection")
        return []

    logger.info(f"Checking {len(market_ids)} markets for spikes and momentum...")

    spikes = []

    for market_id in market_ids:
        try:
            # =================================================================
            # Check orderbook depth spikes
            # =================================================================
            for metric in MONITORED_METRICS:
                is_spike, spike_ratio, baseline, current = detect_spike(
                    market_id, metric, threshold
                )

                if not is_spike:
                    continue

                # Check for duplicate alert
                if check_duplicate_alert(market_id, metric):
                    logger.debug(f"Skipping duplicate alert for {market_id}/{metric}")
                    continue

                # Log to database
                alert_id = log_spike(market_id, metric, spike_ratio, baseline, current)

                if not alert_id:
                    continue

                # Get market details
                market = get_market_details(market_id)

                # Build spike object
                spike = {
                    'alert_id': alert_id,
                    'market_id': market_id,
                    'question': market.get('question', 'Unknown') if market else 'Unknown',
                    'metric_type': metric,
                    'spike_ratio': spike_ratio,
                    'baseline_value': baseline,
                    'current_value': current,
                    'yes_price': market.get('yes_price') if market else None,
                    'no_price': market.get('no_price') if market else None,
                    'slug': market.get('slug', '') if market else '',
                    'detected_at': datetime.now()
                }

                spikes.append(spike)

                # Print to console
                print(format_spike_output(spike))

                # Calculate statistical indicators
                try:
                    from indicators import calculate_signal_quality, calculate_imbalance, analyze_zscore
                    signal_quality = calculate_signal_quality(market_id, spike)
                    spike['signal_quality'] = signal_quality

                    # Add specific indicators
                    imbalance = calculate_imbalance(market_id)
                    if imbalance.get('ratio'):
                        spike['imbalance'] = imbalance

                    zscore = analyze_zscore(market_id, metric, current)
                    if zscore.get('zscore'):
                        spike['zscore'] = zscore

                    logger.debug(f"Indicators calculated for {market_id}/{metric}: score={signal_quality.get('score')}")
                except Exception as ind_error:
                    logger.debug(f"Could not calculate indicators: {ind_error}")

                # Generate AI analysis (if configured)
                try:
                    from analyzer import analyze_spike
                    ai_analysis = analyze_spike(spike)
                    if ai_analysis:
                        spike['ai_analysis'] = ai_analysis
                        logger.info(f"AI analysis generated for {market_id}/{metric}")
                except Exception as analysis_error:
                    logger.error(f"Failed to generate AI analysis: {analysis_error}")

                # Send Discord notification (with extra duplicate check to prevent race conditions)
                try:
                    from notifier import send_discord_notification
                    if check_recent_alert_exists(market_id, metric, minutes=5):
                        logger.debug(f"Skipping Discord notification - recent alert exists for {market_id}/{metric}")
                    elif send_discord_notification(spike):
                        logger.info(f"Discord alert sent for {market_id}/{metric}")
                    else:
                        logger.debug(f"Discord notification skipped or failed for {market_id}")
                except Exception as notif_error:
                    logger.error(f"Failed to send Discord notification: {notif_error}")

            # =================================================================
            # Check price momentum
            # =================================================================
            is_momentum, price_change, direction, baseline_price, current_price = detect_price_momentum(
                market_id, price_threshold
            )

            if is_momentum:
                metric = 'price_momentum'

                # Check for duplicate alert
                if check_duplicate_alert(market_id, metric):
                    logger.debug(f"Skipping duplicate alert for {market_id}/{metric}")
                else:
                    # Log to database (store price_change as spike_ratio for consistency)
                    alert_id = log_spike(market_id, metric, price_change, baseline_price, current_price)

                    if alert_id:
                        # Get market details
                        market = get_market_details(market_id)

                        # Build momentum object
                        momentum = {
                            'alert_id': alert_id,
                            'market_id': market_id,
                            'question': market.get('question', 'Unknown') if market else 'Unknown',
                            'metric_type': metric,
                            'spike_ratio': price_change,  # Reusing field for consistency
                            'direction': direction,
                            'baseline_value': baseline_price,
                            'current_value': current_price,
                            'yes_price': current_price,
                            'no_price': 1 - current_price if current_price else None,
                            'slug': market.get('slug', '') if market else '',
                            'detected_at': datetime.now()
                        }

                        spikes.append(momentum)

                        # Print to console
                        print(format_momentum_output(momentum))

                        # Calculate statistical indicators
                        try:
                            from indicators import calculate_signal_quality, calculate_rsi, calculate_bollinger_bands
                            signal_quality = calculate_signal_quality(market_id, momentum)
                            momentum['signal_quality'] = signal_quality

                            # Add RSI for momentum signals
                            rsi = calculate_rsi(market_id)
                            if rsi.get('rsi'):
                                momentum['rsi'] = rsi

                            # Add Bollinger Bands
                            bb = calculate_bollinger_bands(market_id)
                            if bb.get('position'):
                                momentum['bollinger'] = bb

                            logger.debug(f"Indicators calculated for {market_id}/{metric}: score={signal_quality.get('score')}")
                        except Exception as ind_error:
                            logger.debug(f"Could not calculate indicators: {ind_error}")

                        # Generate AI analysis (if configured)
                        try:
                            from analyzer import analyze_spike
                            ai_analysis = analyze_spike(momentum)
                            if ai_analysis:
                                momentum['ai_analysis'] = ai_analysis
                                logger.info(f"AI analysis generated for {market_id}/{metric}")
                        except Exception as analysis_error:
                            logger.error(f"Failed to generate AI analysis: {analysis_error}")

                        # Send Discord notification
                        try:
                            from notifier import send_discord_notification
                            if check_recent_alert_exists(market_id, metric, minutes=5):
                                logger.debug(f"Skipping Discord notification - recent alert exists for {market_id}/{metric}")
                            elif send_discord_notification(momentum):
                                logger.info(f"Discord alert sent for {market_id}/{metric}")
                            else:
                                logger.debug(f"Discord notification skipped or failed for {market_id}")
                        except Exception as notif_error:
                            logger.error(f"Failed to send Discord notification: {notif_error}")

        except Exception as e:
            logger.error(f"Error processing market {market_id}: {e}")
            continue

    if spikes:
        logger.info(f"Detected {len(spikes)} alert(s) (orderbook + momentum)")
    else:
        logger.info("No spikes or momentum detected")

    return spikes


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

Scheduled Commands (for cron):
  # Every 30 minutes - run detection
  */30 * * * * cd /path && python detector.py

  # Daily at 9am - send digest
  0 9 * * * cd /path && python detector.py digest

  # Weekly Sunday - send pattern report
  0 10 * * 0 cd /path && python detector.py patterns 7 --discord

Examples:
  python detector.py patterns 30 --discord
  python detector.py digest
  python detector.py spikes
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
