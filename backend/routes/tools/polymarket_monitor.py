"""
Polymarket Monitor Dashboard Blueprint
Web dashboard for viewing spike detection alerts and statistics
"""

from flask import Blueprint, render_template, jsonify
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import pooling
import os
import logging
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)

polymarket_monitor_bp = Blueprint('polymarket_monitor', __name__, url_prefix='/tools/polymarket-monitor')

# Load polymarket monitor .env directly for DB config
# The main app .env has different DB credentials, so we read the tool's own .env
_pm_env = {}
try:
    tool_env = Path(__file__).resolve().parents[3] / 'tools' / 'polymarket-monitor' / '.env'
    if tool_env.exists():
        with open(tool_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    _pm_env[key.strip()] = value.strip()
        logger.info(f"Polymarket Monitor: Loaded DB config from {tool_env}")
except Exception as e:
    logger.warning(f"Polymarket Monitor: Could not load tool .env: {e}")

# Database configuration - uses polymarket tool's own credentials
DB_CONFIG = {
    'host': _pm_env.get('DB_HOST', 'localhost'),
    'database': _pm_env.get('DB_NAME', 'polymarket_monitor'),
    'user': _pm_env.get('DB_USER', 'root'),
    'password': _pm_env.get('DB_PASSWORD', ''),
    'port': int(_pm_env.get('DB_PORT', '3306'))
}

# Initialize database connection pool
db_pool = None
if DB_CONFIG['host'] and DB_CONFIG['user']:
    try:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="polymarket_monitor_pool",
            pool_size=3,
            pool_reset_session=True,
            **DB_CONFIG
        )
        logger.info("Polymarket Monitor: Database connection pool initialized")
    except Exception as e:
        logger.error(f"Polymarket Monitor: Failed to create database connection pool: {e}")
else:
    logger.warning("Polymarket Monitor: DB_HOST or DB_USER not configured")

def get_db_connection():
    """Get database connection from pool"""
    try:
        if db_pool:
            return db_pool.get_connection()
        else:
            return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None


# ============================================
# API ENDPOINTS
# ============================================

@polymarket_monitor_bp.route('/api/stats')
def api_stats():
    """Get dashboard statistics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    stats = {}

    try:
        # Total markets tracked
        cursor.execute("SELECT COUNT(*) as count FROM markets")
        stats['total_markets'] = cursor.fetchone()['count']

        # Spikes in last 24 hours
        cursor.execute("""
            SELECT COUNT(*) as count FROM spike_alerts
            WHERE detected_at >= NOW() - INTERVAL 24 HOUR
        """)
        stats['spikes_24h'] = cursor.fetchone()['count']

        # Spikes in last 7 days
        cursor.execute("""
            SELECT COUNT(*) as count FROM spike_alerts
            WHERE detected_at >= NOW() - INTERVAL 7 DAY
        """)
        stats['spikes_7d'] = cursor.fetchone()['count']

        # Last collection time
        cursor.execute("SELECT MAX(timestamp) as last_collection FROM market_snapshots")
        result = cursor.fetchone()
        if result and result['last_collection']:
            stats['last_update'] = result['last_collection'].strftime('%Y-%m-%d %H:%M:%S')
            time_since = datetime.now() - result['last_collection']
            stats['last_update_minutes'] = int(time_since.total_seconds() / 60)
        else:
            stats['last_update'] = 'Never'
            stats['last_update_minutes'] = -1

        # System health status
        if stats['last_update_minutes'] == -1:
            stats['status'] = 'offline'
        elif stats['last_update_minutes'] > 60:
            stats['status'] = 'warning'
        else:
            stats['status'] = 'operational'

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@polymarket_monitor_bp.route('/api/spikes')
def api_spikes():
    """Get recent spike alerts"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                sa.id,
                sa.detected_at,
                sa.metric_type,
                sa.spike_ratio,
                sa.baseline_value,
                sa.current_value,
                m.question,
                m.slug
            FROM spike_alerts sa
            LEFT JOIN markets m ON sa.market_id = m.market_id
            ORDER BY sa.detected_at DESC
            LIMIT 20
        """)

        spikes = cursor.fetchall()

        # Format dates for JSON
        for spike in spikes:
            if spike['detected_at']:
                spike['detected_at'] = spike['detected_at'].strftime('%Y-%m-%d %H:%M:%S')
            spike['spike_ratio'] = float(spike['spike_ratio']) if spike['spike_ratio'] else 0
            spike['baseline_value'] = float(spike['baseline_value']) if spike['baseline_value'] else 0
            spike['current_value'] = float(spike['current_value']) if spike['current_value'] else 0

        return jsonify(spikes)

    except Exception as e:
        logger.error(f"Error fetching spikes: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@polymarket_monitor_bp.route('/api/markets')
def api_markets():
    """Get active markets with most data"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                m.market_id,
                m.question,
                m.slug,
                COUNT(s.id) as snapshot_count,
                MAX(s.timestamp) as last_snapshot,
                AVG(s.orderbook_bid_depth) as avg_bid_depth,
                AVG(s.orderbook_ask_depth) as avg_ask_depth
            FROM markets m
            LEFT JOIN market_snapshots s ON m.market_id = s.market_id
            GROUP BY m.market_id, m.question, m.slug
            HAVING snapshot_count > 0
            ORDER BY snapshot_count DESC
            LIMIT 10
        """)

        markets = cursor.fetchall()

        # Format for JSON
        for market in markets:
            if market['last_snapshot']:
                market['last_snapshot'] = market['last_snapshot'].strftime('%Y-%m-%d %H:%M:%S')
            market['avg_bid_depth'] = float(market['avg_bid_depth']) if market['avg_bid_depth'] else 0
            market['avg_ask_depth'] = float(market['avg_ask_depth']) if market['avg_ask_depth'] else 0

        return jsonify(markets)

    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@polymarket_monitor_bp.route('/api/frequency')
def api_frequency():
    """Get spike frequency data for the last 7 days"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                DATE(detected_at) as date,
                COUNT(*) as count
            FROM spike_alerts
            WHERE detected_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(detected_at)
            ORDER BY date ASC
        """)

        results = cursor.fetchall()

        # Create full 7-day array with zeros for missing days
        frequency = []
        today = datetime.now().date()
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            count = 0
            for r in results:
                if r['date'] == day:
                    count = r['count']
                    break
            frequency.append({
                'date': day.strftime('%m/%d'),
                'day': day.strftime('%a'),
                'count': count
            })

        return jsonify(frequency)

    except Exception as e:
        logger.error(f"Error fetching frequency: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@polymarket_monitor_bp.route('/api/indicators/<market_id>')
def api_indicators(market_id):
    """Get statistical indicators for a specific market"""
    try:
        import sys
        import os
        # Add tools path
        tools_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'tools', 'polymarket-monitor')
        sys.path.insert(0, tools_path)

        from indicators import analyze_market
        analysis = analyze_market(market_id)
        return jsonify(analysis)
    except ImportError as e:
        return jsonify({'error': f'Indicators module not available: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Error fetching indicators: {e}")
        return jsonify({'error': str(e)}), 500


@polymarket_monitor_bp.route('/api/market-health')
def api_market_health():
    """Get health indicators for top markets"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        # Get markets with most recent activity
        cursor.execute("""
            SELECT
                m.market_id,
                m.question,
                m.slug,
                (SELECT yes_price FROM market_snapshots ms
                 WHERE ms.market_id = m.market_id
                 ORDER BY timestamp DESC LIMIT 1) as current_price,
                (SELECT orderbook_bid_depth FROM market_snapshots ms
                 WHERE ms.market_id = m.market_id
                 ORDER BY timestamp DESC LIMIT 1) as bid_depth,
                (SELECT orderbook_ask_depth FROM market_snapshots ms
                 WHERE ms.market_id = m.market_id
                 ORDER BY timestamp DESC LIMIT 1) as ask_depth
            FROM markets m
            WHERE m.updated_at >= NOW() - INTERVAL 24 HOUR
            ORDER BY m.updated_at DESC
            LIMIT 10
        """)

        markets = cursor.fetchall()

        # Calculate simple indicators for each
        for market in markets:
            bid = float(market['bid_depth']) if market['bid_depth'] else 0
            ask = float(market['ask_depth']) if market['ask_depth'] else 0
            price = float(market['current_price']) if market['current_price'] else 0.5

            # Imbalance ratio
            if ask > 0:
                imbalance = bid / ask
                if imbalance > 1:
                    market['imbalance_direction'] = 'bullish'
                    market['imbalance_ratio'] = round(imbalance, 1)
                else:
                    market['imbalance_direction'] = 'bearish'
                    market['imbalance_ratio'] = round(1/imbalance if imbalance > 0 else 0, 1)
            else:
                market['imbalance_direction'] = 'unknown'
                market['imbalance_ratio'] = 0

            market['current_price'] = round(price * 100, 1)
            market['bid_depth'] = round(bid, 0)
            market['ask_depth'] = round(ask, 0)

            # Truncate question
            if market['question'] and len(market['question']) > 50:
                market['question'] = market['question'][:50] + '...'

        return jsonify(markets)

    except Exception as e:
        logger.error(f"Error fetching market health: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@polymarket_monitor_bp.route('/api/patterns')
def api_patterns():
    """Get pattern analysis statistics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        # Get spike type accuracy (simplified analysis)
        # Count spikes by type and check if market price moved toward prediction
        cursor.execute("""
            SELECT
                metric_type,
                COUNT(*) as total,
                SUM(CASE
                    WHEN metric_type = 'orderbook_bid_depth' AND
                         (SELECT yes_price FROM market_snapshots ms2
                          WHERE ms2.market_id = sa.market_id
                          ORDER BY timestamp DESC LIMIT 1) > 0.5 THEN 1
                    WHEN metric_type = 'orderbook_ask_depth' AND
                         (SELECT yes_price FROM market_snapshots ms2
                          WHERE ms2.market_id = sa.market_id
                          ORDER BY timestamp DESC LIMIT 1) < 0.5 THEN 1
                    WHEN metric_type = 'price_momentum' AND
                         sa.current_value > sa.baseline_value AND
                         (SELECT yes_price FROM market_snapshots ms2
                          WHERE ms2.market_id = sa.market_id
                          ORDER BY timestamp DESC LIMIT 1) > 0.5 THEN 1
                    WHEN metric_type = 'price_momentum' AND
                         sa.current_value < sa.baseline_value AND
                         (SELECT yes_price FROM market_snapshots ms2
                          WHERE ms2.market_id = sa.market_id
                          ORDER BY timestamp DESC LIMIT 1) < 0.5 THEN 1
                    WHEN metric_type = 'contrarian_whale' AND
                         sa.current_value > sa.baseline_value AND
                         (SELECT yes_price FROM market_snapshots ms2
                          WHERE ms2.market_id = sa.market_id
                          ORDER BY timestamp DESC LIMIT 1) > 0.5 THEN 1
                    WHEN metric_type = 'contrarian_whale' AND
                         sa.current_value < sa.baseline_value AND
                         (SELECT yes_price FROM market_snapshots ms2
                          WHERE ms2.market_id = sa.market_id
                          ORDER BY timestamp DESC LIMIT 1) < 0.5 THEN 1
                    ELSE 0
                END) as correct
            FROM spike_alerts sa
            WHERE detected_at >= NOW() - INTERVAL 30 DAY
              AND metric_type != 'correlation'
            GROUP BY metric_type
        """)

        type_stats = cursor.fetchall()

        # Format response
        patterns = {
            'by_type': [],
            'overall': {'total': 0, 'correct': 0, 'accuracy': 0}
        }

        total_all = 0
        correct_all = 0

        for stat in type_stats:
            total = stat['total'] or 0
            correct = stat['correct'] or 0
            accuracy = (correct / total * 100) if total > 0 else 0

            type_name = stat['metric_type'].replace('orderbook_', '').replace('_', ' ').title()

            patterns['by_type'].append({
                'type': type_name,
                'metric_type': stat['metric_type'],
                'total': total,
                'correct': correct,
                'accuracy': round(accuracy, 1)
            })

            total_all += total
            correct_all += correct

        patterns['overall'] = {
            'total': total_all,
            'correct': correct_all,
            'accuracy': round((correct_all / total_all * 100) if total_all > 0 else 0, 1)
        }

        return jsonify(patterns)

    except Exception as e:
        logger.error(f"Error fetching patterns: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# MAIN DASHBOARD
# ============================================

@polymarket_monitor_bp.route('/')
def index():
    """Main dashboard page"""
    return render_template('polymarket_monitor.html')
