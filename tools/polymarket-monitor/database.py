"""
Database module for Polymarket Monitor.
Handles MySQL connection and schema management.
"""

import json
import mysql.connector
from mysql.connector import Error
import logging
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)


def get_connection():
    """Create and return a MySQL database connection."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
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
            password=DB_PASSWORD
        )
        cursor = connection.cursor()

        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")

        # Create markets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                market_id VARCHAR(255) PRIMARY KEY,
                event_id VARCHAR(255),
                question TEXT,
                slug VARCHAR(255),
                outcomes TEXT,
                clob_token_ids TEXT,
                category VARCHAR(100),
                end_date DATETIME NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_event_id (event_id),
                INDEX idx_active (active),
                INDEX idx_category (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Add end_date column if missing (for existing installs)
        try:
            cursor.execute("""
                ALTER TABLE markets ADD COLUMN end_date DATETIME NULL AFTER category
            """)
        except Error:
            pass  # Column already exists

        # Create market_snapshots table (time-series data)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                market_id VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                yes_price DECIMAL(5,4),
                no_price DECIMAL(5,4),
                orderbook_bid_depth DECIMAL(18,2),
                orderbook_ask_depth DECIMAL(18,2),
                FOREIGN KEY (market_id) REFERENCES markets(market_id) ON DELETE CASCADE,
                INDEX idx_market_timestamp (market_id, timestamp),
                INDEX idx_timestamp (timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Create spike_alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spike_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                market_id VARCHAR(255) NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metric_type VARCHAR(50),
                spike_ratio DECIMAL(6,2),
                baseline_value DECIMAL(18,2),
                current_value DECIMAL(18,2),
                notified BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (market_id) REFERENCES markets(market_id) ON DELETE CASCADE,
                INDEX idx_market_id (market_id),
                INDEX idx_detected_at (detected_at),
                INDEX idx_notified (notified)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Create ai_predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                market_id VARCHAR(255) NOT NULL,
                predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                suggested_play VARCHAR(20),
                grade VARCHAR(5),
                reasoning TEXT,
                key_signal VARCHAR(100),
                signals_json TEXT,
                market_price_at_prediction DECIMAL(5,4),
                market_end_date DATETIME NULL,
                resolved BOOLEAN DEFAULT FALSE,
                actual_outcome VARCHAR(10) NULL,
                prediction_correct BOOLEAN NULL,
                resolved_at TIMESTAMP NULL,
                alert_ids TEXT,
                FOREIGN KEY (market_id) REFERENCES markets(market_id) ON DELETE CASCADE,
                INDEX idx_market_id (market_id),
                INDEX idx_predicted_at (predicted_at),
                INDEX idx_resolved (resolved),
                INDEX idx_grade (grade)
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


def upsert_market(market_data):
    """
    Insert or update a market record.

    Args:
        market_data: dict with keys: market_id, event_id, question, slug,
                     outcomes, clob_token_ids, category, active
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO markets (market_id, event_id, question, slug, outcomes,
                                 clob_token_ids, category, end_date, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                event_id = VALUES(event_id),
                question = VALUES(question),
                slug = VALUES(slug),
                outcomes = VALUES(outcomes),
                clob_token_ids = VALUES(clob_token_ids),
                category = VALUES(category),
                end_date = COALESCE(VALUES(end_date), end_date),
                active = VALUES(active),
                updated_at = CURRENT_TIMESTAMP
        """

        cursor.execute(query, (
            market_data['market_id'],
            market_data.get('event_id'),
            market_data.get('question'),
            market_data.get('slug'),
            market_data.get('outcomes'),  # JSON string
            market_data.get('clob_token_ids'),  # JSON string
            market_data.get('category'),
            market_data.get('end_date'),
            market_data.get('active', True)
        ))

        connection.commit()
        logger.debug(f"Upserted market: {market_data['market_id']}")

    except Error as e:
        logger.error(f"Error upserting market {market_data.get('market_id')}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_snapshot(snapshot_data):
    """
    Insert a market snapshot record.

    Args:
        snapshot_data: dict with keys: market_id, yes_price, no_price,
                       orderbook_bid_depth, orderbook_ask_depth
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO market_snapshots (market_id, yes_price, no_price,
                                          orderbook_bid_depth, orderbook_ask_depth)
            VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            snapshot_data['market_id'],
            snapshot_data.get('yes_price'),
            snapshot_data.get('no_price'),
            snapshot_data.get('orderbook_bid_depth'),
            snapshot_data.get('orderbook_ask_depth')
        ))

        connection.commit()
        logger.debug(f"Inserted snapshot for market: {snapshot_data['market_id']}")

    except Error as e:
        logger.error(f"Error inserting snapshot for {snapshot_data.get('market_id')}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_alert(alert_data):
    """
    Insert a spike alert record.

    Args:
        alert_data: dict with keys: market_id, metric_type, spike_ratio,
                    baseline_value, current_value
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO spike_alerts (market_id, metric_type, spike_ratio,
                                      baseline_value, current_value)
            VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            alert_data['market_id'],
            alert_data.get('metric_type'),
            alert_data.get('spike_ratio'),
            alert_data.get('baseline_value'),
            alert_data.get('current_value')
        ))

        connection.commit()
        alert_id = cursor.lastrowid
        logger.info(f"Inserted alert {alert_id} for market: {alert_data['market_id']}")
        return alert_id

    except Error as e:
        logger.error(f"Error inserting alert for {alert_data.get('market_id')}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def mark_alert_notified(alert_id):
    """
    Mark a spike alert as notified (Discord notification sent successfully).

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
            "UPDATE spike_alerts SET notified = TRUE WHERE id = %s",
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


def get_market_by_id(market_id):
    """Retrieve a market record by its ID."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT * FROM markets WHERE market_id = %s", (market_id,))
        return cursor.fetchone()

    except Error as e:
        logger.error(f"Error fetching market {market_id}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_recent_snapshots(market_id, hours=24):
    """
    Get recent snapshots for a market.

    Args:
        market_id: The market identifier
        hours: Number of hours to look back (default 24)

    Returns:
        List of snapshot records ordered by timestamp
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT * FROM market_snapshots
            WHERE market_id = %s
              AND timestamp >= NOW() - INTERVAL %s HOUR
            ORDER BY timestamp ASC
        """

        cursor.execute(query, (market_id, hours))
        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error fetching snapshots for {market_id}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def insert_prediction(prediction_data):
    """
    Insert an AI prediction record.

    Args:
        prediction_data: dict with keys: market_id, suggested_play, grade,
                        reasoning, key_signal, signals_json,
                        market_price_at_prediction, market_end_date, alert_ids

    Returns:
        prediction_id or None on failure
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO ai_predictions (market_id, suggested_play, grade,
                                        reasoning, key_signal, signals_json,
                                        market_price_at_prediction, market_end_date,
                                        alert_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        signals_json = prediction_data.get('signals_json')
        if isinstance(signals_json, (dict, list)):
            signals_json = json.dumps(signals_json)

        cursor.execute(query, (
            prediction_data['market_id'],
            prediction_data.get('suggested_play'),
            prediction_data.get('grade'),
            prediction_data.get('reasoning'),
            prediction_data.get('key_signal'),
            signals_json,
            prediction_data.get('market_price_at_prediction'),
            prediction_data.get('market_end_date'),
            prediction_data.get('alert_ids')
        ))

        connection.commit()
        prediction_id = cursor.lastrowid
        logger.info(f"Inserted prediction {prediction_id} for market: {prediction_data['market_id']}")
        return prediction_id

    except Error as e:
        logger.error(f"Error inserting prediction for {prediction_data.get('market_id')}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_accuracy_by_grade(days=90):
    """
    Get prediction accuracy grouped by grade.

    Args:
        days: Number of days to look back

    Returns:
        Dict of grade -> {total, correct, accuracy}
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT grade,
                   COUNT(*) as total,
                   SUM(CASE WHEN prediction_correct = TRUE THEN 1 ELSE 0 END) as correct
            FROM ai_predictions
            WHERE resolved = TRUE
              AND predicted_at >= NOW() - INTERVAL %s DAY
            GROUP BY grade
        """, (days,))

        results = {}
        for row in cursor.fetchall():
            grade = row['grade']
            total = row['total']
            correct = row['correct'] or 0
            results[grade] = {
                'total': total,
                'correct': correct,
                'accuracy': round(correct / total * 100, 1) if total > 0 else 0
            }

        return results

    except Error as e:
        logger.error(f"Error getting accuracy by grade: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_unresolved_predictions():
    """
    Get predictions that haven't been resolved yet and whose market end date has passed.

    Returns:
        List of prediction dicts
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.*, m.question, m.slug
            FROM ai_predictions p
            LEFT JOIN markets m ON p.market_id = m.market_id
            WHERE p.resolved = FALSE
              AND p.market_end_date IS NOT NULL
              AND p.market_end_date <= NOW()
        """)

        return cursor.fetchall()

    except Error as e:
        logger.error(f"Error getting unresolved predictions: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def resolve_prediction(prediction_id, outcome, correct):
    """
    Mark a prediction as resolved with the actual outcome.

    Args:
        prediction_id: The prediction ID
        outcome: 'YES' or 'NO'
        correct: Boolean whether prediction was correct

    Returns:
        True if updated successfully
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE ai_predictions
            SET resolved = TRUE,
                actual_outcome = %s,
                prediction_correct = %s,
                resolved_at = NOW()
            WHERE id = %s
        """, (outcome, correct, prediction_id))

        connection.commit()
        logger.info(f"Resolved prediction {prediction_id}: outcome={outcome}, correct={correct}")
        return cursor.rowcount > 0

    except Error as e:
        logger.error(f"Error resolving prediction {prediction_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def cleanup_old_snapshots(days=7):
    """
    Delete snapshots older than specified number of days.

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

        query = """
            DELETE FROM market_snapshots
            WHERE timestamp < NOW() - INTERVAL %s DAY
        """

        cursor.execute(query, (days,))
        deleted_count = cursor.rowcount
        connection.commit()

        logger.info(f"Cleaned up {deleted_count} snapshots older than {days} days")
        return deleted_count

    except Error as e:
        logger.error(f"Error cleaning up old snapshots: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def cleanup_old_alerts(days=30):
    """
    Delete alerts older than specified number of days.

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

        query = """
            DELETE FROM spike_alerts
            WHERE detected_at < NOW() - INTERVAL %s DAY
        """

        cursor.execute(query, (days,))
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


def cleanup_inactive_markets(days=30):
    """
    Delete markets that haven't been updated in specified number of days.

    Args:
        days: Number of days of inactivity before deletion (default 30)

    Returns:
        Number of rows deleted
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            DELETE FROM markets
            WHERE updated_at < NOW() - INTERVAL %s DAY
        """

        cursor.execute(query, (days,))
        deleted_count = cursor.rowcount
        connection.commit()

        logger.info(f"Cleaned up {deleted_count} inactive markets (no updates in {days} days)")
        return deleted_count

    except Error as e:
        logger.error(f"Error cleaning up inactive markets: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def run_cleanup(snapshot_days=7, alert_days=30, market_days=30):
    """
    Run all cleanup tasks.

    Args:
        snapshot_days: Days to retain snapshots (default 7)
        alert_days: Days to retain alerts (default 30)
        market_days: Days of inactivity before removing markets (default 30)
    """
    logger.info("Starting database cleanup...")

    snapshots_deleted = cleanup_old_snapshots(snapshot_days)
    alerts_deleted = cleanup_old_alerts(alert_days)
    markets_deleted = cleanup_inactive_markets(market_days)

    logger.info(
        f"Cleanup complete: {snapshots_deleted} snapshots, "
        f"{alerts_deleted} alerts, {markets_deleted} markets removed"
    )


if __name__ == "__main__":
    # Setup logging for standalone execution
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
        print("Initializing Polymarket Monitor database...")
        init_database()
        print("Database initialization complete.")
        print("\nTo run cleanup: python database.py cleanup")
