"""
Data collector for Polymarket Monitor.
Fetches market data from Gamma API and orderbook data from CLOB API.
"""

import requests
import json
import time
import logging
from datetime import datetime
from dateutil import parser as dateutil_parser

from config import (
    GAMMA_API_BASE,
    CLOB_API_BASE,
    RATE_LIMIT_DELAY,
    REQUEST_TIMEOUT,
    MAX_EVENTS_PER_FETCH
)
from database import upsert_market, insert_snapshot

logger = logging.getLogger(__name__)


def fetch_active_events(limit=None):
    """
    Fetch active events from Polymarket Gamma API.

    Args:
        limit: Maximum number of events to fetch (default from config)

    Returns:
        List of event dicts containing market data, or empty list on error
    """
    if limit is None:
        limit = MAX_EVENTS_PER_FETCH

    url = f"{GAMMA_API_BASE}/events"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit
    }

    try:
        logger.info(f"Fetching active events from {url}")
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        events = response.json()
        logger.info(f"Fetched {len(events)} active events")
        return events

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching active events: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing events response: {e}")
        return []


def _parse_json_field(value, default=None):
    """
    Parse a field that might be a JSON string or already parsed.

    Args:
        value: The field value (string or list/dict)
        default: Default value if parsing fails

    Returns:
        Parsed value (list or dict) or default
    """
    if value is None:
        return default if default is not None else []

    if isinstance(value, (list, dict)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []

    return default if default is not None else []


def parse_markets_from_events(events):
    """
    Parse market data from events response.

    Args:
        events: List of event dicts from Gamma API

    Returns:
        List of market dicts with normalized data
    """
    markets = []

    for event in events:
        event_id = event.get("id")
        event_slug = event.get("slug", "")
        category = event.get("category")

        # Each event can have multiple markets
        event_markets = event.get("markets", [])

        for market in event_markets:
            market_id = market.get("id")
            if not market_id:
                continue

            # Extract clob token IDs for orderbook queries
            # API returns this as a JSON string, need to parse it
            clob_token_ids = _parse_json_field(market.get("clobTokenIds"), [])

            # Extract outcomes (may also be JSON string)
            outcomes = _parse_json_field(market.get("outcomes"), [])

            # Extract outcome prices (probabilities) - may be JSON string
            outcome_prices = _parse_json_field(market.get("outcomePrices"), [])

            # Parse prices (they come as strings within the array)
            yes_price = None
            no_price = None
            if outcome_prices and len(outcome_prices) >= 1:
                try:
                    yes_price = float(outcome_prices[0])
                except (ValueError, TypeError):
                    pass
            if outcome_prices and len(outcome_prices) >= 2:
                try:
                    no_price = float(outcome_prices[1])
                except (ValueError, TypeError):
                    pass

            # Extract end date from market or event level
            end_date = None
            end_date_raw = market.get("endDate") or market.get("end_date_iso") or event.get("endDate")
            if end_date_raw:
                try:
                    end_date = dateutil_parser.parse(end_date_raw)
                except (ValueError, TypeError):
                    logger.debug(f"Could not parse end_date: {end_date_raw}")

            market_data = {
                "market_id": str(market_id),  # Ensure string for DB
                "event_id": str(event_id) if event_id else None,
                "question": market.get("question"),
                "slug": event_slug,
                "outcomes": json.dumps(outcomes),
                "clob_token_ids": json.dumps(clob_token_ids),
                "category": category,
                "end_date": end_date,
                "active": market.get("active", True),
                "yes_price": yes_price,
                "no_price": no_price,
                "raw_clob_token_ids": clob_token_ids  # Keep parsed list for orderbook fetch
            }

            markets.append(market_data)

    logger.info(f"Parsed {len(markets)} markets from {len(events)} events")
    return markets


def fetch_orderbook_depth(token_id):
    """
    Fetch orderbook depth from Polymarket CLOB API.

    Args:
        token_id: The CLOB token ID for the outcome

    Returns:
        Dict with bid_depth and ask_depth, or None on error
    """
    if not token_id:
        return None

    url = f"{CLOB_API_BASE}/book"
    params = {"token_id": token_id}

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        data = response.json()

        # Calculate total bid depth (sum of all bid sizes)
        bids = data.get("bids", [])
        bid_depth = sum(float(bid.get("size", 0)) for bid in bids)

        # Calculate total ask depth (sum of all ask sizes)
        asks = data.get("asks", [])
        ask_depth = sum(float(ask.get("size", 0)) for ask in asks)

        logger.debug(f"Orderbook for {token_id}: bid_depth={bid_depth}, ask_depth={ask_depth}")

        return {
            "bid_depth": bid_depth,
            "ask_depth": ask_depth
        }

    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching orderbook for token {token_id}: {e}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Error parsing orderbook for token {token_id}: {e}")
        return None


def fetch_combined_orderbook_depth(clob_token_ids):
    """
    Fetch and combine orderbook depth for all token IDs of a market.

    Args:
        clob_token_ids: List of token IDs (typically [YES_token, NO_token])

    Returns:
        Dict with total bid_depth and ask_depth across all outcomes
    """
    total_bid_depth = 0.0
    total_ask_depth = 0.0

    for token_id in clob_token_ids:
        depth = fetch_orderbook_depth(token_id)
        if depth:
            total_bid_depth += depth["bid_depth"]
            total_ask_depth += depth["ask_depth"]

        # Rate limiting between CLOB API calls
        time.sleep(RATE_LIMIT_DELAY)

    return {
        "bid_depth": total_bid_depth,
        "ask_depth": total_ask_depth
    }


def store_market_snapshot(market_data, orderbook_data):
    """
    Store a market snapshot combining price and orderbook data.

    Args:
        market_data: Dict with market info including prices
        orderbook_data: Dict with bid_depth and ask_depth
    """
    # First, upsert the market record
    upsert_market(market_data)

    # Then insert the snapshot
    snapshot = {
        "market_id": market_data["market_id"],
        "yes_price": market_data.get("yes_price"),
        "no_price": market_data.get("no_price"),
        "orderbook_bid_depth": orderbook_data.get("bid_depth") if orderbook_data else None,
        "orderbook_ask_depth": orderbook_data.get("ask_depth") if orderbook_data else None
    }

    insert_snapshot(snapshot)
    logger.debug(f"Stored snapshot for market {market_data['market_id']}")


def is_active_market(market):
    """
    Check if a market is actively trading (not resolved).
    Resolved markets have prices at 0 or 1 and return 404 from CLOB API.

    Args:
        market: Market dict with yes_price and no_price

    Returns:
        True if market appears to be actively trading
    """
    yes_price = market.get("yes_price")
    no_price = market.get("no_price")

    # If no prices, skip
    if yes_price is None and no_price is None:
        return False

    # If price is very close to 0 or 1, market is likely resolved
    if yes_price is not None:
        if yes_price < 0.02 or yes_price > 0.98:
            return False

    return True


def collect_all_markets():
    """
    Main collection routine: fetch all active markets and their orderbooks.

    Returns:
        Tuple of (markets_processed, errors_count)
    """
    start_time = datetime.now()
    logger.info(f"Starting collection run at {start_time}")

    # Fetch active events
    events = fetch_active_events()
    if not events:
        logger.warning("No events fetched, aborting collection")
        return 0, 1

    # Parse markets from events
    all_markets = parse_markets_from_events(events)
    if not all_markets:
        logger.warning("No markets parsed, aborting collection")
        return 0, 1

    # Filter to only active (non-resolved) markets
    markets = [m for m in all_markets if is_active_market(m)]
    skipped = len(all_markets) - len(markets)
    logger.info(f"Filtered to {len(markets)} active markets (skipped {skipped} resolved)")

    markets_processed = 0
    errors_count = 0

    for i, market in enumerate(markets):
        try:
            market_id = market["market_id"]
            clob_token_ids = market.get("raw_clob_token_ids", [])

            # Progress logging every 10 markets
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(markets)} markets processed")

            # Fetch orderbook depth for this market
            orderbook_data = None
            if clob_token_ids:
                orderbook_data = fetch_combined_orderbook_depth(clob_token_ids)

            # Store the snapshot
            store_market_snapshot(market, orderbook_data)
            markets_processed += 1

        except Exception as e:
            logger.error(f"Error processing market {market.get('market_id')}: {e}")
            errors_count += 1
            continue

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info(
        f"Collection complete: {markets_processed} markets processed, "
        f"{errors_count} errors, duration: {duration:.1f}s"
    )

    return markets_processed, errors_count


def main():
    """Entry point for the collector."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Polymarket Monitor Collector starting...")

    # Initialize database (creates tables if needed)
    from database import init_database, run_cleanup
    init_database()

    # Run collection
    markets_processed, errors = collect_all_markets()

    if errors > 0:
        logger.warning(f"Collection completed with {errors} errors")
    else:
        logger.info(f"Collection completed successfully: {markets_processed} markets")

    # Run spike detection
    try:
        from detector import detect_all_spikes
        spikes = detect_all_spikes()

        if spikes:
            logger.info(f"Detected {len(spikes)} orderbook spike(s) this run")
            # Spikes are already printed to console by detect_all_spikes()
            # Discord notifications will be added in Part 3
    except Exception as e:
        logger.error(f"Spike detection failed: {e}")

    # Run cleanup to remove old data
    from config import SNAPSHOT_RETENTION_DAYS, ALERT_RETENTION_DAYS, MARKET_RETENTION_DAYS
    try:
        run_cleanup(
            snapshot_days=SNAPSHOT_RETENTION_DAYS,
            alert_days=ALERT_RETENTION_DAYS,
            market_days=MARKET_RETENTION_DAYS
        )
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


if __name__ == "__main__":
    main()
