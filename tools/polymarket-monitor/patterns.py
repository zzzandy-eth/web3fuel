"""
Historical Pattern Recognition module for Polymarket Monitor.
Analyzes past spikes to identify patterns that predict market outcomes.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict

import requests
from mysql.connector import Error

from database import get_connection
from config import REQUEST_TIMEOUT, GAMMA_API_BASE

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Minimum samples needed to consider a pattern statistically significant
MIN_SAMPLES_FOR_PATTERN = 5

# Days of history to analyze
DEFAULT_ANALYSIS_DAYS = 30

# Spike magnitude buckets for pattern analysis
SPIKE_MAGNITUDE_BUCKETS = [
    (3.0, 5.0, "3-5x"),
    (5.0, 10.0, "5-10x"),
    (10.0, float('inf'), "10x+")
]

# Price momentum buckets (percentage points)
MOMENTUM_BUCKETS = [
    (0.10, 0.15, "10-15pp"),
    (0.15, 0.25, "15-25pp"),
    (0.25, float('inf'), "25pp+")
]


# =============================================================================
# Market Outcome Functions
# =============================================================================

def fetch_market_outcome_from_api(market_id):
    """
    Fetch market outcome from Polymarket API.

    Args:
        market_id: The market identifier (condition_id or token_id)

    Returns:
        Dict with 'resolved', 'outcome' ('YES'/'NO'/None), 'resolution_price'
    """
    try:
        # Try to get market info from Gamma API
        response = requests.get(
            f"{GAMMA_API_BASE}/markets/{market_id}",
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()

            # Check if market is resolved
            if data.get('closed') or data.get('resolved'):
                # Determine outcome from final price
                outcome_price = data.get('outcomePrices', [1, 0])[0]
                if isinstance(outcome_price, str):
                    outcome_price = float(outcome_price)

                if outcome_price >= 0.95:
                    outcome = 'YES'
                elif outcome_price <= 0.05:
                    outcome = 'NO'
                else:
                    outcome = None  # Ambiguous

                return {
                    'resolved': True,
                    'outcome': outcome,
                    'resolution_price': outcome_price
                }

        return {'resolved': False, 'outcome': None, 'resolution_price': None}

    except Exception as e:
        logger.debug(f"Could not fetch outcome for {market_id}: {e}")
        return {'resolved': False, 'outcome': None, 'resolution_price': None}


def get_market_outcomes_from_db():
    """
    Get all markets with their current resolution status from database.
    Uses latest snapshot price as proxy for outcome (price near 0 or 1 = resolved).

    Returns:
        Dict mapping market_id to outcome info
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Get latest price for each market
        cursor.execute("""
            SELECT
                m.market_id,
                m.question,
                m.slug,
                ms.yes_price,
                ms.timestamp as last_update
            FROM markets m
            INNER JOIN (
                SELECT market_id, MAX(timestamp) as max_ts
                FROM market_snapshots
                GROUP BY market_id
            ) latest ON m.market_id = latest.market_id
            INNER JOIN market_snapshots ms
                ON ms.market_id = latest.market_id
                AND ms.timestamp = latest.max_ts
        """)

        outcomes = {}
        for row in cursor.fetchall():
            price = float(row['yes_price']) if row['yes_price'] else 0.5

            # Determine if resolved based on price
            if price >= 0.95:
                outcome = 'YES'
                resolved = True
            elif price <= 0.05:
                outcome = 'NO'
                resolved = True
            else:
                outcome = None
                resolved = False

            outcomes[row['market_id']] = {
                'question': row['question'],
                'slug': row['slug'],
                'resolved': resolved,
                'outcome': outcome,
                'final_price': price,
                'last_update': row['last_update']
            }

        return outcomes

    except Error as e:
        logger.error(f"Error getting market outcomes: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Spike History Functions
# =============================================================================

def get_spike_history(days=DEFAULT_ANALYSIS_DAYS):
    """
    Get all spike alerts from the specified time period.

    Args:
        days: Number of days of history to fetch

    Returns:
        List of spike alert dicts
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                sa.id,
                sa.market_id,
                sa.metric_type,
                sa.spike_ratio,
                sa.baseline_value,
                sa.current_value,
                sa.detected_at,
                m.question,
                m.slug
            FROM spike_alerts sa
            LEFT JOIN markets m ON sa.market_id = m.market_id
            WHERE sa.detected_at >= NOW() - INTERVAL %s DAY
            ORDER BY sa.detected_at DESC
        """, (days,))

        spikes = cursor.fetchall()

        # Convert to proper types
        for spike in spikes:
            spike['spike_ratio'] = float(spike['spike_ratio']) if spike['spike_ratio'] else 0
            spike['baseline_value'] = float(spike['baseline_value']) if spike['baseline_value'] else 0
            spike['current_value'] = float(spike['current_value']) if spike['current_value'] else 0

        return spikes

    except Error as e:
        logger.error(f"Error getting spike history: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_price_at_spike(market_id, spike_time):
    """
    Get the YES price at the time of a spike.

    Args:
        market_id: Market identifier
        spike_time: Datetime of the spike

    Returns:
        Float price or None
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get snapshot closest to spike time
        cursor.execute("""
            SELECT yes_price
            FROM market_snapshots
            WHERE market_id = %s
              AND timestamp <= %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (market_id, spike_time))

        result = cursor.fetchone()
        return float(result[0]) if result and result[0] else None

    except Error as e:
        logger.error(f"Error getting price at spike: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Pattern Analysis Functions
# =============================================================================

def classify_spike_magnitude(spike_ratio, metric_type):
    """
    Classify a spike into magnitude bucket.

    Args:
        spike_ratio: The spike ratio or change value
        metric_type: Type of metric (orderbook or momentum)

    Returns:
        String bucket label
    """
    if metric_type == 'price_momentum':
        for low, high, label in MOMENTUM_BUCKETS:
            if low <= spike_ratio < high:
                return label
        return "10-15pp"  # Default
    else:
        for low, high, label in SPIKE_MAGNITUDE_BUCKETS:
            if low <= spike_ratio < high:
                return label
        return "3-5x"  # Default


def determine_spike_prediction(spike):
    """
    Determine what outcome a spike predicts.

    Args:
        spike: Spike dict with metric_type, current_value, baseline_value

    Returns:
        'YES', 'NO', or None if unclear
    """
    metric_type = spike.get('metric_type', '')

    if metric_type == 'orderbook_bid_depth':
        # Bid depth spike = buyers entering = predicts YES
        return 'YES'
    elif metric_type == 'orderbook_ask_depth':
        # Ask depth spike = sellers entering = predicts NO
        return 'NO'
    elif metric_type == 'price_momentum':
        # Price momentum direction determines prediction
        current = spike.get('current_value', 0)
        baseline = spike.get('baseline_value', 0)
        if current > baseline:
            return 'YES'  # Price going up
        else:
            return 'NO'   # Price going down
    elif metric_type == 'correlation':
        return None  # Correlations don't have simple YES/NO prediction

    return None


def analyze_spike_accuracy(spikes, outcomes):
    """
    Analyze accuracy of spikes against actual outcomes.

    Args:
        spikes: List of spike dicts
        outcomes: Dict mapping market_id to outcome info

    Returns:
        Dict with accuracy statistics
    """
    stats = {
        'total_spikes': len(spikes),
        'resolved_markets': 0,
        'correct_predictions': 0,
        'incorrect_predictions': 0,
        'by_type': defaultdict(lambda: {'total': 0, 'correct': 0, 'samples': []}),
        'by_magnitude': defaultdict(lambda: {'total': 0, 'correct': 0}),
        'combined_patterns': defaultdict(lambda: {'total': 0, 'correct': 0, 'samples': []})
    }

    for spike in spikes:
        market_id = spike.get('market_id')
        if not market_id or market_id not in outcomes:
            continue

        outcome_info = outcomes[market_id]
        if not outcome_info.get('resolved'):
            continue

        stats['resolved_markets'] += 1

        # Get spike prediction
        prediction = determine_spike_prediction(spike)
        if not prediction:
            continue

        actual_outcome = outcome_info.get('outcome')
        if not actual_outcome:
            continue

        # Check if prediction was correct
        is_correct = prediction == actual_outcome

        if is_correct:
            stats['correct_predictions'] += 1
        else:
            stats['incorrect_predictions'] += 1

        # Track by type
        metric_type = spike.get('metric_type', 'unknown')
        stats['by_type'][metric_type]['total'] += 1
        if is_correct:
            stats['by_type'][metric_type]['correct'] += 1
        stats['by_type'][metric_type]['samples'].append({
            'market': spike.get('question', '')[:50],
            'prediction': prediction,
            'actual': actual_outcome,
            'correct': is_correct
        })

        # Track by magnitude
        magnitude = classify_spike_magnitude(
            spike.get('spike_ratio', 0),
            metric_type
        )
        magnitude_key = f"{metric_type}_{magnitude}"
        stats['by_magnitude'][magnitude_key]['total'] += 1
        if is_correct:
            stats['by_magnitude'][magnitude_key]['correct'] += 1

        # Track combined patterns (check for multiple spikes on same market)
        pattern_key = f"{metric_type}_{magnitude}"
        stats['combined_patterns'][pattern_key]['total'] += 1
        if is_correct:
            stats['combined_patterns'][pattern_key]['correct'] += 1

    return stats


def find_combined_patterns(spikes, outcomes, time_window_hours=6):
    """
    Find markets with multiple spike types and analyze their combined accuracy.

    Args:
        spikes: List of spike dicts
        outcomes: Dict mapping market_id to outcome info
        time_window_hours: Hours within which to consider spikes as combined

    Returns:
        Dict with combined pattern statistics
    """
    # Group spikes by market
    market_spikes = defaultdict(list)
    for spike in spikes:
        market_id = spike.get('market_id')
        if market_id:
            market_spikes[market_id].append(spike)

    combined_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'markets': []})

    for market_id, market_spike_list in market_spikes.items():
        if len(market_spike_list) < 2:
            continue

        if market_id not in outcomes or not outcomes[market_id].get('resolved'):
            continue

        # Sort by time
        sorted_spikes = sorted(market_spike_list, key=lambda x: x.get('detected_at', datetime.min))

        # Find spike combinations within time window
        for i, spike1 in enumerate(sorted_spikes):
            for spike2 in sorted_spikes[i+1:]:
                time1 = spike1.get('detected_at')
                time2 = spike2.get('detected_at')

                if not time1 or not time2:
                    continue

                # Check if within time window
                time_diff = abs((time2 - time1).total_seconds() / 3600)
                if time_diff > time_window_hours:
                    continue

                # Create pattern key
                types = sorted([spike1.get('metric_type', ''), spike2.get('metric_type', '')])
                pattern_key = f"{types[0]} + {types[1]}"

                # Determine combined prediction (use bid/momentum as primary signal)
                prediction = determine_spike_prediction(spike1)
                if not prediction:
                    prediction = determine_spike_prediction(spike2)

                if not prediction:
                    continue

                actual = outcomes[market_id].get('outcome')
                is_correct = prediction == actual

                combined_stats[pattern_key]['total'] += 1
                if is_correct:
                    combined_stats[pattern_key]['correct'] += 1
                combined_stats[pattern_key]['markets'].append({
                    'question': market_spike_list[0].get('question', '')[:40],
                    'correct': is_correct
                })

    return dict(combined_stats)


# =============================================================================
# Report Generation
# =============================================================================

def generate_pattern_report(days=DEFAULT_ANALYSIS_DAYS):
    """
    Generate a comprehensive pattern analysis report.

    Args:
        days: Days of history to analyze

    Returns:
        Dict with full analysis report
    """
    logger.info(f"Generating pattern report for last {days} days...")

    # Get data
    spikes = get_spike_history(days)
    outcomes = get_market_outcomes_from_db()

    if not spikes:
        return {
            'error': 'No spike data available',
            'days_analyzed': days
        }

    # Run analysis
    accuracy_stats = analyze_spike_accuracy(spikes, outcomes)
    combined_patterns = find_combined_patterns(spikes, outcomes)

    # Calculate overall accuracy
    total_predictions = accuracy_stats['correct_predictions'] + accuracy_stats['incorrect_predictions']
    overall_accuracy = (
        accuracy_stats['correct_predictions'] / total_predictions * 100
        if total_predictions > 0 else 0
    )

    # Find best performing patterns
    best_patterns = []
    for pattern_key, data in accuracy_stats['by_magnitude'].items():
        if data['total'] >= MIN_SAMPLES_FOR_PATTERN:
            accuracy = data['correct'] / data['total'] * 100
            best_patterns.append({
                'pattern': pattern_key,
                'accuracy': accuracy,
                'samples': data['total']
            })

    # Add combined patterns
    for pattern_key, data in combined_patterns.items():
        if data['total'] >= MIN_SAMPLES_FOR_PATTERN:
            accuracy = data['correct'] / data['total'] * 100
            best_patterns.append({
                'pattern': pattern_key,
                'accuracy': accuracy,
                'samples': data['total'],
                'combined': True
            })

    # Sort by accuracy
    best_patterns.sort(key=lambda x: x['accuracy'], reverse=True)

    # Build report
    report = {
        'generated_at': datetime.now().isoformat(),
        'days_analyzed': days,
        'summary': {
            'total_spikes': accuracy_stats['total_spikes'],
            'resolved_markets': accuracy_stats['resolved_markets'],
            'total_predictions': total_predictions,
            'correct_predictions': accuracy_stats['correct_predictions'],
            'overall_accuracy': round(overall_accuracy, 1)
        },
        'by_spike_type': {},
        'by_magnitude': {},
        'combined_patterns': combined_patterns,
        'best_patterns': best_patterns[:10],  # Top 10
        'insights': []
    }

    # Format by type stats
    for spike_type, data in accuracy_stats['by_type'].items():
        if data['total'] > 0:
            accuracy = data['correct'] / data['total'] * 100
            report['by_spike_type'][spike_type] = {
                'total': data['total'],
                'correct': data['correct'],
                'accuracy': round(accuracy, 1)
            }

    # Format by magnitude stats
    for mag_key, data in accuracy_stats['by_magnitude'].items():
        if data['total'] > 0:
            accuracy = data['correct'] / data['total'] * 100
            report['by_magnitude'][mag_key] = {
                'total': data['total'],
                'correct': data['correct'],
                'accuracy': round(accuracy, 1)
            }

    # Generate insights
    report['insights'] = generate_insights(report)

    return report


def generate_insights(report):
    """
    Generate human-readable insights from the pattern report.

    Args:
        report: Pattern analysis report dict

    Returns:
        List of insight strings
    """
    insights = []

    # Overall accuracy insight
    overall = report['summary']['overall_accuracy']
    if overall >= 70:
        insights.append(f"Strong predictive signal: {overall}% overall accuracy")
    elif overall >= 50:
        insights.append(f"Moderate predictive signal: {overall}% overall accuracy")
    else:
        insights.append(f"Weak predictive signal: {overall}% overall accuracy")

    # Best pattern insight
    if report['best_patterns']:
        best = report['best_patterns'][0]
        if best['accuracy'] >= 70 and best['samples'] >= MIN_SAMPLES_FOR_PATTERN:
            insights.append(
                f"Best pattern: '{best['pattern']}' with {best['accuracy']:.0f}% accuracy "
                f"({best['samples']} samples)"
            )

    # Bid vs Ask comparison
    bid_stats = report['by_spike_type'].get('orderbook_bid_depth', {})
    ask_stats = report['by_spike_type'].get('orderbook_ask_depth', {})

    if bid_stats.get('total', 0) >= MIN_SAMPLES_FOR_PATTERN:
        insights.append(
            f"Bid depth spikes: {bid_stats['accuracy']}% accurate for YES outcomes"
        )
    if ask_stats.get('total', 0) >= MIN_SAMPLES_FOR_PATTERN:
        insights.append(
            f"Ask depth spikes: {ask_stats['accuracy']}% accurate for NO outcomes"
        )

    # Momentum insight
    momentum_stats = report['by_spike_type'].get('price_momentum', {})
    if momentum_stats.get('total', 0) >= MIN_SAMPLES_FOR_PATTERN:
        insights.append(
            f"Price momentum: {momentum_stats['accuracy']}% accurate"
        )

    # Combined pattern insight
    for pattern, data in report['combined_patterns'].items():
        if data['total'] >= MIN_SAMPLES_FOR_PATTERN:
            accuracy = data['correct'] / data['total'] * 100
            if accuracy >= 75:
                insights.append(
                    f"Strong combined signal: '{pattern}' at {accuracy:.0f}% ({data['total']} samples)"
                )

    return insights


def format_pattern_report(report):
    """
    Format pattern report for console output.

    Args:
        report: Pattern analysis report dict

    Returns:
        Formatted string
    """
    if 'error' in report:
        return f"\n[ERROR] {report['error']}\n"

    summary = report['summary']

    output = f"""
================================================================================
PATTERN ANALYSIS REPORT
================================================================================
Generated: {report['generated_at']}
Period: Last {report['days_analyzed']} days

SUMMARY
-------
Total Spikes Analyzed: {summary['total_spikes']}
Markets Resolved: {summary['resolved_markets']}
Predictions Made: {summary['total_predictions']}
Correct Predictions: {summary['correct_predictions']}
Overall Accuracy: {summary['overall_accuracy']}%

BY SPIKE TYPE
-------------"""

    for spike_type, stats in report['by_spike_type'].items():
        type_name = spike_type.replace('orderbook_', '').replace('_', ' ').title()
        output += f"\n  {type_name}: {stats['accuracy']}% ({stats['correct']}/{stats['total']})"

    output += "\n\nBY MAGNITUDE"
    output += "\n------------"

    for mag_key, stats in report['by_magnitude'].items():
        if stats['total'] >= MIN_SAMPLES_FOR_PATTERN:
            output += f"\n  {mag_key}: {stats['accuracy']}% ({stats['correct']}/{stats['total']})"

    if report['combined_patterns']:
        output += "\n\nCOMBINED PATTERNS"
        output += "\n-----------------"
        for pattern, data in report['combined_patterns'].items():
            if data['total'] >= MIN_SAMPLES_FOR_PATTERN:
                accuracy = data['correct'] / data['total'] * 100
                output += f"\n  {pattern}: {accuracy:.0f}% ({data['correct']}/{data['total']})"

    if report['best_patterns']:
        output += "\n\nTOP PERFORMING PATTERNS"
        output += "\n-----------------------"
        for i, pattern in enumerate(report['best_patterns'][:5], 1):
            combined_tag = " [COMBINED]" if pattern.get('combined') else ""
            output += f"\n  {i}. {pattern['pattern']}: {pattern['accuracy']:.0f}% ({pattern['samples']} samples){combined_tag}"

    if report['insights']:
        output += "\n\nKEY INSIGHTS"
        output += "\n------------"
        for insight in report['insights']:
            output += f"\n  • {insight}"

    output += "\n\n================================================================================"

    return output


# =============================================================================
# Database Storage for Pattern Stats
# =============================================================================

def save_pattern_report(report):
    """
    Save pattern report to database for historical tracking.

    Args:
        report: Pattern analysis report dict

    Returns:
        True if saved successfully
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                days_analyzed INT,
                total_spikes INT,
                resolved_markets INT,
                overall_accuracy DECIMAL(5,2),
                report_json JSON,
                INDEX idx_generated (generated_at)
            )
        """)

        # Insert report
        cursor.execute("""
            INSERT INTO pattern_reports
            (days_analyzed, total_spikes, resolved_markets, overall_accuracy, report_json)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            report['days_analyzed'],
            report['summary']['total_spikes'],
            report['summary']['resolved_markets'],
            report['summary']['overall_accuracy'],
            json.dumps(report)
        ))

        connection.commit()
        logger.info("Pattern report saved to database")
        return True

    except Error as e:
        logger.error(f"Error saving pattern report: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_accuracy_trend(days=90):
    """
    Get accuracy trend over time from saved reports.

    Args:
        days: Days of report history to fetch

    Returns:
        List of (date, accuracy) tuples
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT DATE(generated_at) as report_date, overall_accuracy
            FROM pattern_reports
            WHERE generated_at >= NOW() - INTERVAL %s DAY
            ORDER BY generated_at ASC
        """, (days,))

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error getting accuracy trend: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# CLI / Testing
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Historical Pattern Recognition")
    print("=" * 60)

    # Generate report
    print("\n[ANALYZING] Generating pattern report...")
    report = generate_pattern_report(days=30)

    if 'error' in report:
        print(f"\n[ERROR] {report['error']}")
        print("Make sure you have spike alert history in the database.")
    else:
        # Display report
        print(format_pattern_report(report))

        # Save to database
        print("\n[SAVING] Saving report to database...")
        if save_pattern_report(report):
            print("[OK] Report saved successfully")
        else:
            print("[WARN] Could not save report to database")

        # Export to JSON
        json_file = 'pattern_report.json'
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"[OK] Report exported to {json_file}")

    print("\n" + "=" * 60)
