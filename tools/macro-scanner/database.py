"""
Database module for Macro Scanner.
Handles MySQL connection and schema management.
"""

import json
import mysql.connector
from mysql.connector import Error
import logging
from config import (
    DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT,
    DEEP_DIVE_EXPIRY_HOURS, OUTCOME_RESOLUTION_DAYS, OUTCOME_BREAKEVEN_PCT
)

logger = logging.getLogger(__name__)


def get_connection():
    """Create and return a MySQL database connection."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL: {e}")
        raise


def init_database():
    """Initialize database schema. Creates tables if they don't exist."""
    connection = None
    cursor = None

    try:
        # First connect without database to create it if needed
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = connection.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")

        # Create scan_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_top10 JSON,
                filtered_top3 JSON,
                deep_research TEXT,
                indicators JSON,
                scan_duration_seconds DECIMAL(8,2),
                INDEX idx_scanned_at (scanned_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Create trade_alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_id INT NOT NULL,
                alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                top_stories JSON,
                narrative TEXT,
                trade_idea TEXT,
                confidence INT DEFAULT 1,
                notified BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (scan_id) REFERENCES scan_results(id) ON DELETE CASCADE,
                INDEX idx_scan_id (scan_id),
                INDEX idx_alerted_at (alerted_at),
                INDEX idx_notified (notified),
                INDEX idx_confidence (confidence)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Create deep_dive_queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deep_dive_queue (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_id INT,
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('pending','in_progress','completed','expired','failed') DEFAULT 'pending',
                headline VARCHAR(500) NOT NULL,
                rationale TEXT,
                direction VARCHAR(20),
                sectors JSON,
                key_instruments JSON,
                impact_score INT,
                source_url VARCHAR(1000),
                deep_research TEXT,
                completed_at TIMESTAMP NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scan_results(id) ON DELETE SET NULL,
                INDEX idx_status (status),
                INDEX idx_expires_at (expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Create trade_outcomes table (feedback loop)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_outcomes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                alert_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ticker VARCHAR(20) NOT NULL,
                direction VARCHAR(10) NOT NULL,
                entry_price DECIMAL(12,4),
                target_price DECIMAL(12,4),
                stop_price DECIMAL(12,4),
                setup_grade VARCHAR(5),
                confidence INT,
                expires_at TIMESTAMP NOT NULL,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at TIMESTAMP NULL,
                outcome ENUM('win','loss','breakeven','expired') NULL,
                exit_price DECIMAL(12,4) NULL,
                pct_move DECIMAL(8,4) NULL,
                FOREIGN KEY (alert_id) REFERENCES trade_alerts(id) ON DELETE CASCADE,
                INDEX idx_resolved (resolved),
                INDEX idx_setup_grade (setup_grade),
                INDEX idx_expires_at (expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Create active_positions table (position tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_positions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) DEFAULT 'default',
                alert_id INT NULL,
                ticker VARCHAR(20) NOT NULL,
                direction VARCHAR(10) NOT NULL,
                entry_price DECIMAL(12,4),
                entry_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                target_price DECIMAL(12,4),
                stop_loss DECIMAL(12,4),
                status ENUM('open','closed','stopped_out','target_hit','expired') DEFAULT 'open',
                exit_price DECIMAL(12,4) NULL,
                exit_date TIMESTAMP NULL,
                thesis TEXT,
                notes TEXT,
                FOREIGN KEY (alert_id) REFERENCES trade_alerts(id) ON DELETE SET NULL,
                INDEX idx_user_status (user_id, status),
                INDEX idx_ticker (ticker),
                INDEX idx_alert_id (alert_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        connection.commit()
        logger.info("Database schema initialized successfully")

    except Error as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_scan_result(scan_data):
    """
    Insert a scan result record.

    Args:
        scan_data: dict with keys: raw_top10, filtered_top3, deep_research,
                   indicators, scan_duration_seconds

    Returns:
        scan_id or None on failure
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        raw_top10 = scan_data.get('raw_top10')
        if isinstance(raw_top10, (dict, list)):
            raw_top10 = json.dumps(raw_top10)

        filtered_top3 = scan_data.get('filtered_top3')
        if isinstance(filtered_top3, (dict, list)):
            filtered_top3 = json.dumps(filtered_top3)

        indicators = scan_data.get('indicators')
        if isinstance(indicators, (dict, list)):
            indicators = json.dumps(indicators)

        query = """
            INSERT INTO scan_results (raw_top10, filtered_top3, deep_research,
                                      indicators, scan_duration_seconds)
            VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            raw_top10,
            filtered_top3,
            scan_data.get('deep_research'),
            indicators,
            scan_data.get('scan_duration_seconds')
        ))

        connection.commit()
        scan_id = cursor.lastrowid
        logger.info(f"Inserted scan result {scan_id}")
        return scan_id

    except Error as e:
        logger.error(f"Error inserting scan result: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_trade_alert(alert_data):
    """
    Insert a trade alert record.

    Args:
        alert_data: dict with keys: scan_id, top_stories, narrative,
                    trade_idea, confidence

    Returns:
        alert_id or None on failure
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        top_stories = alert_data.get('top_stories')
        if isinstance(top_stories, (dict, list)):
            top_stories = json.dumps(top_stories)

        query = """
            INSERT INTO trade_alerts (scan_id, top_stories, narrative,
                                      trade_idea, confidence)
            VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            alert_data['scan_id'],
            top_stories,
            alert_data.get('narrative'),
            alert_data.get('trade_idea'),
            alert_data.get('confidence', 1)
        ))

        connection.commit()
        alert_id = cursor.lastrowid
        logger.info(f"Inserted trade alert {alert_id} for scan {alert_data['scan_id']}")
        return alert_id

    except Error as e:
        logger.error(f"Error inserting trade alert: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def mark_alert_notified(alert_id):
    """
    Mark a trade alert as notified (Discord notification sent successfully).

    Args:
        alert_id: The alert ID to mark as notified

    Returns:
        True if updated successfully, False otherwise
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE trade_alerts SET notified = TRUE WHERE id = %s",
            (alert_id,)
        )

        connection.commit()
        logger.debug(f"Marked alert {alert_id} as notified")
        return cursor.rowcount > 0

    except Error as e:
        logger.error(f"Error marking alert {alert_id} as notified: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_recent_scans(hours=24):
    """
    Get recent scan results.

    Args:
        hours: Number of hours to look back (default 24)

    Returns:
        List of scan result dicts
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM scan_results
            WHERE scanned_at >= NOW() - INTERVAL %s HOUR
            ORDER BY scanned_at DESC
        """, (hours,))

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error fetching recent scans: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_recent_alerts(hours=24):
    """
    Get recent trade alerts.

    Args:
        hours: Number of hours to look back (default 24)

    Returns:
        List of alert dicts
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT ta.*, sr.scanned_at, sr.indicators
            FROM trade_alerts ta
            LEFT JOIN scan_results sr ON ta.scan_id = sr.id
            WHERE ta.alerted_at >= NOW() - INTERVAL %s HOUR
            ORDER BY ta.alerted_at DESC
        """, (hours,))

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error fetching recent alerts: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def queue_deep_dive(item, scan_id=None):
    """
    Insert an item into the deep_dive_queue as pending.

    Args:
        item: Dict with headline, rationale, direction, affected_sectors,
              key_instruments, impact_score, url
        scan_id: Optional scan_results ID that found this item

    Returns:
        queue_id or None on failure
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        sectors = item.get('affected_sectors', item.get('sectors', []))
        if isinstance(sectors, (list, dict)):
            sectors = json.dumps(sectors)

        instruments = item.get('key_instruments', [])
        if isinstance(instruments, (list, dict)):
            instruments = json.dumps(instruments)

        query = """
            INSERT INTO deep_dive_queue
                (scan_id, headline, rationale, direction, sectors,
                 key_instruments, impact_score, source_url, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    NOW() + INTERVAL %s HOUR)
        """

        cursor.execute(query, (
            scan_id,
            item.get('headline', 'Unknown')[:500],
            item.get('rationale', ''),
            item.get('direction', 'mixed'),
            sectors,
            instruments,
            item.get('impact_score', 5),
            item.get('url', item.get('source_url', ''))[:1000],
            DEEP_DIVE_EXPIRY_HOURS
        ))

        connection.commit()
        queue_id = cursor.lastrowid
        logger.info(f"Queued deep dive {queue_id}: {item.get('headline', '')[:80]}")
        return queue_id

    except Error as e:
        logger.error(f"Error queuing deep dive: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_pending_deep_dives():
    """
    Get pending deep-dive items. Expires stale items first.

    Returns:
        List of pending queue item dicts, sorted by impact_score desc
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Expire stale items
        cursor.execute("""
            UPDATE deep_dive_queue
            SET status = 'expired'
            WHERE status = 'pending' AND expires_at < NOW()
        """)
        expired = cursor.rowcount
        if expired:
            logger.info(f"Expired {expired} stale deep-dive items")

        connection.commit()

        # Fetch remaining pending items
        cursor.execute("""
            SELECT id, scan_id, queued_at, headline, rationale, direction,
                   sectors, key_instruments, impact_score, source_url, expires_at
            FROM deep_dive_queue
            WHERE status = 'pending'
            ORDER BY impact_score DESC
        """)

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error fetching pending deep dives: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_deep_dive(queue_id, status, deep_research=None):
    """
    Update a deep-dive queue item's status and optionally store research results.

    Args:
        queue_id: The queue item ID
        status: New status (in_progress, completed, failed)
        deep_research: Optional research text to store

    Returns:
        True if updated, False otherwise
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        if deep_research and status == 'completed':
            cursor.execute("""
                UPDATE deep_dive_queue
                SET status = %s, deep_research = %s, completed_at = NOW()
                WHERE id = %s
            """, (status, deep_research, queue_id))
        else:
            cursor.execute("""
                UPDATE deep_dive_queue
                SET status = %s
                WHERE id = %s
            """, (status, queue_id))

        connection.commit()
        logger.info(f"Updated deep dive {queue_id} -> {status}")
        return cursor.rowcount > 0

    except Error as e:
        logger.error(f"Error updating deep dive {queue_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Trade Outcomes (Feedback Loop)
# =============================================================================

def _parse_price_string(price_str, ticker):
    """
    Extract a dollar price for a specific ticker from strings like:
      "XLE: $89.50; OXY: $52.10"
      "XLE: at market ($89.50)"
      "$89.50"

    Returns:
        float or None
    """
    if not price_str:
        return None

    import re

    # Try ticker-specific pattern first: "TICKER: $XX.XX" or "TICKER: at market ($XX.XX)"
    pattern = rf'{re.escape(ticker)}[^$]*\$(\d+(?:\.\d+)?)'
    match = re.search(pattern, str(price_str), re.IGNORECASE)
    if match:
        return float(match.group(1))

    # Fallback: if only one ticker mentioned, grab any dollar amount
    dollar_matches = re.findall(r'\$(\d+(?:\.\d+)?)', str(price_str))
    if len(dollar_matches) == 1:
        return float(dollar_matches[0])

    return None


def auto_create_outcomes(alert_id, trade_data, setup_grade, confidence):
    """
    Auto-create trade_outcomes rows from alert trade data.
    Called when confidence >= 2 and tickers exist.

    Args:
        alert_id: The trade_alerts.id
        trade_data: Dict with tickers, direction, entry, target, stop_loss
        setup_grade: Grade string (A+, A, B+, B, C)
        confidence: Int 0-5

    Returns:
        Count of outcomes created
    """
    tickers = trade_data.get('tickers', [])
    if not tickers:
        return 0

    direction = trade_data.get('direction', 'long')
    entry_str = trade_data.get('entry', '')
    target_str = trade_data.get('target', '')
    stop_str = trade_data.get('stop_loss', '')

    count = 0
    for ticker in tickers:
        entry_price = _parse_price_string(entry_str, ticker)
        target_price = _parse_price_string(target_str, ticker)
        stop_price = _parse_price_string(stop_str, ticker)

        if entry_price is None:
            logger.warning(f"Could not parse entry price for {ticker}, skipping outcome")
            continue

        oid = insert_trade_outcome(
            alert_id=alert_id,
            ticker=ticker,
            direction=direction,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            setup_grade=setup_grade,
            confidence=confidence
        )
        if oid:
            count += 1

    logger.info(f"Created {count} trade outcome(s) for alert {alert_id}")
    return count


def insert_trade_outcome(alert_id, ticker, direction, entry_price,
                         target_price, stop_price, setup_grade, confidence):
    """Insert a single trade_outcomes row."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO trade_outcomes
                (alert_id, ticker, direction, entry_price, target_price,
                 stop_price, setup_grade, confidence, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    NOW() + INTERVAL %s DAY)
        """, (
            alert_id, ticker, direction, entry_price, target_price,
            stop_price, setup_grade, confidence, OUTCOME_RESOLUTION_DAYS
        ))

        connection.commit()
        oid = cursor.lastrowid
        logger.debug(f"Inserted trade outcome {oid}: {direction} {ticker} @ ${entry_price}")
        return oid

    except Error as e:
        logger.error(f"Error inserting trade outcome: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_unresolved_outcomes():
    """Return all unresolved trade_outcomes rows, ordered by expires_at."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, alert_id, created_at, ticker, direction,
                   entry_price, target_price, stop_price,
                   setup_grade, confidence, expires_at
            FROM trade_outcomes
            WHERE resolved = FALSE
            ORDER BY expires_at ASC
        """)

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error fetching unresolved outcomes: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def resolve_outcome(outcome_id, outcome, exit_price, pct_move):
    """Mark a trade outcome as resolved."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE trade_outcomes
            SET resolved = TRUE, resolved_at = NOW(),
                outcome = %s, exit_price = %s, pct_move = %s
            WHERE id = %s
        """, (outcome, exit_price, pct_move, outcome_id))

        connection.commit()
        logger.info(f"Resolved outcome {outcome_id}: {outcome} (exit ${exit_price}, move {pct_move:+.2f}%)")
        return cursor.rowcount > 0

    except Error as e:
        logger.error(f"Error resolving outcome {outcome_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_accuracy_by_grade(days=90):
    """
    Aggregate trade outcome accuracy by setup grade over the last N days.

    Returns:
        Dict of {grade: {total, wins, losses, breakevens, win_rate, avg_move}}
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                setup_grade,
                COUNT(*) as total,
                SUM(outcome = 'win') as wins,
                SUM(outcome = 'loss') as losses,
                SUM(outcome = 'breakeven') as breakevens,
                AVG(pct_move) as avg_move
            FROM trade_outcomes
            WHERE resolved = TRUE
              AND resolved_at >= NOW() - INTERVAL %s DAY
              AND setup_grade IS NOT NULL
            GROUP BY setup_grade
            ORDER BY setup_grade
        """, (days,))

        results = {}
        for row in cursor.fetchall():
            grade = row['setup_grade']
            total = row['total']
            wins = int(row['wins'] or 0)
            results[grade] = {
                'total': total,
                'wins': wins,
                'losses': int(row['losses'] or 0),
                'breakevens': int(row['breakevens'] or 0),
                'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
                'avg_move': round(float(row['avg_move'] or 0), 2)
            }

        return results

    except Error as e:
        logger.error(f"Error fetching accuracy by grade: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def cleanup_trade_outcomes(days=90):
    """Delete old resolved trade outcomes."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM trade_outcomes
            WHERE resolved = TRUE
              AND resolved_at < NOW() - INTERVAL %s DAY
        """, (days,))

        deleted_count = cursor.rowcount
        connection.commit()
        logger.info(f"Cleaned up {deleted_count} trade outcomes older than {days} days")
        return deleted_count

    except Error as e:
        logger.error(f"Error cleaning up trade outcomes: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =============================================================================
# Active Positions (Position Tracking)
# =============================================================================

def enter_position_from_alert(alert_id, user_id='default'):
    """
    Create active position(s) from a trade alert's stored data.

    Args:
        alert_id: trade_alerts.id to read trade data from
        user_id: User identifier (default 'default')

    Returns:
        List of created position IDs, or empty list on failure
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Read the alert's top_stories JSON (contains trade data)
        cursor.execute(
            "SELECT top_stories, narrative FROM trade_alerts WHERE id = %s",
            (alert_id,)
        )
        row = cursor.fetchone()
        if not row:
            logger.error(f"Alert {alert_id} not found")
            return []

        trade_data = row['top_stories']
        if isinstance(trade_data, str):
            trade_data = json.loads(trade_data)

        tickers = trade_data.get('tickers', [])
        if not tickers:
            logger.error(f"Alert {alert_id} has no tickers")
            return []

        direction = trade_data.get('direction', 'long')
        entry_str = trade_data.get('entry', '')
        target_str = trade_data.get('target', '')
        stop_str = trade_data.get('stop_loss', '')
        thesis = trade_data.get('thesis', row.get('narrative', ''))

        position_ids = []
        for ticker in tickers:
            entry_price = _parse_price_string(entry_str, ticker)
            target_price = _parse_price_string(target_str, ticker)
            stop_price = _parse_price_string(stop_str, ticker)

            cursor.execute("""
                INSERT INTO active_positions
                    (user_id, alert_id, ticker, direction, entry_price,
                     target_price, stop_loss, thesis)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, alert_id, ticker, direction,
                entry_price, target_price, stop_price, thesis
            ))
            position_ids.append(cursor.lastrowid)
            logger.info(f"Created position: {direction} {ticker} @ ${entry_price} (alert {alert_id})")

        connection.commit()
        return position_ids

    except Error as e:
        logger.error(f"Error creating positions from alert {alert_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_active_positions(user_id='default'):
    """Return all open positions for a user."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, user_id, alert_id, ticker, direction, entry_price,
                   entry_date, target_price, stop_loss, status, thesis, notes
            FROM active_positions
            WHERE user_id = %s AND status = 'open'
            ORDER BY entry_date DESC
        """, (user_id,))

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error fetching active positions: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def close_position(position_id, exit_price=None, status='closed'):
    """
    Close an active position.

    Args:
        position_id: active_positions.id
        exit_price: Price at exit (if None, will need to be fetched externally)
        status: One of closed, stopped_out, target_hit, expired
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE active_positions
            SET status = %s, exit_price = %s, exit_date = NOW()
            WHERE id = %s AND status = 'open'
        """, (status, exit_price, position_id))

        connection.commit()
        logger.info(f"Closed position {position_id}: {status} @ ${exit_price}")
        return cursor.rowcount > 0

    except Error as e:
        logger.error(f"Error closing position {position_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def update_position_status(position_id, status, exit_price=None):
    """Update position status (used by resolver for auto stop/target hits)."""
    return close_position(position_id, exit_price=exit_price, status=status)


def cleanup_deep_dives(days=7):
    """
    Delete old completed/expired/failed deep-dive items.

    Args:
        days: Number of days to retain (default 7)

    Returns:
        Number of rows deleted
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM deep_dive_queue
            WHERE status IN ('completed', 'expired', 'failed')
              AND queued_at < NOW() - INTERVAL %s DAY
        """, (days,))

        deleted_count = cursor.rowcount
        connection.commit()

        logger.info(f"Cleaned up {deleted_count} deep-dive items older than {days} days")
        return deleted_count

    except Error as e:
        logger.error(f"Error cleaning up deep dives: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def cleanup_old_scans(days=30):
    """
    Delete scan results older than specified number of days.

    Args:
        days: Number of days to retain (default 30)

    Returns:
        Number of rows deleted
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM scan_results
            WHERE scanned_at < NOW() - INTERVAL %s DAY
        """, (days,))

        deleted_count = cursor.rowcount
        connection.commit()

        logger.info(f"Cleaned up {deleted_count} scans older than {days} days")
        return deleted_count

    except Error as e:
        logger.error(f"Error cleaning up old scans: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def cleanup_old_alerts(days=90):
    """
    Delete trade alerts older than specified number of days.

    Args:
        days: Number of days to retain (default 90)

    Returns:
        Number of rows deleted
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM trade_alerts
            WHERE alerted_at < NOW() - INTERVAL %s DAY
        """, (days,))

        deleted_count = cursor.rowcount
        connection.commit()

        logger.info(f"Cleaned up {deleted_count} alerts older than {days} days")
        return deleted_count

    except Error as e:
        logger.error(f"Error cleaning up old alerts: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def run_cleanup(scan_days=30, alert_days=90):
    """
    Run all cleanup tasks.

    Args:
        scan_days: Days to retain scans (default 30)
        alert_days: Days to retain alerts (default 90)
    """
    logger.info("Starting database cleanup...")

    scans_deleted = cleanup_old_scans(scan_days)
    alerts_deleted = cleanup_old_alerts(alert_days)
    dives_deleted = cleanup_deep_dives(days=7)
    outcomes_deleted = cleanup_trade_outcomes(days=alert_days)

    logger.info(
        f"Cleanup complete: {scans_deleted} scans, "
        f"{alerts_deleted} alerts, {dives_deleted} deep-dives, "
        f"{outcomes_deleted} outcomes removed"
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        print("Running database cleanup...")
        run_cleanup()
        print("Cleanup complete.")
    else:
        print("Initializing Macro Scanner database...")
        init_database()
        print("Database initialization complete.")
        print("\nTo run cleanup: python database.py cleanup")
