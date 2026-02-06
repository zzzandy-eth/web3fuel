"""
Polymarket Monitor Dashboard Blueprint
Web dashboard for viewing spike detection alerts and statistics
"""

from flask import Blueprint, render_template_string, jsonify
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import pooling
import os
import logging

# Setup logging
logger = logging.getLogger(__name__)

polymarket_monitor_bp = Blueprint('polymarket_monitor', __name__, url_prefix='/tools/polymarket-monitor')

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': 'polymarket_monitor',
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# Initialize database connection pool
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
    db_pool = None

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

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Polymarket Monitor - Spike Detection Dashboard</title>
        <style>
            :root {
                --primary: #00ffea;
                --secondary: #ff00ff;
                --background: #000000;
                --text: #ffffff;
                --text-muted: #a1a1aa;
                --border-color: #27272a;
                --card-bg: #161b22;
                --success: #22c55e;
                --warning: #f59e0b;
                --danger: #ef4444;
            }
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                min-height: 100vh;
                color: #e6edf3;
            }

            /* Header */
            .site-header {
                position: sticky;
                top: 0;
                z-index: 40;
                width: 100%;
                border-bottom: 1px solid var(--border-color);
                background: rgba(0, 0, 0, 0.95);
                backdrop-filter: blur(20px);
                box-shadow: 0 4px 20px rgba(0, 255, 234, 0.1);
            }
            .header-container {
                display: flex;
                height: 5rem;
                align-items: center;
                justify-content: space-between;
                max-width: 1650px;
                margin: 0 auto;
                padding: 0 1.5rem;
            }
            .logo {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                text-decoration: none;
                flex-shrink: 0;
            }
            .logo:hover {
                transform: scale(1.05);
                transition: transform 0.3s ease;
            }
            .logo-icon-wrapper {
                position: relative;
                height: 4rem;
                display: flex;
                align-items: center;
            }
            .logo-icon {
                height: 4rem;
                width: auto;
                transition: opacity 0.3s ease;
            }
            .logo-default {
                opacity: 1;
            }
            .logo-neon {
                position: absolute;
                left: 0;
                opacity: 0;
            }
            .logo:hover .logo-default {
                opacity: 0;
            }
            .logo:hover .logo-neon {
                opacity: 1;
            }
            .logo-text {
                font-size: 1.75rem;
                font-weight: bold;
                background: linear-gradient(45deg, var(--primary), var(--secondary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .nav-desktop {
                display: none;
                align-items: center;
                gap: 0.5rem;
                margin-left: auto;
            }
            .nav-link {
                color: var(--text);
                text-decoration: none;
                font-size: 1rem;
                font-weight: 600;
                padding: 0.625rem 1rem;
                border-radius: 8px;
                border: 1px solid transparent;
                transition: all 0.3s ease;
            }
            .nav-link:hover {
                color: var(--primary);
                border-color: var(--primary);
                background: rgba(0, 255, 234, 0.1);
            }
            .nav-link.active {
                color: var(--background);
                background: var(--primary);
                border-color: var(--primary);
            }
            .menu-button {
                background: rgba(0, 255, 234, 0.1);
                border: 2px solid var(--primary);
                color: var(--primary);
                cursor: pointer;
                font-size: 1.25rem;
                padding: 0.625rem;
                border-radius: 8px;
                transition: all 0.3s ease;
            }
            .menu-button:hover {
                background: var(--primary);
                color: var(--background);
            }
            .mobile-menu {
                position: fixed;
                top: 0;
                right: -100%;
                width: 100%;
                height: 100vh;
                background: rgba(0, 0, 0, 0.95);
                backdrop-filter: blur(20px);
                transition: right 0.3s ease;
                z-index: 50;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                gap: 2rem;
            }
            .mobile-menu.active {
                right: 0;
            }
            .close-menu {
                position: absolute;
                top: 1.5rem;
                right: 1.5rem;
                background: transparent;
                border: 2px solid var(--primary);
                color: var(--primary);
                font-size: 1.5rem;
                padding: 0.5rem 0.75rem;
                border-radius: 8px;
                cursor: pointer;
            }
            .mobile-nav-link {
                color: var(--text);
                text-decoration: none;
                font-size: 1.5rem;
                font-weight: 600;
                padding: 1rem 2rem;
                border-radius: 8px;
            }
            @media (min-width: 768px) {
                .nav-desktop { display: flex; }
                .menu-button { display: none; }
            }

            /* Main Container */
            .main-container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 30px 20px;
            }

            /* Tool Header */
            .tool-header {
                text-align: center;
                margin-bottom: 40px;
                padding: 30px;
                background: var(--card-bg);
                border-radius: 16px;
                border: 1px solid var(--border-color);
            }
            .tool-title {
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 10px;
                background: linear-gradient(45deg, var(--primary), var(--secondary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .tool-tagline {
                font-size: 1.1rem;
                color: var(--text-muted);
                margin-bottom: 20px;
            }
            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
            }
            .status-badge.operational {
                background: rgba(34, 197, 94, 0.2);
                color: var(--success);
                border: 1px solid rgba(34, 197, 94, 0.3);
            }
            .status-badge.warning {
                background: rgba(245, 158, 11, 0.2);
                color: var(--warning);
                border: 1px solid rgba(245, 158, 11, 0.3);
            }
            .status-badge.offline {
                background: rgba(239, 68, 68, 0.2);
                color: var(--danger);
                border: 1px solid rgba(239, 68, 68, 0.3);
            }
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            .status-badge.operational .status-dot { background: var(--success); }
            .status-badge.warning .status-dot { background: var(--warning); }
            .status-badge.offline .status-dot { background: var(--danger); }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            /* Stats Grid */
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: var(--card-bg);
                padding: 25px;
                border-radius: 12px;
                text-align: center;
                border: 1px solid var(--border-color);
                transition: transform 0.3s, border-color 0.3s;
            }
            .stat-card:hover {
                transform: translateY(-3px);
                border-color: var(--primary);
            }
            .stat-icon {
                font-size: 2rem;
                margin-bottom: 10px;
            }
            .stat-value {
                font-size: 2.5rem;
                font-weight: 700;
                color: var(--primary);
                margin-bottom: 5px;
            }
            .stat-label {
                color: var(--text-muted);
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            /* Section */
            .section {
                background: var(--card-bg);
                border-radius: 12px;
                border: 1px solid var(--border-color);
                margin-bottom: 30px;
                overflow: hidden;
            }
            .section-header {
                padding: 20px 25px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .section-title {
                font-size: 1.25rem;
                font-weight: 600;
                color: var(--text);
            }
            .section-body {
                padding: 20px 25px;
            }

            /* Table */
            .data-table {
                width: 100%;
                border-collapse: collapse;
            }
            .data-table th {
                text-align: left;
                padding: 12px 15px;
                color: var(--text-muted);
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 1px solid var(--border-color);
            }
            .data-table td {
                padding: 15px;
                border-bottom: 1px solid var(--border-color);
                font-size: 14px;
            }
            .data-table tr:last-child td {
                border-bottom: none;
            }
            .data-table tr:hover {
                background: rgba(0, 255, 234, 0.03);
            }
            .spike-ratio {
                font-weight: 700;
                color: var(--secondary);
            }
            .market-link {
                color: var(--primary);
                text-decoration: none;
            }
            .market-link:hover {
                text-decoration: underline;
            }
            .metric-badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
            }
            .metric-badge.bid {
                background: rgba(34, 197, 94, 0.2);
                color: var(--success);
            }
            .metric-badge.ask {
                background: rgba(239, 68, 68, 0.2);
                color: var(--danger);
            }
            .metric-badge.momentum-up {
                background: rgba(0, 255, 234, 0.2);
                color: var(--primary);
            }
            .metric-badge.momentum-down {
                background: rgba(255, 0, 255, 0.2);
                color: var(--secondary);
            }
            .metric-badge.correlation {
                background: rgba(155, 89, 182, 0.2);
                color: #9b59b6;
            }

            /* Pattern Stats */
            .pattern-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }
            .pattern-card {
                background: rgba(0, 255, 234, 0.05);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 15px;
                text-align: center;
            }
            .pattern-card:hover {
                border-color: var(--primary);
            }
            .pattern-type {
                font-size: 14px;
                color: var(--text-muted);
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .pattern-accuracy {
                font-size: 2rem;
                font-weight: 700;
                margin-bottom: 5px;
            }
            .pattern-accuracy.high { color: var(--success); }
            .pattern-accuracy.medium { color: var(--warning); }
            .pattern-accuracy.low { color: var(--danger); }
            .pattern-samples {
                font-size: 12px;
                color: var(--text-muted);
            }
            .overall-accuracy {
                text-align: center;
                padding: 20px;
                background: linear-gradient(135deg, rgba(0, 255, 234, 0.1), rgba(255, 0, 255, 0.1));
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .overall-label {
                font-size: 14px;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .overall-value {
                font-size: 3rem;
                font-weight: 700;
                background: linear-gradient(45deg, var(--primary), var(--secondary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .overall-subtitle {
                font-size: 13px;
                color: var(--text-muted);
                margin-top: 5px;
            }

            /* Market Health Cards */
            .health-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
            }
            .health-card {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 15px;
                transition: all 0.3s ease;
            }
            .health-card:hover {
                border-color: var(--primary);
                transform: translateY(-2px);
            }
            .health-card-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 12px;
            }
            .health-card-title {
                font-size: 14px;
                color: var(--text);
                flex: 1;
                margin-right: 10px;
            }
            .health-card-title a {
                color: var(--text);
                text-decoration: none;
            }
            .health-card-title a:hover {
                color: var(--primary);
            }
            .health-card-price {
                font-size: 1.25rem;
                font-weight: 700;
                color: var(--primary);
            }
            .health-card-indicators {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            .health-indicator {
                display: flex;
                align-items: center;
                gap: 5px;
                padding: 4px 8px;
                background: rgba(255,255,255,0.05);
                border-radius: 4px;
                font-size: 12px;
            }
            .health-indicator.bullish {
                background: rgba(34, 197, 94, 0.15);
                color: var(--success);
            }
            .health-indicator.bearish {
                background: rgba(239, 68, 68, 0.15);
                color: var(--danger);
            }
            .health-indicator.neutral {
                background: rgba(255,255,255,0.05);
                color: var(--text-muted);
            }
            .depth-bar-container {
                display: flex;
                align-items: center;
                gap: 5px;
                margin-top: 10px;
            }
            .depth-bar {
                flex: 1;
                height: 6px;
                background: var(--border-color);
                border-radius: 3px;
                overflow: hidden;
                display: flex;
            }
            .depth-bar-bid {
                background: var(--success);
                height: 100%;
            }
            .depth-bar-ask {
                background: var(--danger);
                height: 100%;
            }
            .depth-label {
                font-size: 11px;
                color: var(--text-muted);
                min-width: 45px;
            }

            /* Chart */
            .chart-container {
                height: 200px;
                display: flex;
                align-items: flex-end;
                justify-content: space-around;
                gap: 10px;
                padding: 20px 0;
            }
            .chart-bar-wrapper {
                display: flex;
                flex-direction: column;
                align-items: center;
                flex: 1;
                max-width: 80px;
            }
            .chart-bar {
                width: 100%;
                background: linear-gradient(180deg, var(--primary), var(--secondary));
                border-radius: 4px 4px 0 0;
                min-height: 4px;
                transition: height 0.5s ease;
            }
            .chart-label {
                margin-top: 10px;
                font-size: 12px;
                color: var(--text-muted);
            }
            .chart-count {
                font-size: 14px;
                font-weight: 600;
                color: var(--text);
                margin-top: 5px;
            }

            /* Markets List */
            .market-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px 0;
                border-bottom: 1px solid var(--border-color);
            }
            .market-item:last-child {
                border-bottom: none;
            }
            .market-question {
                flex: 1;
                color: var(--text);
                font-size: 14px;
                margin-right: 20px;
            }
            .market-stats {
                display: flex;
                gap: 20px;
                font-size: 13px;
                color: var(--text-muted);
            }
            .market-stat {
                display: flex;
                align-items: center;
                gap: 5px;
            }

            /* Footer */
            .tool-footer {
                background: var(--card-bg);
                border-radius: 12px;
                border: 1px solid var(--border-color);
                padding: 30px;
                margin-top: 40px;
            }
            .footer-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 30px;
            }
            .footer-section h4 {
                color: var(--primary);
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 15px;
            }
            .footer-section p, .footer-section li {
                color: var(--text-muted);
                font-size: 14px;
                line-height: 1.8;
            }
            .footer-section ul {
                list-style: none;
            }
            .footer-section a {
                color: var(--primary);
                text-decoration: none;
            }
            .footer-section a:hover {
                text-decoration: underline;
            }
            .tech-tag {
                display: inline-block;
                padding: 4px 10px;
                background: rgba(0, 255, 234, 0.1);
                border: 1px solid rgba(0, 255, 234, 0.2);
                border-radius: 4px;
                font-size: 12px;
                color: var(--primary);
                margin: 2px;
            }

            /* Loading State */
            .loading {
                text-align: center;
                padding: 40px;
                color: var(--text-muted);
            }
            .loading-spinner {
                width: 40px;
                height: 40px;
                border: 3px solid var(--border-color);
                border-top-color: var(--primary);
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }

            /* Empty State */
            .empty-state {
                text-align: center;
                padding: 40px;
                color: var(--text-muted);
            }
            .empty-state-icon {
                font-size: 3rem;
                margin-bottom: 15px;
                opacity: 0.5;
            }

            /* Alert Type Legend */
            .alert-legend {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                padding: 15px 20px;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .legend-item {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 13px;
                color: var(--text-muted);
            }
            .legend-dot {
                width: 12px;
                height: 12px;
                border-radius: 3px;
            }
            .legend-dot.bid { background: var(--success); }
            .legend-dot.ask { background: var(--danger); }
            .legend-dot.momentum-up { background: var(--primary); }
            .legend-dot.momentum-down { background: var(--secondary); }
            .legend-dot.correlation { background: #9b59b6; }

            /* Filter Buttons */
            .filter-buttons {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 15px;
            }
            .filter-btn {
                padding: 8px 16px;
                border-radius: 20px;
                border: 1px solid var(--border-color);
                background: transparent;
                color: var(--text-muted);
                font-size: 13px;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .filter-btn:hover {
                border-color: var(--primary);
                color: var(--primary);
            }
            .filter-btn.active {
                background: var(--primary);
                border-color: var(--primary);
                color: var(--background);
            }
            .filter-btn .count {
                display: inline-block;
                background: rgba(255,255,255,0.2);
                padding: 2px 6px;
                border-radius: 10px;
                margin-left: 5px;
                font-size: 11px;
            }
            .filter-btn.active .count {
                background: rgba(0,0,0,0.2);
            }

            /* Today's Summary Row */
            .today-summary {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 12px;
                margin-bottom: 25px;
            }
            .summary-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 12px 15px;
                background: var(--card-bg);
                border-radius: 8px;
                border: 1px solid var(--border-color);
            }
            .summary-icon {
                font-size: 1.5rem;
            }
            .summary-info {
                flex: 1;
            }
            .summary-count {
                font-size: 1.25rem;
                font-weight: 700;
                color: var(--text);
            }
            .summary-label {
                font-size: 11px;
                color: var(--text-muted);
                text-transform: uppercase;
            }

            /* Confidence Badge */
            .confidence-badge {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            .confidence-badge.high {
                background: rgba(34, 197, 94, 0.2);
                color: var(--success);
            }
            .confidence-badge.medium {
                background: rgba(245, 158, 11, 0.2);
                color: var(--warning);
            }
            .confidence-badge.low {
                background: rgba(239, 68, 68, 0.2);
                color: var(--danger);
            }

            /* Responsive */
            @media (max-width: 1024px) {
                .stats-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
                .footer-grid {
                    grid-template-columns: 1fr;
                }
            }
            @media (max-width: 768px) {
                .tool-title { font-size: 1.8rem; }
                .stats-grid { grid-template-columns: 1fr 1fr; }
                .stat-value { font-size: 2rem; }
                .data-table { font-size: 13px; }
                .section-body { padding: 15px; overflow-x: auto; }
            }
            @media (max-width: 480px) {
                .stats-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <!-- Header -->
        <header class="site-header">
            <div class="header-container">
                <a href="/" class="logo">
                    <span class="logo-icon-wrapper">
                        <img src="/static/images/web3fuel-logo.svg" alt="Web3Fuel Logo" class="logo-icon logo-default">
                        <img src="/static/images/web3fuel-logo-neon.svg" alt="Web3Fuel Logo" class="logo-icon logo-neon">
                    </span>
                    <span class="logo-text">Web3Fuel.io</span>
                </a>
                <nav class="nav-desktop">
                    <a href="/research" class="nav-link">Research</a>
                    <a href="/tools" class="nav-link active">Tools</a>
                    <a href="/about" class="nav-link">About</a>
                    <a href="/contact" class="nav-link">Contact</a>
                </nav>
                <button class="menu-button" id="menu-button">☰</button>
            </div>
            <div class="mobile-menu" id="mobile-menu">
                <button class="close-menu" id="close-menu">✕</button>
                <a href="/research" class="mobile-nav-link">Research</a>
                <a href="/tools" class="mobile-nav-link">Tools</a>
                <a href="/about" class="mobile-nav-link">About</a>
                <a href="/contact" class="mobile-nav-link">Contact</a>
            </div>
        </header>

        <div class="main-container">
            <!-- Tool Header -->
            <div class="tool-header">
                <h1 class="tool-title">Polymarket Spike Monitor</h1>
                <p class="tool-tagline">Detecting unusual orderbook activity that may indicate insider trading</p>
                <div class="status-badge operational" id="status-badge">
                    <span class="status-dot"></span>
                    <span id="status-text">Loading...</span>
                </div>
            </div>

            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📊</div>
                    <div class="stat-value" id="stat-markets">-</div>
                    <div class="stat-label">Markets Tracked</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🔥</div>
                    <div class="stat-value" id="stat-spikes-24h">-</div>
                    <div class="stat-label">Spikes (24h)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📈</div>
                    <div class="stat-value" id="stat-spikes-7d">-</div>
                    <div class="stat-label">Spikes (7 Days)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🕐</div>
                    <div class="stat-value" id="stat-last-update">-</div>
                    <div class="stat-label">Minutes Ago</div>
                </div>
            </div>

            <!-- Today's Summary by Type -->
            <div class="today-summary" id="today-summary">
                <div class="summary-item">
                    <div class="summary-icon">📊</div>
                    <div class="summary-info">
                        <div class="summary-count" id="today-bid">-</div>
                        <div class="summary-label">Bid Spikes</div>
                    </div>
                </div>
                <div class="summary-item">
                    <div class="summary-icon">📉</div>
                    <div class="summary-info">
                        <div class="summary-count" id="today-ask">-</div>
                        <div class="summary-label">Ask Spikes</div>
                    </div>
                </div>
                <div class="summary-item">
                    <div class="summary-icon">📈</div>
                    <div class="summary-info">
                        <div class="summary-count" id="today-momentum">-</div>
                        <div class="summary-label">Momentum</div>
                    </div>
                </div>
                <div class="summary-item">
                    <div class="summary-icon">🔗</div>
                    <div class="summary-info">
                        <div class="summary-count" id="today-correlation">-</div>
                        <div class="summary-label">Arbitrage</div>
                    </div>
                </div>
            </div>

            <!-- Alert Type Legend -->
            <div class="alert-legend">
                <div class="legend-item">
                    <span class="legend-dot bid"></span>
                    <span>Bid Spike (Whale buying)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot ask"></span>
                    <span>Ask Spike (Whale selling)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot momentum-up"></span>
                    <span>Price Up (Bullish momentum)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot momentum-down"></span>
                    <span>Price Down (Bearish momentum)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot correlation"></span>
                    <span>Arbitrage (Correlation divergence)</span>
                </div>
            </div>

            <!-- Spike Frequency Chart -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Spike Frequency (Last 7 Days)</h2>
                </div>
                <div class="section-body">
                    <div class="chart-container" id="frequency-chart">
                        <div class="loading">
                            <div class="loading-spinner"></div>
                            Loading chart...
                        </div>
                    </div>
                </div>
            </div>

            <!-- Recent Spikes -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Recent Alerts</h2>
                </div>
                <div class="section-body">
                    <div class="filter-buttons" id="filter-buttons">
                        <button class="filter-btn active" data-filter="all">All <span class="count" id="filter-count-all">0</span></button>
                        <button class="filter-btn" data-filter="orderbook_bid_depth">Bid <span class="count" id="filter-count-bid">0</span></button>
                        <button class="filter-btn" data-filter="orderbook_ask_depth">Ask <span class="count" id="filter-count-ask">0</span></button>
                        <button class="filter-btn" data-filter="price_momentum">Momentum <span class="count" id="filter-count-momentum">0</span></button>
                        <button class="filter-btn" data-filter="correlation">Arbitrage <span class="count" id="filter-count-correlation">0</span></button>
                    </div>
                    <div id="spikes-table">
                        <div class="loading">
                            <div class="loading-spinner"></div>
                            Loading alerts...
                        </div>
                    </div>
                </div>
            </div>

            <!-- Pattern Analysis -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Pattern Analysis (30 Days)</h2>
                </div>
                <div class="section-body">
                    <div id="pattern-stats">
                        <div class="loading">
                            <div class="loading-spinner"></div>
                            Loading patterns...
                        </div>
                    </div>
                </div>
            </div>

            <!-- Market Health -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Market Health Indicators</h2>
                </div>
                <div class="section-body">
                    <div id="market-health">
                        <div class="loading">
                            <div class="loading-spinner"></div>
                            Loading market health...
                        </div>
                    </div>
                </div>
            </div>

            <!-- Active Markets -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Top Monitored Markets</h2>
                </div>
                <div class="section-body">
                    <div id="markets-list">
                        <div class="loading">
                            <div class="loading-spinner"></div>
                            Loading markets...
                        </div>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="tool-footer">
                <div class="footer-grid">
                    <div class="footer-section">
                        <h4>How It Works</h4>
                        <p>
                            This tool monitors Polymarket with three detection types:<br><br>
                            <strong>Orderbook Spikes:</strong> Bid/ask depth exceeds 3x baseline (whale activity).<br>
                            <strong>Price Momentum:</strong> Odds shift 10+ percentage points (news/sentiment).<br>
                            <strong>Correlation Arbitrage:</strong> Related markets diverge unexpectedly.
                            <br><br>Each alert includes <strong>AI-powered analysis</strong> with news context.
                        </p>
                    </div>
                    <div class="footer-section">
                        <h4>Tech Stack</h4>
                        <div>
                            <span class="tech-tag">Python</span>
                            <span class="tech-tag">MySQL</span>
                            <span class="tech-tag">Flask</span>
                            <span class="tech-tag">Polymarket API</span>
                            <span class="tech-tag">Claude API</span>
                            <span class="tech-tag">Discord Webhooks</span>
                            <span class="tech-tag">Cron</span>
                        </div>
                    </div>
                    <div class="footer-section">
                        <h4>Links</h4>
                        <ul>
                            <li><a href="https://polymarket.com" target="_blank">Polymarket</a></li>
                            <li><a href="/tools">All Tools</a></li>
                            <li><a href="/contact">Contact</a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Mobile Menu Toggle
            const menuButton = document.getElementById('menu-button');
            const mobileMenu = document.getElementById('mobile-menu');
            const closeMenu = document.getElementById('close-menu');

            if (menuButton && mobileMenu) {
                menuButton.addEventListener('click', () => {
                    mobileMenu.classList.add('active');
                    document.body.style.overflow = 'hidden';
                });
                closeMenu.addEventListener('click', () => {
                    mobileMenu.classList.remove('active');
                    document.body.style.overflow = 'auto';
                });
            }

            // Load Stats
            async function loadStats() {
                try {
                    const response = await fetch('/tools/polymarket-monitor/api/stats');
                    const stats = await response.json();

                    document.getElementById('stat-markets').textContent = stats.total_markets.toLocaleString();
                    document.getElementById('stat-spikes-24h').textContent = stats.spikes_24h;
                    document.getElementById('stat-spikes-7d').textContent = stats.spikes_7d;

                    if (stats.last_update_minutes >= 0) {
                        document.getElementById('stat-last-update').textContent = stats.last_update_minutes;
                    } else {
                        document.getElementById('stat-last-update').textContent = 'N/A';
                    }

                    // Update status badge
                    const badge = document.getElementById('status-badge');
                    const statusText = document.getElementById('status-text');
                    badge.className = 'status-badge ' + stats.status;

                    if (stats.status === 'operational') {
                        statusText.textContent = 'Operational';
                    } else if (stats.status === 'warning') {
                        statusText.textContent = 'Delayed';
                    } else {
                        statusText.textContent = 'Offline';
                    }
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }

            // Load Frequency Chart
            async function loadFrequencyChart() {
                try {
                    const response = await fetch('/tools/polymarket-monitor/api/frequency');
                    const frequency = await response.json();

                    const maxCount = Math.max(...frequency.map(d => d.count), 1);

                    let html = '';
                    frequency.forEach(day => {
                        const height = (day.count / maxCount) * 150 + 4;
                        html += `
                            <div class="chart-bar-wrapper">
                                <div class="chart-bar" style="height: ${height}px"></div>
                                <div class="chart-label">${day.day}</div>
                                <div class="chart-count">${day.count}</div>
                            </div>
                        `;
                    });

                    document.getElementById('frequency-chart').innerHTML = html;
                } catch (error) {
                    console.error('Error loading frequency:', error);
                    document.getElementById('frequency-chart').innerHTML = '<div class="empty-state">Failed to load chart</div>';
                }
            }

            // Global spikes data for filtering
            let allSpikes = [];
            let currentFilter = 'all';

            // Load Spikes Table
            async function loadSpikes() {
                try {
                    const response = await fetch('/tools/polymarket-monitor/api/spikes');
                    allSpikes = await response.json();

                    // Update today's summary counts
                    updateTodaySummary(allSpikes);

                    // Update filter counts
                    updateFilterCounts(allSpikes);

                    // Render table with current filter
                    renderSpikesTable(allSpikes, currentFilter);

                } catch (error) {
                    console.error('Error loading spikes:', error);
                    document.getElementById('spikes-table').innerHTML = '<div class="empty-state">Failed to load alerts</div>';
                }
            }

            // Update today's summary counts
            function updateTodaySummary(spikes) {
                const today = new Date().toISOString().split('T')[0];
                const todaySpikes = spikes.filter(s => s.detected_at && s.detected_at.startsWith(today));

                const counts = {
                    bid: todaySpikes.filter(s => s.metric_type === 'orderbook_bid_depth').length,
                    ask: todaySpikes.filter(s => s.metric_type === 'orderbook_ask_depth').length,
                    momentum: todaySpikes.filter(s => s.metric_type === 'price_momentum').length,
                    correlation: todaySpikes.filter(s => s.metric_type === 'correlation').length
                };

                document.getElementById('today-bid').textContent = counts.bid;
                document.getElementById('today-ask').textContent = counts.ask;
                document.getElementById('today-momentum').textContent = counts.momentum;
                document.getElementById('today-correlation').textContent = counts.correlation;
            }

            // Update filter button counts
            function updateFilterCounts(spikes) {
                document.getElementById('filter-count-all').textContent = spikes.length;
                document.getElementById('filter-count-bid').textContent = spikes.filter(s => s.metric_type === 'orderbook_bid_depth').length;
                document.getElementById('filter-count-ask').textContent = spikes.filter(s => s.metric_type === 'orderbook_ask_depth').length;
                document.getElementById('filter-count-momentum').textContent = spikes.filter(s => s.metric_type === 'price_momentum').length;
                document.getElementById('filter-count-correlation').textContent = spikes.filter(s => s.metric_type === 'correlation').length;
            }

            // Render spikes table with filter
            function renderSpikesTable(spikes, filter) {
                const filteredSpikes = filter === 'all' ? spikes : spikes.filter(s => s.metric_type === filter);

                if (filteredSpikes.length === 0) {
                    document.getElementById('spikes-table').innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">🔍</div>
                            <p>${filter === 'all' ? 'No alerts detected yet.' : 'No alerts of this type.'}</p>
                        </div>
                    `;
                    return;
                }

                let html = `
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Market</th>
                                <th>Type</th>
                                <th>Change</th>
                                <th>Baseline</th>
                                <th>Current</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                filteredSpikes.forEach(spike => {
                    const question = spike.question ?
                        (spike.question.length > 50 ? spike.question.substring(0, 50) + '...' : spike.question) :
                        'Unknown';

                    // Determine metric type and formatting
                    let metricClass, metricLabel, ratioDisplay, baselineDisplay, currentDisplay;

                    if (spike.metric_type === 'correlation') {
                        metricClass = 'correlation';
                        metricLabel = '🔗 ARB';
                        ratioDisplay = `${(spike.spike_ratio * 100).toFixed(1)}pp`;
                        baselineDisplay = `${(spike.baseline_value * 100).toFixed(1)}%`;
                        currentDisplay = `${(spike.current_value * 100).toFixed(1)}%`;
                    } else if (spike.metric_type === 'price_momentum') {
                        const changePct = spike.spike_ratio * 100;
                        const isUp = spike.current_value > spike.baseline_value;
                        metricClass = isUp ? 'momentum-up' : 'momentum-down';
                        metricLabel = isUp ? '📈 UP' : '📉 DOWN';
                        ratioDisplay = `${isUp ? '+' : '-'}${changePct.toFixed(1)}pp`;
                        baselineDisplay = `${(spike.baseline_value * 100).toFixed(1)}%`;
                        currentDisplay = `${(spike.current_value * 100).toFixed(1)}%`;
                    } else {
                        const isBid = spike.metric_type.includes('bid');
                        metricClass = isBid ? 'bid' : 'ask';
                        metricLabel = isBid ? 'BID' : 'ASK';
                        ratioDisplay = `${spike.spike_ratio.toFixed(1)}x`;
                        baselineDisplay = `$${spike.baseline_value.toLocaleString(undefined, {maximumFractionDigits: 0})}`;
                        currentDisplay = `$${spike.current_value.toLocaleString(undefined, {maximumFractionDigits: 0})}`;
                    }

                    html += `
                        <tr data-type="${spike.metric_type}">
                            <td>${spike.detected_at}</td>
                            <td>
                                ${spike.slug ?
                                    `<a href="https://polymarket.com/event/${spike.slug}" target="_blank" class="market-link">${question}</a>` :
                                    question
                                }
                            </td>
                            <td><span class="metric-badge ${metricClass}">${metricLabel}</span></td>
                            <td><span class="spike-ratio">${ratioDisplay}</span></td>
                            <td>${baselineDisplay}</td>
                            <td>${currentDisplay}</td>
                        </tr>
                    `;
                });

                html += '</tbody></table>';
                document.getElementById('spikes-table').innerHTML = html;
            }

            // Filter button click handlers
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    // Update active state
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    // Apply filter
                    currentFilter = btn.dataset.filter;
                    renderSpikesTable(allSpikes, currentFilter);
                });
            });

            // Load Markets List
            async function loadMarkets() {
                try {
                    const response = await fetch('/tools/polymarket-monitor/api/markets');
                    const markets = await response.json();

                    if (markets.length === 0) {
                        document.getElementById('markets-list').innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">📊</div>
                                <p>No markets being monitored yet. Run the collector to start.</p>
                            </div>
                        `;
                        return;
                    }

                    let html = '';
                    markets.forEach(market => {
                        const question = market.question ?
                            (market.question.length > 60 ? market.question.substring(0, 60) + '...' : market.question) :
                            'Unknown';

                        html += `
                            <div class="market-item">
                                <div class="market-question">
                                    ${market.slug ?
                                        `<a href="https://polymarket.com/event/${market.slug}" target="_blank" class="market-link">${question}</a>` :
                                        question
                                    }
                                </div>
                                <div class="market-stats">
                                    <div class="market-stat">
                                        <span>📸</span>
                                        <span>${market.snapshot_count} snapshots</span>
                                    </div>
                                    <div class="market-stat">
                                        <span>💰</span>
                                        <span>$${Math.round(market.avg_bid_depth).toLocaleString()} avg depth</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    });

                    document.getElementById('markets-list').innerHTML = html;
                } catch (error) {
                    console.error('Error loading markets:', error);
                    document.getElementById('markets-list').innerHTML = '<div class="empty-state">Failed to load markets</div>';
                }
            }

            // Load Pattern Analysis
            async function loadPatterns() {
                try {
                    const response = await fetch('/tools/polymarket-monitor/api/patterns');
                    const patterns = await response.json();

                    if (patterns.error) {
                        document.getElementById('pattern-stats').innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">📊</div>
                                <p>Pattern analysis requires spike alert history.</p>
                            </div>
                        `;
                        return;
                    }

                    // Determine accuracy class
                    const getAccuracyClass = (acc) => {
                        if (acc >= 65) return 'high';
                        if (acc >= 50) return 'medium';
                        return 'low';
                    };

                    let html = `
                        <div class="overall-accuracy">
                            <div class="overall-label">Overall Prediction Accuracy</div>
                            <div class="overall-value">${patterns.overall.accuracy}%</div>
                            <div class="overall-subtitle">${patterns.overall.correct} correct out of ${patterns.overall.total} predictions</div>
                        </div>
                        <div class="pattern-grid">
                    `;

                    patterns.by_type.forEach(pattern => {
                        const accClass = getAccuracyClass(pattern.accuracy);
                        html += `
                            <div class="pattern-card">
                                <div class="pattern-type">${pattern.type}</div>
                                <div class="pattern-accuracy ${accClass}">${pattern.accuracy}%</div>
                                <div class="pattern-samples">${pattern.correct}/${pattern.total} correct</div>
                            </div>
                        `;
                    });

                    html += '</div>';

                    document.getElementById('pattern-stats').innerHTML = html;
                } catch (error) {
                    console.error('Error loading patterns:', error);
                    document.getElementById('pattern-stats').innerHTML = '<div class="empty-state">Failed to load pattern analysis</div>';
                }
            }

            // Load Market Health
            async function loadMarketHealth() {
                try {
                    const response = await fetch('/tools/polymarket-monitor/api/market-health');
                    const markets = await response.json();

                    if (!markets.length) {
                        document.getElementById('market-health').innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">📊</div>
                                <p>No active markets to analyze.</p>
                            </div>
                        `;
                        return;
                    }

                    let html = '<div class="health-grid">';

                    markets.forEach(market => {
                        const totalDepth = (market.bid_depth || 0) + (market.ask_depth || 0);
                        const bidPct = totalDepth > 0 ? ((market.bid_depth || 0) / totalDepth * 100) : 50;
                        const askPct = 100 - bidPct;

                        const imbalanceClass = market.imbalance_direction === 'bullish' ? 'bullish' :
                                              market.imbalance_direction === 'bearish' ? 'bearish' : 'neutral';

                        html += `
                            <div class="health-card">
                                <div class="health-card-header">
                                    <div class="health-card-title">
                                        ${market.slug ?
                                            `<a href="https://polymarket.com/event/${market.slug}" target="_blank">${market.question}</a>` :
                                            market.question
                                        }
                                    </div>
                                    <div class="health-card-price">${market.current_price}%</div>
                                </div>
                                <div class="health-card-indicators">
                                    <div class="health-indicator ${imbalanceClass}">
                                        ${market.imbalance_direction === 'bullish' ? '📈' : market.imbalance_direction === 'bearish' ? '📉' : '➖'}
                                        ${market.imbalance_ratio}:1 ${market.imbalance_direction}
                                    </div>
                                    <div class="health-indicator neutral">
                                        💰 $${market.bid_depth.toLocaleString()} bid
                                    </div>
                                    <div class="health-indicator neutral">
                                        📉 $${market.ask_depth.toLocaleString()} ask
                                    </div>
                                </div>
                                <div class="depth-bar-container">
                                    <span class="depth-label">Bid ${bidPct.toFixed(0)}%</span>
                                    <div class="depth-bar">
                                        <div class="depth-bar-bid" style="width: ${bidPct}%"></div>
                                        <div class="depth-bar-ask" style="width: ${askPct}%"></div>
                                    </div>
                                    <span class="depth-label">Ask ${askPct.toFixed(0)}%</span>
                                </div>
                            </div>
                        `;
                    });

                    html += '</div>';
                    document.getElementById('market-health').innerHTML = html;

                } catch (error) {
                    console.error('Error loading market health:', error);
                    document.getElementById('market-health').innerHTML = '<div class="empty-state">Failed to load market health</div>';
                }
            }

            // Load all data on page load
            document.addEventListener('DOMContentLoaded', () => {
                loadStats();
                loadFrequencyChart();
                loadSpikes();
                loadMarkets();
                loadPatterns();
                loadMarketHealth();

                // Refresh every 5 minutes
                setInterval(() => {
                    loadStats();
                    loadFrequencyChart();
                    loadSpikes();
                    loadMarkets();
                    loadPatterns();
                    loadMarketHealth();
                }, 5 * 60 * 1000);
            });
        </script>
    </body>
    </html>
    """

    return render_template_string(html)
