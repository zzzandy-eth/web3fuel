"""
Polymarket Monitor - Status and Health Monitor
Displays collection statistics, spike alerts, and system health.
"""

import sys
import logging
from datetime import datetime, timedelta

from mysql.connector import Error

from database import get_connection
from config import DISCORD_WEBHOOK_URL, SPIKE_THRESHOLD_RATIO, SNAPSHOT_RETENTION_DAYS

logging.basicConfig(level=logging.WARNING)


class MonitorStatus:
    """Status monitor for Polymarket spike detection system."""

    def __init__(self):
        self.db = None

    def connect(self):
        """Establish database connection."""
        try:
            self.db = get_connection()
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()

    def get_collection_stats(self):
        """Get data collection statistics."""
        cursor = self.db.cursor(dictionary=True)

        stats = {}

        # Total markets tracked
        cursor.execute("SELECT COUNT(*) as count FROM markets")
        stats['total_markets'] = cursor.fetchone()['count']

        # Active markets (updated recently)
        cursor.execute("""
            SELECT COUNT(*) as count FROM markets
            WHERE updated_at >= NOW() - INTERVAL 24 HOUR
        """)
        stats['active_markets'] = cursor.fetchone()['count']

        # Total snapshots collected
        cursor.execute("SELECT COUNT(*) as count FROM market_snapshots")
        stats['total_snapshots'] = cursor.fetchone()['count']

        # Snapshots in last 24 hours
        cursor.execute("""
            SELECT COUNT(*) as count FROM market_snapshots
            WHERE timestamp >= NOW() - INTERVAL 24 HOUR
        """)
        stats['snapshots_24h'] = cursor.fetchone()['count']

        # Last collection time
        cursor.execute("SELECT MAX(timestamp) as last_collection FROM market_snapshots")
        result = cursor.fetchone()
        stats['last_collection'] = result['last_collection'] if result else None

        # Markets with sufficient history (12+ snapshots)
        cursor.execute("""
            SELECT COUNT(*) as count FROM (
                SELECT market_id
                FROM market_snapshots
                GROUP BY market_id
                HAVING COUNT(*) >= 12
            ) as ready_markets
        """)
        stats['markets_ready'] = cursor.fetchone()['count']

        # Database size estimate
        try:
            cursor.execute("""
                SELECT
                    TABLE_NAME as tbl_name,
                    ROUND(DATA_LENGTH / 1024 / 1024, 2) as data_mb,
                    TABLE_ROWS as row_count
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY DATA_LENGTH DESC
            """)
            stats['table_sizes'] = cursor.fetchall()
        except Exception:
            stats['table_sizes'] = []

        cursor.close()
        return stats

    def get_spike_stats(self):
        """Get spike detection statistics."""
        cursor = self.db.cursor(dictionary=True)

        stats = {}

        # Total spikes detected
        cursor.execute("SELECT COUNT(*) as count FROM spike_alerts")
        stats['total_spikes'] = cursor.fetchone()['count']

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

        # Most recent spikes with market details
        cursor.execute("""
            SELECT
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
            LIMIT 5
        """)
        stats['recent_spikes'] = cursor.fetchall()

        # Spike distribution by metric type
        cursor.execute("""
            SELECT metric_type, COUNT(*) as count
            FROM spike_alerts
            GROUP BY metric_type
        """)
        stats['by_metric'] = cursor.fetchall()

        cursor.close()
        return stats

    def get_top_markets(self, limit=5):
        """Get markets with most data collected."""
        cursor = self.db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                m.market_id,
                m.question,
                COUNT(s.id) as snapshot_count,
                MAX(s.timestamp) as last_snapshot,
                AVG(s.orderbook_bid_depth) as avg_bid_depth
            FROM markets m
            LEFT JOIN market_snapshots s ON m.market_id = s.market_id
            GROUP BY m.market_id, m.question
            ORDER BY snapshot_count DESC
            LIMIT %s
        """, (limit,))

        markets = cursor.fetchall()
        cursor.close()
        return markets

    def check_health(self):
        """Run health checks and return list of issues."""
        issues = []
        warnings = []

        cursor = self.db.cursor(dictionary=True)

        # Check 1: Recent data collection
        cursor.execute("SELECT MAX(timestamp) as last FROM market_snapshots")
        result = cursor.fetchone()
        last_collection = result['last'] if result else None

        if last_collection:
            time_since = datetime.now() - last_collection
            minutes_since = time_since.total_seconds() / 60

            if minutes_since > 60:
                issues.append(f"No data collected in {minutes_since:.0f} minutes (expected every 30 min)")
            elif minutes_since > 35:
                warnings.append(f"Last collection was {minutes_since:.0f} minutes ago")
        else:
            issues.append("No data collected yet - run collector.py")

        # Check 2: Discord webhook
        if not DISCORD_WEBHOOK_URL:
            warnings.append("Discord webhook not configured (no alerts will be sent)")

        # Check 3: Markets ready for spike detection
        cursor.execute("""
            SELECT COUNT(*) as count FROM (
                SELECT market_id FROM market_snapshots
                GROUP BY market_id HAVING COUNT(*) >= 12
            ) as ready
        """)
        ready_count = cursor.fetchone()['count']

        if ready_count == 0:
            warnings.append("No markets have enough history for spike detection (need 12+ snapshots)")

        # Check 4: Database growth
        cursor.execute("SELECT COUNT(*) as count FROM market_snapshots")
        snapshot_count = cursor.fetchone()['count']

        # Rough estimate: 7 days of data at 48 collections/day, ~300 markets = ~100k snapshots
        expected_max = SNAPSHOT_RETENTION_DAYS * 48 * 500
        if snapshot_count > expected_max:
            warnings.append(f"Database may need cleanup ({snapshot_count:,} snapshots)")

        cursor.close()

        return issues, warnings

    def display_status(self):
        """Display complete status report."""
        print("=" * 65)
        print("  POLYMARKET MONITOR - STATUS REPORT")
        print("=" * 65)
        print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 65)
        print()

        # Health Status (show first - most important)
        issues, warnings = self.check_health()

        print("[HEALTH STATUS]")
        print("-" * 65)

        if not issues and not warnings:
            print("  [OK] All systems operational")
        else:
            for issue in issues:
                print(f"  [ERROR] {issue}")
            for warning in warnings:
                print(f"  [WARN]  {warning}")

        print()

        # Collection Stats
        print("[DATA COLLECTION]")
        print("-" * 65)

        stats = self.get_collection_stats()

        print(f"  Total markets tracked:      {stats['total_markets']:,}")
        print(f"  Active markets (24h):       {stats['active_markets']:,}")
        print(f"  Total snapshots:            {stats['total_snapshots']:,}")
        print(f"  Snapshots (24h):            {stats['snapshots_24h']:,}")
        print(f"  Markets ready for spikes:   {stats['markets_ready']:,}")

        if stats['last_collection']:
            time_ago = datetime.now() - stats['last_collection']
            minutes_ago = time_ago.total_seconds() / 60
            print(f"  Last collection:            {minutes_ago:.0f} minutes ago")
        else:
            print(f"  Last collection:            Never")

        print()

        # Spike Stats
        print("[SPIKE DETECTION]")
        print("-" * 65)

        spike_stats = self.get_spike_stats()

        print(f"  Total spikes detected:      {spike_stats['total_spikes']:,}")
        print(f"  Spikes (last 24h):          {spike_stats['spikes_24h']:,}")
        print(f"  Spikes (last 7 days):       {spike_stats['spikes_7d']:,}")
        print(f"  Detection threshold:        {SPIKE_THRESHOLD_RATIO}x baseline")

        if spike_stats['by_metric']:
            print(f"  By metric:")
            for row in spike_stats['by_metric']:
                metric = row['metric_type'].replace('orderbook_', '')
                print(f"    - {metric}: {row['count']}")

        print()

        # Recent Spikes
        if spike_stats['recent_spikes']:
            print("[RECENT SPIKES]")
            print("-" * 65)

            for spike in spike_stats['recent_spikes']:
                when = spike['detected_at'].strftime('%m/%d %H:%M')
                ratio = spike['spike_ratio']
                metric = spike['metric_type'].replace('orderbook_', '').replace('_depth', '')
                question = spike['question'] or 'Unknown'
                if len(question) > 45:
                    question = question[:45] + "..."

                print(f"  {when} | {ratio:5.1f}x {metric:4s} | {question}")

            print()

        # Top Markets
        print("[TOP MARKETS BY DATA]")
        print("-" * 65)

        top_markets = self.get_top_markets(5)
        for market in top_markets:
            question = market['question'] or 'Unknown'
            if len(question) > 40:
                question = question[:40] + "..."
            count = market['snapshot_count'] or 0
            print(f"  {count:4d} snapshots | {question}")

        print()

        # Database Size
        if stats['table_sizes']:
            print("[DATABASE SIZE]")
            print("-" * 65)

            for table in stats['table_sizes']:
                name = table.get('tbl_name') or table.get('TABLE_NAME', 'unknown')
                size = table.get('data_mb') or table.get('DATA_MB', 0) or 0
                rows = table.get('row_count') or table.get('TABLE_ROWS', 0) or 0
                print(f"  {name:20s} {rows:>10,} rows  {size:>6.2f} MB")

        print()
        print("=" * 65)
        print("  Commands: python collector.py (run now)")
        print("            python notifier.py  (test Discord)")
        print("            python detector.py  (detect spikes)")
        print("=" * 65)


def main():
    """Main entry point."""
    monitor = MonitorStatus()

    if not monitor.connect():
        print("\nFailed to connect to database. Check your .env configuration.")
        sys.exit(1)

    try:
        monitor.display_status()
    except Exception as e:
        print(f"\n[ERROR] Failed to generate status: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        monitor.close()


if __name__ == "__main__":
    main()
