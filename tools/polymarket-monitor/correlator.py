"""
Multi-Market Correlation module for Polymarket Monitor.
Tracks related markets and detects arbitrage opportunities when correlations break down.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from mysql.connector import Error

from database import get_connection
from config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Path to correlation config file
CORRELATIONS_FILE = Path(__file__).parent / 'correlations.json'

# Minimum price divergence to trigger arbitrage alert (percentage points)
# E.g., 0.10 = if markets diverge by 10+ percentage points from expected
MIN_DIVERGENCE_THRESHOLD = 0.10

# Hours to suppress duplicate correlation alerts
CORRELATION_ALERT_HOURS = 12

# =============================================================================
# Correlation Types
# =============================================================================

CORRELATION_TYPES = {
    'positive': 1.0,    # Markets should move in same direction
    'negative': -1.0,   # Markets should move in opposite directions
    'inverse': -1.0,    # Alias for negative
    'same': 1.0,        # Alias for positive
}


# =============================================================================
# Correlation Configuration
# =============================================================================

def load_correlations():
    """
    Load market correlations from config file.

    Returns:
        List of correlation dicts
    """
    if not CORRELATIONS_FILE.exists():
        logger.info(f"No correlations file found at {CORRELATIONS_FILE}")
        return []

    try:
        with open(CORRELATIONS_FILE, 'r') as f:
            data = json.load(f)
            correlations = data.get('correlations', [])
            logger.info(f"Loaded {len(correlations)} market correlations")
            return correlations
    except Exception as e:
        logger.error(f"Error loading correlations: {e}")
        return []


def save_correlations(correlations):
    """
    Save market correlations to config file.

    Args:
        correlations: List of correlation dicts
    """
    try:
        data = {
            'description': 'Market correlation definitions for arbitrage detection',
            'updated': datetime.now().isoformat(),
            'correlations': correlations
        }
        with open(CORRELATIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(correlations)} correlations to {CORRELATIONS_FILE}")
    except Exception as e:
        logger.error(f"Error saving correlations: {e}")


# =============================================================================
# Market Data Functions
# =============================================================================

def get_market_by_slug(slug):
    """
    Get market data by slug.

    Args:
        slug: Market slug (URL identifier)

    Returns:
        Dict with market data or None
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT m.*,
                   (SELECT yes_price FROM market_snapshots
                    WHERE market_id = m.market_id
                    ORDER BY timestamp DESC LIMIT 1) as current_price
            FROM markets m
            WHERE m.slug = %s
        """, (slug,))

        return cursor.fetchone()

    except Error as e:
        logger.error(f"Error getting market by slug {slug}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_market_by_question_keywords(keywords):
    """
    Find market by keywords in question.

    Args:
        keywords: List of keywords to search for

    Returns:
        Dict with market data or None
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Build LIKE conditions for each keyword
        conditions = ' AND '.join([f"m.question LIKE %s" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]

        cursor.execute(f"""
            SELECT m.*,
                   (SELECT yes_price FROM market_snapshots
                    WHERE market_id = m.market_id
                    ORDER BY timestamp DESC LIMIT 1) as current_price
            FROM markets m
            WHERE {conditions}
            LIMIT 1
        """, params)

        return cursor.fetchone()

    except Error as e:
        logger.error(f"Error searching market by keywords: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_market_price_history(market_id, hours=24):
    """
    Get recent price history for a market.

    Args:
        market_id: Market identifier
        hours: Hours of history to fetch

    Returns:
        List of (timestamp, price) tuples
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT timestamp, yes_price
            FROM market_snapshots
            WHERE market_id = %s
              AND timestamp >= NOW() - INTERVAL %s HOUR
              AND yes_price IS NOT NULL
            ORDER BY timestamp ASC
        """, (market_id, hours))

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error getting price history for {market_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_current_prices(market_ids):
    """
    Get current prices for multiple markets.

    Args:
        market_ids: List of market identifiers

    Returns:
        Dict mapping market_id to current price
    """
    if not market_ids:
        return {}

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Get latest price for each market
        placeholders = ','.join(['%s'] * len(market_ids))
        cursor.execute(f"""
            SELECT ms.market_id, ms.yes_price
            FROM market_snapshots ms
            INNER JOIN (
                SELECT market_id, MAX(timestamp) as max_ts
                FROM market_snapshots
                WHERE market_id IN ({placeholders})
                GROUP BY market_id
            ) latest ON ms.market_id = latest.market_id AND ms.timestamp = latest.max_ts
        """, market_ids)

        prices = {}
        for row in cursor.fetchall():
            prices[row['market_id']] = float(row['yes_price']) if row['yes_price'] else None

        return prices

    except Error as e:
        logger.error(f"Error getting current prices: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Correlation Analysis
# =============================================================================

def find_market_for_correlation(correlation_def):
    """
    Find actual market data for a correlation definition.

    Args:
        correlation_def: Dict with 'slug' or 'keywords' for market identification

    Returns:
        Dict with market data or None
    """
    # Try slug first
    if 'slug' in correlation_def:
        market = get_market_by_slug(correlation_def['slug'])
        if market:
            return market

    # Try keywords
    if 'keywords' in correlation_def:
        market = get_market_by_question_keywords(correlation_def['keywords'])
        if market:
            return market

    return None


def calculate_expected_price(base_price, base_change, correlation_type):
    """
    Calculate expected price of correlated market given base market change.

    Args:
        base_price: Current price of base market (0-1)
        base_change: Price change of base market (can be negative)
        correlation_type: 'positive' or 'negative'

    Returns:
        Expected price change for correlated market
    """
    correlation_factor = CORRELATION_TYPES.get(correlation_type, 1.0)
    return base_change * correlation_factor


def check_correlation_divergence(corr_config):
    """
    Check if a market correlation has diverged unexpectedly.

    Args:
        corr_config: Correlation config dict with market_a, market_b, type

    Returns:
        Dict with divergence info or None if no divergence
    """
    # Find markets
    market_a = find_market_for_correlation(corr_config.get('market_a', {}))
    market_b = find_market_for_correlation(corr_config.get('market_b', {}))

    if not market_a or not market_b:
        logger.debug(f"Could not find markets for correlation: {corr_config.get('name', 'unnamed')}")
        return None

    # Get price histories
    history_a = get_market_price_history(market_a['market_id'], hours=6)
    history_b = get_market_price_history(market_b['market_id'], hours=6)

    if len(history_a) < 2 or len(history_b) < 2:
        logger.debug(f"Insufficient price history for correlation check")
        return None

    # Calculate price changes (using 3-hour baseline vs current)
    # Get baseline (average of first half of data)
    baseline_a = sum(p[1] for p in history_a[:len(history_a)//2]) / (len(history_a)//2) if history_a else 0
    baseline_b = sum(p[1] for p in history_b[:len(history_b)//2]) / (len(history_b)//2) if history_b else 0

    current_a = float(market_a.get('current_price', 0) or 0)
    current_b = float(market_b.get('current_price', 0) or 0)

    if baseline_a == 0 or baseline_b == 0:
        return None

    # Calculate changes
    change_a = current_a - baseline_a
    change_b = current_b - baseline_b

    # Calculate expected change for B given change in A
    corr_type = corr_config.get('type', 'positive')
    expected_change_b = calculate_expected_price(current_a, change_a, corr_type)

    # Calculate divergence (difference between actual and expected)
    divergence = abs(change_b - expected_change_b)

    # Check if divergence exceeds threshold
    threshold = corr_config.get('threshold', MIN_DIVERGENCE_THRESHOLD)

    if divergence >= threshold and abs(change_a) >= 0.05:  # Only if A moved significantly
        return {
            'correlation_name': corr_config.get('name', 'Unnamed Correlation'),
            'correlation_type': corr_type,
            'market_a': {
                'question': market_a.get('question', 'Unknown'),
                'slug': market_a.get('slug', ''),
                'market_id': market_a.get('market_id'),
                'baseline_price': baseline_a,
                'current_price': current_a,
                'change': change_a
            },
            'market_b': {
                'question': market_b.get('question', 'Unknown'),
                'slug': market_b.get('slug', ''),
                'market_id': market_b.get('market_id'),
                'baseline_price': baseline_b,
                'current_price': current_b,
                'change': change_b,
                'expected_change': expected_change_b
            },
            'divergence': divergence,
            'arbitrage_signal': get_arbitrage_signal(corr_type, change_a, change_b),
            'detected_at': datetime.now()
        }

    return None


def get_arbitrage_signal(corr_type, change_a, change_b):
    """
    Generate human-readable arbitrage signal.

    Args:
        corr_type: Correlation type ('positive' or 'negative')
        change_a: Price change of market A
        change_b: Price change of market B

    Returns:
        String describing the arbitrage opportunity
    """
    if corr_type in ['negative', 'inverse']:
        # Markets should move opposite
        if change_a > 0 and change_b >= 0:
            return "Market B should DROP as Market A rose - potential BUY NO on B"
        elif change_a < 0 and change_b <= 0:
            return "Market B should RISE as Market A fell - potential BUY YES on B"
        elif change_a > 0 and change_b < 0:
            return "Markets moving as expected (inverse correlation)"
        else:
            return "Markets moving as expected (inverse correlation)"
    else:
        # Markets should move together
        if change_a > 0 and change_b <= 0:
            return "Market B should RISE with Market A - potential BUY YES on B"
        elif change_a < 0 and change_b >= 0:
            return "Market B should DROP with Market A - potential BUY NO on B"
        else:
            return "Markets moving as expected (positive correlation)"


# =============================================================================
# Duplicate Alert Check
# =============================================================================

def check_duplicate_correlation_alert(correlation_name, hours=None):
    """
    Check if we've already alerted for this correlation recently.

    Args:
        correlation_name: Name of the correlation
        hours: Hours to look back (default CORRELATION_ALERT_HOURS)

    Returns:
        True if duplicate exists, False if new
    """
    if hours is None:
        hours = CORRELATION_ALERT_HOURS

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Check spike_alerts table for correlation alerts
        cursor.execute("""
            SELECT COUNT(*)
            FROM spike_alerts
            WHERE metric_type = 'correlation'
              AND market_id = %s
              AND detected_at > NOW() - INTERVAL %s HOUR
        """, (correlation_name, hours))

        result = cursor.fetchone()
        return result[0] > 0 if result else False

    except Error as e:
        logger.error(f"Error checking duplicate correlation alert: {e}")
        return True  # Assume duplicate on error
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def log_correlation_alert(divergence_data):
    """
    Log a correlation alert to the database.

    Args:
        divergence_data: Dict with divergence information

    Returns:
        Alert ID or None
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO spike_alerts
            (market_id, metric_type, spike_ratio, baseline_value, current_value, detected_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            divergence_data['correlation_name'],  # Using name as market_id for correlations
            'correlation',
            divergence_data['divergence'],
            divergence_data['market_a']['current_price'],
            divergence_data['market_b']['current_price']
        ))

        connection.commit()
        return cursor.lastrowid

    except Error as e:
        logger.error(f"Error logging correlation alert: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Main Detection Function
# =============================================================================

def detect_correlation_divergences():
    """
    Main function to detect all correlation divergences.

    Returns:
        List of divergence dicts
    """
    correlations = load_correlations()

    if not correlations:
        logger.info("No correlations configured")
        return []

    logger.info(f"Checking {len(correlations)} market correlations...")

    divergences = []

    for corr in correlations:
        if not corr.get('enabled', True):
            continue

        try:
            divergence = check_correlation_divergence(corr)

            if divergence:
                # Check for duplicate
                if check_duplicate_correlation_alert(divergence['correlation_name']):
                    logger.debug(f"Skipping duplicate correlation alert: {divergence['correlation_name']}")
                    continue

                # Log to database
                alert_id = log_correlation_alert(divergence)
                if alert_id:
                    divergence['alert_id'] = alert_id
                    divergences.append(divergence)

                    logger.info(
                        f"Correlation divergence detected: {divergence['correlation_name']} "
                        f"({divergence['divergence']*100:.1f}pp divergence)"
                    )

        except Exception as e:
            logger.error(f"Error checking correlation {corr.get('name', 'unnamed')}: {e}")
            continue

    if divergences:
        logger.info(f"Detected {len(divergences)} correlation divergence(s)")
    else:
        logger.info("No correlation divergences detected")

    return divergences


def format_correlation_output(divergence):
    """
    Format a correlation divergence for console output.

    Args:
        divergence: Divergence dict

    Returns:
        Formatted string
    """
    ma = divergence['market_a']
    mb = divergence['market_b']

    output = f"""
================================================================================
🔗 CORRELATION DIVERGENCE DETECTED
================================================================================
Correlation: {divergence['correlation_name']}
Type: {divergence['correlation_type'].upper()}

Market A: {ma['question'][:60]}
  Baseline: {ma['baseline_price']*100:.1f}% → Current: {ma['current_price']*100:.1f}%
  Change: {'+' if ma['change'] > 0 else ''}{ma['change']*100:.1f}pp

Market B: {mb['question'][:60]}
  Baseline: {mb['baseline_price']*100:.1f}% → Current: {mb['current_price']*100:.1f}%
  Change: {'+' if mb['change'] > 0 else ''}{mb['change']*100:.1f}pp
  Expected: {'+' if mb['expected_change'] > 0 else ''}{mb['expected_change']*100:.1f}pp

Divergence: {divergence['divergence']*100:.1f} percentage points

💡 ARBITRAGE SIGNAL:
{divergence['arbitrage_signal']}

URLs:
  A: https://polymarket.com/event/{ma['slug']}
  B: https://polymarket.com/event/{mb['slug']}

Detected: {divergence['detected_at']}
================================================================================
"""
    return output


# =============================================================================
# Testing / CLI
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Multi-Market Correlation Detector")
    print("=" * 60)

    # Check if correlations file exists
    if not CORRELATIONS_FILE.exists():
        print(f"\n[INFO] No correlations.json found. Creating example file...")

        # Create example correlations
        example_correlations = [
            {
                "name": "Trump Election vs Impeachment",
                "enabled": True,
                "type": "negative",
                "threshold": 0.10,
                "description": "If Trump wins, impeachment probability should drop",
                "market_a": {
                    "keywords": ["Trump", "win", "2024", "election"]
                },
                "market_b": {
                    "keywords": ["Trump", "impeach"]
                }
            },
            {
                "name": "Bitcoin Price Correlation",
                "enabled": True,
                "type": "positive",
                "threshold": 0.12,
                "description": "Bitcoin hitting milestones should move together",
                "market_a": {
                    "keywords": ["Bitcoin", "100000", "100k"]
                },
                "market_b": {
                    "keywords": ["Bitcoin", "bull", "market"]
                }
            }
        ]

        save_correlations(example_correlations)
        print(f"    Created example correlations.json")
        print(f"    Edit this file to define your market correlations")

    # Load and display correlations
    correlations = load_correlations()
    print(f"\nLoaded {len(correlations)} correlations:")
    for corr in correlations:
        status = "✓" if corr.get('enabled', True) else "✗"
        print(f"  [{status}] {corr.get('name', 'Unnamed')} ({corr.get('type', 'positive')})")

    # Run detection
    print(f"\n[RUNNING] Checking for correlation divergences...")
    divergences = detect_correlation_divergences()

    if divergences:
        print(f"\n[FOUND] {len(divergences)} divergence(s):\n")
        for div in divergences:
            print(format_correlation_output(div))
    else:
        print("\n[OK] No correlation divergences detected")

    print("\n" + "=" * 60)
