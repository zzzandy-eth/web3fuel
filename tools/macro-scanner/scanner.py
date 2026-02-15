"""
Macro Scanner - Main entry point.
Orchestrates the pipeline: News scan (Comet/file) -> yfinance indicators ->
Claude analysis -> Discord alert -> DB storage.

Usage:
    python scanner.py                  # Run pipeline + Discord alert (cron mode)
    python scanner.py --test           # Send test Discord notification
    python scanner.py --scan           # Comet scan + pipeline, NO Discord alert (manual mode)
    python scanner.py --no-notify      # Run pipeline without Discord notification
    python scanner.py --deep-dive=list # Show pending deep-dive queue as JSON
    python scanner.py --deep-dive      # Read daily summary JSON from stdin, store + send summary
    python scanner.py --deep-dive=file # Read daily summary JSON from file path
"""

import sys
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Ensure tool directory is on path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CLAUDE_API_KEY,
    DISCORD_WEBHOOK_URL,
    SCAN_RETENTION_DAYS,
    ALERT_RETENTION_DAYS,
    LOG_LEVEL,
    DEEP_RESEARCH_THRESHOLD
)

logger = logging.getLogger("macro_scanner")


def setup_logging():
    """Configure logging with both console and file output."""
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "scanner.log"

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(str(log_file))
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def run_pipeline(notify=True):
    """
    Execute the macro scanning pipeline.

    Args:
        notify: If True, send Discord alert. If False, skip (Comet/manual mode).

    Returns:
        Tuple of (scan_id, alert_id) or (None, None) on failure
    """
    from perplexity import get_top_macro_items
    from indicators import fetch_indicators, indicators_to_serializable
    from analyzer import analyze_macro
    from notifier import send_macro_alert
    from database import insert_scan_result, insert_trade_alert, mark_alert_notified

    start_time = time.time()
    scan_id = None
    alert_id = None

    # =========================================================================
    # Step 1: Load macro news (from Comet scan_input.json)
    # =========================================================================
    logger.info("=" * 60)
    logger.info("Step 1/4: Load macro news")
    logger.info("=" * 60)

    top3 = get_top_macro_items()

    if not top3:
        logger.warning("No macro news found - check scan_input.json")
        scan_id = _store_scan_result([], {}, time.time() - start_time)
        return scan_id, None

    logger.info(f"Got {len(top3)} macro items")

    # =========================================================================
    # Step 2: Market indicators
    # =========================================================================
    logger.info("=" * 60)
    logger.info("Step 2/4: Market indicators")
    logger.info("=" * 60)

    indicators = fetch_indicators()
    indicators_serial = indicators_to_serializable(indicators)
    logger.info("Market indicators fetched")

    # =========================================================================
    # Step 3: Claude analysis
    # =========================================================================
    logger.info("=" * 60)
    logger.info("Step 3/4: Claude analysis")
    logger.info("=" * 60)

    analysis = None
    if CLAUDE_API_KEY:
        analysis = analyze_macro(top3, indicators)
        if analysis:
            logger.info(f"Claude analysis complete (confidence: {analysis.get('confidence', '?')}/5)")
        else:
            logger.warning("Claude analysis returned no result")
    else:
        logger.warning("CLAUDE_API_KEY not set - skipping analysis")

    # =========================================================================
    # Store results in DB
    # =========================================================================
    scan_duration = time.time() - start_time
    scan_id = _store_scan_result(top3, indicators_serial, scan_duration)

    if analysis and scan_id:
        alert_id = _store_trade_alert(scan_id, analysis)

    # =========================================================================
    # Queue high-impact stories for deep-dive research
    # =========================================================================
    from database import queue_deep_dive

    queued_count = 0
    for item in top3:
        if item.get('impact_score', 0) >= DEEP_RESEARCH_THRESHOLD:
            qid = queue_deep_dive(item, scan_id=scan_id)
            if qid:
                queued_count += 1
    if queued_count:
        logger.info(f"Queued {queued_count} high-impact item(s) for deep-dive research")

    # =========================================================================
    # Step 4: Discord notification
    # =========================================================================
    logger.info("=" * 60)
    logger.info("Step 4/4: Discord notification")
    logger.info("=" * 60)

    if not notify:
        logger.info("Notification suppressed (manual/Comet mode) — will send via daily summary")
    elif analysis and DISCORD_WEBHOOK_URL:
        success = send_macro_alert(analysis, indicators)
        if success and alert_id:
            mark_alert_notified(alert_id)
            logger.info(f"Discord alert sent and marked as notified (alert {alert_id})")
        elif not success:
            logger.warning("Failed to send Discord alert")
    elif not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set - skipping Discord notification")
    elif not analysis:
        logger.info("No analysis to send - skipping Discord notification")

    # =========================================================================
    # Summary
    # =========================================================================
    total_duration = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {total_duration:.1f}s")
    logger.info(f"  Scan ID: {scan_id}")
    logger.info(f"  Alert ID: {alert_id}")
    logger.info(f"  Stories: {len(top3)}")
    logger.info(f"  Analysis: {'Yes' if analysis else 'No'}")
    logger.info(f"  Confidence: {analysis.get('confidence', 'N/A') if analysis else 'N/A'}/5")
    logger.info("=" * 60)

    return scan_id, alert_id


def _store_scan_result(top3, indicators, duration):
    """Store scan result in database."""
    from database import insert_scan_result

    try:
        scan_id = insert_scan_result({
            'raw_top10': None,
            'filtered_top3': top3,
            'deep_research': None,
            'indicators': indicators,
            'scan_duration_seconds': round(duration, 2)
        })
        if scan_id:
            logger.info(f"Scan result stored (ID: {scan_id})")
        return scan_id
    except Exception as e:
        logger.error(f"Failed to store scan result: {e}")
        return None


def _store_trade_alert(scan_id, analysis):
    """Store trade alert in database."""
    from database import insert_trade_alert

    try:
        # Build trade_idea string from new structured trade format
        trade = analysis.get('trade', {})
        sector = analysis.get('sector_impact', '')
        if trade and trade.get('tickers'):
            tickers = ', '.join(trade.get('tickers', []))
            trade_idea = (
                f"{trade.get('direction', 'long').upper()} {tickers}"
                f"{' | ' + sector if sector else ''} | "
                f"Entry: {trade.get('entry', 'N/A')} | "
                f"Target: {trade.get('target', 'N/A')} | "
                f"Stop: {trade.get('stop_loss', 'N/A')} | "
                f"Timeline: {trade.get('timeline', 'N/A')}"
            )
        else:
            trade_idea = analysis.get('trade_idea', 'No trade')

        alert_id = insert_trade_alert({
            'scan_id': scan_id,
            'top_stories': analysis.get('trade', {}),
            'narrative': analysis.get('narrative', ''),
            'trade_idea': trade_idea,
            'confidence': analysis.get('confidence', 0)
        })
        if alert_id:
            logger.info(f"Trade alert stored (ID: {alert_id})")
        return alert_id
    except Exception as e:
        logger.error(f"Failed to store trade alert: {e}")
        return None


def list_deep_dive_queue():
    """Print pending deep-dive items as JSON to stdout."""
    import json
    from database import get_pending_deep_dives
    from perplexity import build_deep_dive_prompt

    items = get_pending_deep_dives()
    if not items:
        print("[]")
        return

    output = []
    for item in items:
        # Convert datetime objects to strings for JSON serialization
        entry = {
            "queue_id": item["id"],
            "headline": item["headline"],
            "impact_score": item["impact_score"],
            "direction": item.get("direction", "mixed"),
            "rationale": item.get("rationale", ""),
            "sectors": item.get("sectors"),
            "key_instruments": item.get("key_instruments"),
            "prompt": build_deep_dive_prompt(item),
            "expires_at": str(item["expires_at"]) if item.get("expires_at") else None
        }
        output.append(entry)

    print(json.dumps(output, indent=2))


def run_deep_dives(source):
    """
    Process deep-dive results and send a daily summary to Discord.

    Args:
        source: File path to JSON, or '' to read from stdin.
                JSON object with:
                  - headlines: [{headline, summary, direction, sectors}] (today's key news)
                  - deep_dives: [{queue_id, headline, deep_research}] (deep-dive results)
                  - trade: {tickers, direction, entry, target, stop_loss, thesis, timeline} (optional verified trade)
    """
    import json
    from database import update_deep_dive
    from notifier import send_daily_summary

    try:
        if source:
            with open(source, 'r') as f:
                data = json.load(f)
        else:
            logger.info("Reading daily summary from stdin...")
            data = json.load(sys.stdin)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Failed to load daily summary data: {e}")
        sys.exit(1)

    # Support both old format (list of results) and new format (summary object)
    if isinstance(data, list):
        # Legacy format: list of {queue_id, headline, deep_research}
        data = {"deep_dives": data}

    deep_dives = data.get('deep_dives', [])
    headlines = data.get('headlines', [])
    trade = data.get('trade', {})

    # Store deep-dive results in DB
    completed_dives = []
    for item in deep_dives:
        queue_id = item.get('queue_id')
        deep_research = item.get('deep_research', '')
        headline = item.get('headline', 'Unknown')

        if not queue_id:
            logger.warning(f"Skipping item without queue_id: {headline}")
            completed_dives.append({"headline": headline, "insight": deep_research})
            continue

        success = update_deep_dive(queue_id, 'completed', deep_research=deep_research)
        if success:
            completed_dives.append({"headline": headline, "insight": deep_research})
            logger.info(f"Stored deep-dive for queue_id={queue_id}: {headline}")
        else:
            logger.warning(f"Failed to update queue_id={queue_id}")

    # Build summary payload
    summary = {
        "headlines": headlines,
        "insights": completed_dives,
        "trade": trade
    }

    if (headlines or completed_dives) and DISCORD_WEBHOOK_URL:
        send_daily_summary(summary)
        logger.info(f"Daily summary sent: {len(headlines)} headlines, {len(completed_dives)} insights")
    elif headlines or completed_dives:
        logger.info(f"Daily summary stored (no Discord webhook): {len(headlines)} headlines, {len(completed_dives)} insights")
    else:
        logger.warning("No content for daily summary")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Macro Scanner - Macroeconomic news scanner")
    parser.add_argument('--test', action='store_true', help="Send test Discord notification")
    parser.add_argument('--scan', type=str, nargs='?', const='', help="Load Comet JSON from stdin or file path, save to scan_input.json, then run pipeline")
    parser.add_argument('--no-notify', action='store_true', dest='no_notify',
                        help="Run pipeline without sending Discord notification")
    parser.add_argument('--deep-dive', type=str, nargs='?', const='', dest='deep_dive',
                        help="Deep-dive mode: 'list' to show pending queue as JSON, or path/stdin to store daily summary")
    args = parser.parse_args()

    setup_logging()

    if args.test:
        logger.info("Running in test mode - sending test notification")
        from notifier import send_test_notification
        success = send_test_notification()
        sys.exit(0 if success else 1)

    # Handle --deep-dive mode
    if args.deep_dive is not None:
        from database import init_database
        init_database()

        if args.deep_dive == 'list':
            list_deep_dive_queue()
            sys.exit(0)
        else:
            run_deep_dives(args.deep_dive)
            sys.exit(0)

    # If --scan provided, load Comet results into scan_input.json first
    if args.scan is not None:
        from perplexity import get_top_macro_items_from_comet, save_scan_input
        import json as _json

        if args.scan:
            # File path provided
            logger.info(f"Loading Comet scan from file: {args.scan}")
            with open(args.scan, 'r') as f:
                raw = _json.load(f)
        else:
            # Read from stdin
            logger.info("Reading Comet scan from stdin...")
            raw = _json.load(sys.stdin)

        items = get_top_macro_items_from_comet(raw)
        if items:
            save_scan_input(items)
            logger.info(f"Saved {len(items)} items to scan_input.json")
        else:
            logger.error("No valid items from Comet scan")
            sys.exit(1)

    logger.info("Macro Scanner starting...")
    logger.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Initialize database
    try:
        from database import init_database
        init_database()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

    # --scan implies --no-notify (daily summary comes after deep dive instead)
    should_notify = not (args.no_notify or args.scan is not None)

    # Run pipeline
    try:
        scan_id, alert_id = run_pipeline(notify=should_notify)
    except Exception as e:
        logger.error(f"Pipeline failed with unexpected error: {e}", exc_info=True)

    # Run cleanup
    try:
        from database import run_cleanup
        run_cleanup(
            scan_days=SCAN_RETENTION_DAYS,
            alert_days=ALERT_RETENTION_DAYS
        )
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

    logger.info("Macro Scanner finished.")


if __name__ == "__main__":
    main()
