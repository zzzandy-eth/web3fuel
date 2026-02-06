"""
Statistical Indicators module for Polymarket Monitor.
Provides advanced trading indicators adapted for prediction markets.
"""

import logging
import math
from datetime import datetime, timedelta
from collections import defaultdict

from mysql.connector import Error

from database import get_connection

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Z-Score thresholds
ZSCORE_SIGNIFICANT = 2.0      # 95th percentile
ZSCORE_HIGHLY_SIGNIFICANT = 2.5  # 99th percentile
ZSCORE_EXTREME = 3.0          # 99.7th percentile

# RSI settings
RSI_PERIOD = 12  # Number of snapshots for RSI calculation (6 hours at 30min)
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Bollinger Band settings
BB_PERIOD = 20  # Snapshots for moving average
BB_STD_DEV = 2  # Standard deviations for bands

# Bid/Ask imbalance thresholds
IMBALANCE_SIGNIFICANT = 2.0   # 2:1 ratio
IMBALANCE_STRONG = 3.0        # 3:1 ratio
IMBALANCE_EXTREME = 5.0       # 5:1 ratio

# Time-based analysis
NORMAL_HOURS_START = 9   # 9 AM UTC
NORMAL_HOURS_END = 21    # 9 PM UTC

# Minimum data points needed
MIN_DATA_POINTS = 12


# =============================================================================
# Data Fetching Functions
# =============================================================================

def get_market_snapshots(market_id, hours=24):
    """
    Get recent snapshots for a market.

    Args:
        market_id: Market identifier
        hours: Hours of history to fetch

    Returns:
        List of snapshot dicts ordered by timestamp ASC
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                timestamp,
                yes_price,
                no_price,
                orderbook_bid_depth,
                orderbook_ask_depth
            FROM market_snapshots
            WHERE market_id = %s
              AND timestamp >= NOW() - INTERVAL %s HOUR
            ORDER BY timestamp ASC
        """, (market_id, hours))

        snapshots = cursor.fetchall()

        # Convert Decimal to float
        for snap in snapshots:
            for key in ['yes_price', 'no_price', 'orderbook_bid_depth', 'orderbook_ask_depth']:
                if snap.get(key) is not None:
                    snap[key] = float(snap[key])

        return snapshots

    except Error as e:
        logger.error(f"Error getting snapshots for {market_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_all_markets_current_data():
    """
    Get current snapshot data for all markets.

    Returns:
        Dict mapping market_id to current data
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                ms.market_id,
                ms.yes_price,
                ms.orderbook_bid_depth,
                ms.orderbook_ask_depth,
                ms.timestamp
            FROM market_snapshots ms
            INNER JOIN (
                SELECT market_id, MAX(timestamp) as max_ts
                FROM market_snapshots
                GROUP BY market_id
            ) latest ON ms.market_id = latest.market_id AND ms.timestamp = latest.max_ts
        """)

        data = {}
        for row in cursor.fetchall():
            data[row['market_id']] = {
                'yes_price': float(row['yes_price']) if row['yes_price'] else None,
                'bid_depth': float(row['orderbook_bid_depth']) if row['orderbook_bid_depth'] else None,
                'ask_depth': float(row['orderbook_ask_depth']) if row['orderbook_ask_depth'] else None,
                'timestamp': row['timestamp']
            }

        return data

    except Error as e:
        logger.error(f"Error getting current market data: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Statistical Functions
# =============================================================================

def calculate_mean(values):
    """Calculate arithmetic mean."""
    if not values:
        return None
    return sum(values) / len(values)


def calculate_std_dev(values, mean=None):
    """Calculate standard deviation."""
    if not values or len(values) < 2:
        return None
    if mean is None:
        mean = calculate_mean(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def calculate_zscore(value, mean, std_dev):
    """
    Calculate Z-score (number of standard deviations from mean).

    Args:
        value: Current value
        mean: Historical mean
        std_dev: Historical standard deviation

    Returns:
        Z-score or None if calculation not possible
    """
    if std_dev is None or std_dev == 0:
        return None
    return (value - mean) / std_dev


# =============================================================================
# Z-Score Analysis
# =============================================================================

def analyze_zscore(market_id, metric='orderbook_bid_depth', current_value=None):
    """
    Calculate Z-score for a metric to determine statistical significance.

    Args:
        market_id: Market identifier
        metric: Metric to analyze
        current_value: Optional current value (if None, fetched from DB)

    Returns:
        Dict with z-score analysis
    """
    snapshots = get_market_snapshots(market_id, hours=48)

    if len(snapshots) < MIN_DATA_POINTS:
        return {
            'zscore': None,
            'significance': 'insufficient_data',
            'percentile': None
        }

    # Extract metric values
    if metric in ['orderbook_bid_depth', 'orderbook_ask_depth']:
        values = [s.get(metric) for s in snapshots if s.get(metric) is not None and s.get(metric) > 0]
    else:
        values = [s.get('yes_price') for s in snapshots if s.get('yes_price') is not None]

    if len(values) < MIN_DATA_POINTS:
        return {
            'zscore': None,
            'significance': 'insufficient_data',
            'percentile': None
        }

    # Get current value if not provided
    if current_value is None:
        current_value = values[-1] if values else None

    if current_value is None:
        return {
            'zscore': None,
            'significance': 'no_current_value',
            'percentile': None
        }

    # Calculate statistics (excluding current value)
    historical = values[:-1] if len(values) > 1 else values
    mean = calculate_mean(historical)
    std_dev = calculate_std_dev(historical, mean)

    if std_dev is None or std_dev == 0:
        return {
            'zscore': None,
            'significance': 'zero_variance',
            'percentile': None,
            'mean': mean
        }

    zscore = calculate_zscore(current_value, mean, std_dev)

    # Determine significance level
    abs_zscore = abs(zscore)
    if abs_zscore >= ZSCORE_EXTREME:
        significance = 'extreme'
        percentile = 99.7
    elif abs_zscore >= ZSCORE_HIGHLY_SIGNIFICANT:
        significance = 'highly_significant'
        percentile = 99.0
    elif abs_zscore >= ZSCORE_SIGNIFICANT:
        significance = 'significant'
        percentile = 95.0
    else:
        significance = 'normal'
        percentile = None

    return {
        'zscore': round(zscore, 2),
        'significance': significance,
        'percentile': percentile,
        'mean': round(mean, 2),
        'std_dev': round(std_dev, 2),
        'current_value': current_value
    }


# =============================================================================
# RSI (Relative Strength Index)
# =============================================================================

def calculate_rsi(market_id, period=RSI_PERIOD):
    """
    Calculate RSI for a market's price.
    RSI measures momentum and identifies overbought/oversold conditions.

    Args:
        market_id: Market identifier
        period: Number of periods for RSI calculation

    Returns:
        Dict with RSI analysis
    """
    snapshots = get_market_snapshots(market_id, hours=24)

    if len(snapshots) < period + 1:
        return {
            'rsi': None,
            'condition': 'insufficient_data'
        }

    # Get price changes
    prices = [s.get('yes_price') for s in snapshots if s.get('yes_price') is not None]

    if len(prices) < period + 1:
        return {
            'rsi': None,
            'condition': 'insufficient_data'
        }

    # Calculate price changes
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

    # Separate gains and losses
    gains = [c if c > 0 else 0 for c in changes[-period:]]
    losses = [-c if c < 0 else 0 for c in changes[-period:]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    # Determine condition
    if rsi >= RSI_OVERBOUGHT:
        condition = 'overbought'
    elif rsi <= RSI_OVERSOLD:
        condition = 'oversold'
    else:
        condition = 'neutral'

    return {
        'rsi': round(rsi, 1),
        'condition': condition,
        'avg_gain': round(avg_gain * 100, 2),  # As percentage points
        'avg_loss': round(avg_loss * 100, 2)
    }


# =============================================================================
# Bollinger Bands
# =============================================================================

def calculate_bollinger_bands(market_id, period=BB_PERIOD, num_std=BB_STD_DEV):
    """
    Calculate Bollinger Bands for market price.
    Bands help identify price breakouts and volatility.

    Args:
        market_id: Market identifier
        period: Moving average period
        num_std: Number of standard deviations for bands

    Returns:
        Dict with Bollinger Band analysis
    """
    snapshots = get_market_snapshots(market_id, hours=48)

    prices = [s.get('yes_price') for s in snapshots if s.get('yes_price') is not None]

    if len(prices) < period:
        return {
            'upper_band': None,
            'middle_band': None,
            'lower_band': None,
            'position': 'insufficient_data'
        }

    # Calculate moving average and standard deviation
    recent_prices = prices[-period:]
    middle_band = calculate_mean(recent_prices)
    std_dev = calculate_std_dev(recent_prices, middle_band)

    if std_dev is None:
        return {
            'upper_band': None,
            'middle_band': middle_band,
            'lower_band': None,
            'position': 'zero_variance'
        }

    upper_band = middle_band + (num_std * std_dev)
    lower_band = middle_band - (num_std * std_dev)

    # Clamp bands to valid price range (0-1)
    upper_band = min(upper_band, 1.0)
    lower_band = max(lower_band, 0.0)

    current_price = prices[-1]

    # Determine position relative to bands
    if current_price >= upper_band:
        position = 'above_upper'
        breakout = 'bullish_breakout'
    elif current_price <= lower_band:
        position = 'below_lower'
        breakout = 'bearish_breakout'
    elif current_price > middle_band:
        position = 'upper_half'
        breakout = None
    else:
        position = 'lower_half'
        breakout = None

    # Calculate band width (volatility indicator)
    band_width = (upper_band - lower_band) / middle_band if middle_band > 0 else 0

    return {
        'upper_band': round(upper_band, 4),
        'middle_band': round(middle_band, 4),
        'lower_band': round(lower_band, 4),
        'current_price': round(current_price, 4),
        'position': position,
        'breakout': breakout,
        'band_width': round(band_width, 4),
        'volatility': 'high' if band_width > 0.2 else 'low' if band_width < 0.05 else 'normal'
    }


# =============================================================================
# Bid/Ask Imbalance
# =============================================================================

def calculate_imbalance(market_id, current_bid=None, current_ask=None):
    """
    Calculate bid/ask imbalance ratio.
    High bid imbalance = bullish pressure, high ask = bearish.

    Args:
        market_id: Market identifier
        current_bid: Optional current bid depth
        current_ask: Optional current ask depth

    Returns:
        Dict with imbalance analysis
    """
    if current_bid is None or current_ask is None:
        snapshots = get_market_snapshots(market_id, hours=1)
        if snapshots:
            latest = snapshots[-1]
            current_bid = latest.get('orderbook_bid_depth')
            current_ask = latest.get('orderbook_ask_depth')

    if not current_bid or not current_ask or current_ask == 0:
        return {
            'ratio': None,
            'direction': 'unknown',
            'strength': 'unknown'
        }

    # Calculate ratio (bid/ask)
    ratio = current_bid / current_ask

    # Determine direction
    if ratio > 1:
        direction = 'bullish'
        display_ratio = ratio
    else:
        direction = 'bearish'
        display_ratio = 1 / ratio if ratio > 0 else 0

    # Determine strength
    if display_ratio >= IMBALANCE_EXTREME:
        strength = 'extreme'
    elif display_ratio >= IMBALANCE_STRONG:
        strength = 'strong'
    elif display_ratio >= IMBALANCE_SIGNIFICANT:
        strength = 'moderate'
    else:
        strength = 'balanced'

    return {
        'ratio': round(ratio, 2),
        'display_ratio': round(display_ratio, 1),
        'direction': direction,
        'strength': strength,
        'bid_depth': current_bid,
        'ask_depth': current_ask
    }


# =============================================================================
# Volatility Analysis
# =============================================================================

def calculate_volatility(market_id, hours=24):
    """
    Calculate price volatility for a market.

    Args:
        market_id: Market identifier
        hours: Hours of history to analyze

    Returns:
        Dict with volatility metrics
    """
    snapshots = get_market_snapshots(market_id, hours=hours)

    prices = [s.get('yes_price') for s in snapshots if s.get('yes_price') is not None]

    if len(prices) < MIN_DATA_POINTS:
        return {
            'volatility': None,
            'category': 'insufficient_data'
        }

    # Calculate returns (price changes)
    returns = [(prices[i] - prices[i-1]) for i in range(1, len(prices))]

    # Calculate volatility (standard deviation of returns)
    volatility = calculate_std_dev(returns)

    if volatility is None:
        return {
            'volatility': None,
            'category': 'zero_variance'
        }

    # Calculate other metrics
    max_price = max(prices)
    min_price = min(prices)
    price_range = max_price - min_price

    # Categorize volatility
    if volatility > 0.05:  # 5% std dev in returns
        category = 'high'
    elif volatility > 0.02:
        category = 'medium'
    else:
        category = 'low'

    return {
        'volatility': round(volatility * 100, 2),  # As percentage
        'category': category,
        'price_range': round(price_range * 100, 1),  # As percentage points
        'max_price': round(max_price * 100, 1),
        'min_price': round(min_price * 100, 1),
        'samples': len(prices)
    }


# =============================================================================
# Time-Based Anomaly Detection
# =============================================================================

def analyze_time_pattern(market_id, spike_time=None):
    """
    Analyze if activity is occurring at unusual times.

    Args:
        market_id: Market identifier
        spike_time: Time of the spike (default: now)

    Returns:
        Dict with time analysis
    """
    if spike_time is None:
        spike_time = datetime.now()

    # Get hour of spike (UTC)
    spike_hour = spike_time.hour

    # Determine if within normal hours
    is_normal_hours = NORMAL_HOURS_START <= spike_hour < NORMAL_HOURS_END

    # Get historical activity distribution
    snapshots = get_market_snapshots(market_id, hours=168)  # 7 days

    if len(snapshots) < 48:  # Need at least 2 days
        return {
            'is_unusual': None,
            'reason': 'insufficient_history'
        }

    # Count activity by hour
    hour_counts = defaultdict(int)
    for snap in snapshots:
        if snap.get('timestamp'):
            hour_counts[snap['timestamp'].hour] += 1

    total_activity = sum(hour_counts.values())
    if total_activity == 0:
        return {
            'is_unusual': None,
            'reason': 'no_activity'
        }

    # Calculate percentage of activity at spike hour
    spike_hour_pct = hour_counts.get(spike_hour, 0) / total_activity * 100

    # Determine if unusual
    if spike_hour_pct < 2:  # Less than 2% of activity normally happens at this hour
        is_unusual = True
        unusualness = 'very_unusual'
    elif spike_hour_pct < 5:
        is_unusual = True
        unusualness = 'unusual'
    else:
        is_unusual = False
        unusualness = 'normal'

    return {
        'is_unusual': is_unusual,
        'unusualness': unusualness,
        'spike_hour': spike_hour,
        'normal_hours': is_normal_hours,
        'hour_activity_pct': round(spike_hour_pct, 1),
        'peak_hour': max(hour_counts, key=hour_counts.get) if hour_counts else None
    }


# =============================================================================
# Rate of Change (ROC)
# =============================================================================

def calculate_rate_of_change(market_id, metric='orderbook_bid_depth', periods=6):
    """
    Calculate rate of change for a metric.
    Measures velocity of change - rapid changes may indicate breaking news.

    Args:
        market_id: Market identifier
        metric: Metric to analyze
        periods: Number of periods to look back

    Returns:
        Dict with ROC analysis
    """
    snapshots = get_market_snapshots(market_id, hours=12)

    if len(snapshots) < periods + 1:
        return {
            'roc': None,
            'acceleration': 'insufficient_data'
        }

    # Get metric values
    if metric in ['orderbook_bid_depth', 'orderbook_ask_depth']:
        values = [s.get(metric) for s in snapshots if s.get(metric) is not None]
    else:
        values = [s.get('yes_price') for s in snapshots if s.get('yes_price') is not None]

    if len(values) < periods + 1:
        return {
            'roc': None,
            'acceleration': 'insufficient_data'
        }

    # Calculate ROC: ((current - past) / past) * 100
    current = values[-1]
    past = values[-(periods + 1)]

    if past == 0:
        return {
            'roc': None,
            'acceleration': 'zero_baseline'
        }

    roc = ((current - past) / past) * 100

    # Calculate acceleration (ROC of ROC)
    if len(values) >= periods * 2 + 1:
        mid = values[-(periods + 1)]
        earlier = values[-(periods * 2 + 1)]
        if earlier > 0:
            prev_roc = ((mid - earlier) / earlier) * 100
            acceleration = roc - prev_roc
        else:
            acceleration = None
    else:
        acceleration = None

    # Categorize
    if abs(roc) > 100:
        speed = 'extreme'
    elif abs(roc) > 50:
        speed = 'rapid'
    elif abs(roc) > 20:
        speed = 'moderate'
    else:
        speed = 'slow'

    return {
        'roc': round(roc, 1),
        'speed': speed,
        'direction': 'increasing' if roc > 0 else 'decreasing',
        'acceleration': round(acceleration, 1) if acceleration is not None else None,
        'accelerating': acceleration > 0 if acceleration is not None else None
    }


# =============================================================================
# Signal Quality Score
# =============================================================================

def calculate_signal_quality(market_id, spike_data):
    """
    Calculate overall signal quality score based on multiple indicators.

    Args:
        market_id: Market identifier
        spike_data: Dict with spike information

    Returns:
        Dict with signal quality assessment
    """
    scores = []
    factors = []

    metric_type = spike_data.get('metric_type', '')
    current_value = spike_data.get('current_value')
    baseline_value = spike_data.get('baseline_value')

    # 1. Z-Score analysis
    if metric_type in ['orderbook_bid_depth', 'orderbook_ask_depth']:
        zscore_analysis = analyze_zscore(market_id, metric_type, current_value)
        if zscore_analysis.get('zscore') is not None:
            abs_z = abs(zscore_analysis['zscore'])
            if abs_z >= 3:
                scores.append(100)
                factors.append(f"Z-score: {zscore_analysis['zscore']}σ (extreme)")
            elif abs_z >= 2.5:
                scores.append(80)
                factors.append(f"Z-score: {zscore_analysis['zscore']}σ (highly significant)")
            elif abs_z >= 2:
                scores.append(60)
                factors.append(f"Z-score: {zscore_analysis['zscore']}σ (significant)")
            else:
                scores.append(30)
                factors.append(f"Z-score: {zscore_analysis['zscore']}σ (normal)")

    # 2. Bid/Ask Imbalance
    imbalance = calculate_imbalance(market_id)
    if imbalance.get('ratio') is not None:
        if imbalance['strength'] == 'extreme':
            scores.append(90)
            factors.append(f"Imbalance: {imbalance['display_ratio']}:1 {imbalance['direction']} (extreme)")
        elif imbalance['strength'] == 'strong':
            scores.append(70)
            factors.append(f"Imbalance: {imbalance['display_ratio']}:1 {imbalance['direction']} (strong)")
        elif imbalance['strength'] == 'moderate':
            scores.append(50)
            factors.append(f"Imbalance: {imbalance['display_ratio']}:1 {imbalance['direction']}")
        else:
            scores.append(20)
            factors.append("Imbalance: balanced")

    # 3. Volatility context
    volatility = calculate_volatility(market_id)
    if volatility.get('category'):
        if volatility['category'] == 'low':
            # Low volatility + spike = more significant
            scores.append(80)
            factors.append(f"Low volatility market (spike more significant)")
        elif volatility['category'] == 'high':
            scores.append(40)
            factors.append(f"High volatility market (spike less unusual)")
        else:
            scores.append(60)
            factors.append(f"Normal volatility")

    # 4. Rate of change
    if metric_type in ['orderbook_bid_depth', 'orderbook_ask_depth']:
        roc = calculate_rate_of_change(market_id, metric_type)
        if roc.get('speed'):
            if roc['speed'] == 'extreme':
                scores.append(90)
                factors.append(f"Rate of change: {roc['roc']}% (extreme velocity)")
            elif roc['speed'] == 'rapid':
                scores.append(70)
                factors.append(f"Rate of change: {roc['roc']}% (rapid)")

    # 5. Time-based
    time_analysis = analyze_time_pattern(market_id)
    if time_analysis.get('is_unusual'):
        scores.append(75)
        factors.append(f"Unusual timing: {time_analysis['spike_hour']}:00 UTC ({time_analysis['hour_activity_pct']}% normal activity)")

    # 6. RSI for price momentum
    if metric_type == 'price_momentum':
        rsi = calculate_rsi(market_id)
        if rsi.get('rsi') is not None:
            if rsi['condition'] == 'overbought':
                scores.append(70)
                factors.append(f"RSI: {rsi['rsi']} (overbought - potential reversal)")
            elif rsi['condition'] == 'oversold':
                scores.append(70)
                factors.append(f"RSI: {rsi['rsi']} (oversold - potential reversal)")
            else:
                scores.append(40)
                factors.append(f"RSI: {rsi['rsi']} (neutral)")

    # Calculate overall score
    if scores:
        overall_score = sum(scores) / len(scores)
    else:
        overall_score = 50  # Default neutral

    # Determine quality rating
    if overall_score >= 80:
        rating = 'excellent'
        emoji = '🔥'
    elif overall_score >= 65:
        rating = 'good'
        emoji = '✅'
    elif overall_score >= 50:
        rating = 'moderate'
        emoji = '⚡'
    else:
        rating = 'weak'
        emoji = '⚪'

    return {
        'score': round(overall_score, 0),
        'rating': rating,
        'emoji': emoji,
        'factors': factors,
        'factor_count': len(factors)
    }


# =============================================================================
# Comprehensive Market Analysis
# =============================================================================

def analyze_market(market_id, include_all=True):
    """
    Run comprehensive analysis on a market.

    Args:
        market_id: Market identifier
        include_all: Include all indicators

    Returns:
        Dict with all analysis results
    """
    analysis = {
        'market_id': market_id,
        'analyzed_at': datetime.now().isoformat()
    }

    # Z-Score for bid depth
    analysis['zscore_bid'] = analyze_zscore(market_id, 'orderbook_bid_depth')

    # Z-Score for ask depth
    analysis['zscore_ask'] = analyze_zscore(market_id, 'orderbook_ask_depth')

    # RSI
    analysis['rsi'] = calculate_rsi(market_id)

    # Bollinger Bands
    analysis['bollinger'] = calculate_bollinger_bands(market_id)

    # Bid/Ask Imbalance
    analysis['imbalance'] = calculate_imbalance(market_id)

    # Volatility
    analysis['volatility'] = calculate_volatility(market_id)

    # Time pattern
    analysis['time_pattern'] = analyze_time_pattern(market_id)

    # Rate of change
    analysis['roc_bid'] = calculate_rate_of_change(market_id, 'orderbook_bid_depth')
    analysis['roc_price'] = calculate_rate_of_change(market_id, 'yes_price')

    return analysis


# =============================================================================
# CLI / Testing
# =============================================================================

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("Statistical Indicators Module - Test")
    print("=" * 70)

    # Get a market to analyze
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT market_id, question
        FROM markets
        ORDER BY updated_at DESC
        LIMIT 1
    """)

    market = cursor.fetchone()
    cursor.close()
    connection.close()

    if not market:
        print("\n[ERROR] No markets found in database")
        sys.exit(1)

    market_id = market['market_id']
    print(f"\nAnalyzing: {market['question'][:60]}...")
    print("-" * 70)

    # Run full analysis
    analysis = analyze_market(market_id)

    # Display results
    print("\n[Z-SCORE ANALYSIS]")
    print(f"  Bid Depth: {analysis['zscore_bid'].get('zscore', 'N/A')}σ ({analysis['zscore_bid'].get('significance', 'N/A')})")
    print(f"  Ask Depth: {analysis['zscore_ask'].get('zscore', 'N/A')}σ ({analysis['zscore_ask'].get('significance', 'N/A')})")

    print("\n[RSI]")
    print(f"  Value: {analysis['rsi'].get('rsi', 'N/A')}")
    print(f"  Condition: {analysis['rsi'].get('condition', 'N/A')}")

    print("\n[BOLLINGER BANDS]")
    bb = analysis['bollinger']
    print(f"  Upper: {bb.get('upper_band', 'N/A')}")
    print(f"  Middle: {bb.get('middle_band', 'N/A')}")
    print(f"  Lower: {bb.get('lower_band', 'N/A')}")
    print(f"  Position: {bb.get('position', 'N/A')}")
    print(f"  Volatility: {bb.get('volatility', 'N/A')}")

    print("\n[BID/ASK IMBALANCE]")
    imb = analysis['imbalance']
    print(f"  Ratio: {imb.get('display_ratio', 'N/A')}:1")
    print(f"  Direction: {imb.get('direction', 'N/A')}")
    print(f"  Strength: {imb.get('strength', 'N/A')}")

    print("\n[VOLATILITY]")
    vol = analysis['volatility']
    print(f"  Volatility: {vol.get('volatility', 'N/A')}%")
    print(f"  Category: {vol.get('category', 'N/A')}")
    print(f"  Price Range: {vol.get('price_range', 'N/A')}pp")

    print("\n[TIME PATTERN]")
    time_p = analysis['time_pattern']
    print(f"  Is Unusual: {time_p.get('is_unusual', 'N/A')}")
    print(f"  Peak Hour: {time_p.get('peak_hour', 'N/A')}:00 UTC")

    print("\n[RATE OF CHANGE]")
    roc = analysis['roc_bid']
    print(f"  Bid ROC: {roc.get('roc', 'N/A')}%")
    print(f"  Speed: {roc.get('speed', 'N/A')}")

    # Test signal quality
    print("\n[SIGNAL QUALITY TEST]")
    test_spike = {
        'metric_type': 'orderbook_bid_depth',
        'current_value': 10000,
        'baseline_value': 3000
    }
    quality = calculate_signal_quality(market_id, test_spike)
    print(f"  Score: {quality['score']}/100")
    print(f"  Rating: {quality['emoji']} {quality['rating']}")
    print(f"  Factors:")
    for factor in quality['factors']:
        print(f"    - {factor}")

    print("\n" + "=" * 70)
