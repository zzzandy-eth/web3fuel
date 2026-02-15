"""
Trade outcome resolver for Macro Scanner.
Checks unresolved outcomes and active positions against current prices,
marks them as win/loss/breakeven/expired when thresholds are hit.
"""

import logging
from datetime import datetime, timezone

from config import OUTCOME_BREAKEVEN_PCT
from database import (
    get_unresolved_outcomes, resolve_outcome,
    get_active_positions, update_position_status
)

logger = logging.getLogger(__name__)


def _determine_outcome(direction, entry, target, stop, current_price, expired):
    """
    Determine if a trade outcome is resolved based on current price.

    Args:
        direction: 'long' or 'short'
        entry: Entry price (float)
        target: Target price (float or None)
        stop: Stop price (float or None)
        current_price: Current market price (float)
        expired: Whether the outcome's expiry has passed

    Returns:
        (outcome, exit_price) or (None, None) if not yet resolved
    """
    if entry is None or current_price is None:
        return None, None

    entry = float(entry)
    current = float(current_price)

    if direction == 'long':
        if target and current >= float(target):
            return 'win', current
        if stop and current <= float(stop):
            return 'loss', current
    elif direction == 'short':
        if target and current <= float(target):
            return 'win', current
        if stop and current >= float(stop):
            return 'loss', current

    if expired:
        pct = ((current - entry) / entry) * 100
        if direction == 'short':
            pct = -pct
        if abs(pct) <= OUTCOME_BREAKEVEN_PCT:
            return 'breakeven', current
        elif pct > 0:
            return 'win', current
        else:
            return 'loss', current

    return None, None


def _fetch_batch_prices(tickers):
    """Fetch current prices for a list of tickers via yfinance."""
    from analyzer import _fetch_ticker_prices
    return _fetch_ticker_prices(tickers)


def check_resolutions():
    """
    Check all unresolved trade outcomes and resolve any that hit target/stop/expiry.

    Returns:
        Count of outcomes resolved
    """
    outcomes = get_unresolved_outcomes()
    if not outcomes:
        logger.info("No unresolved trade outcomes to check")
        return 0

    # Collect unique tickers
    tickers = list({o['ticker'] for o in outcomes})
    logger.info(f"Checking {len(outcomes)} unresolved outcomes across {len(tickers)} tickers")

    prices = _fetch_batch_prices(tickers)
    if not prices:
        logger.warning("Could not fetch any prices for resolution check")
        return 0

    now = datetime.now(timezone.utc)
    resolved_count = 0

    for outcome in outcomes:
        ticker = outcome['ticker']
        current_price = prices.get(ticker)
        if current_price is None:
            continue

        entry = outcome['entry_price']
        expired = outcome['expires_at'] <= now if outcome['expires_at'] else False

        result, exit_price = _determine_outcome(
            direction=outcome['direction'],
            entry=entry,
            target=outcome['target_price'],
            stop=outcome['stop_price'],
            current_price=current_price,
            expired=expired
        )

        if result:
            entry_f = float(entry) if entry else 0
            pct_move = ((exit_price - entry_f) / entry_f * 100) if entry_f else 0
            if outcome['direction'] == 'short':
                pct_move = -pct_move

            resolve_outcome(outcome['id'], result, exit_price, round(pct_move, 4))
            resolved_count += 1

    logger.info(f"Resolved {resolved_count}/{len(outcomes)} trade outcomes")
    return resolved_count


def check_active_positions():
    """
    Check active positions for target/stop hits and auto-update status.

    Returns:
        Count of positions updated
    """
    positions = get_active_positions()
    if not positions:
        logger.info("No active positions to check")
        return 0

    tickers = list({p['ticker'] for p in positions})
    logger.info(f"Checking {len(positions)} active positions across {len(tickers)} tickers")

    prices = _fetch_batch_prices(tickers)
    if not prices:
        logger.warning("Could not fetch any prices for position check")
        return 0

    updated_count = 0

    for pos in positions:
        ticker = pos['ticker']
        current_price = prices.get(ticker)
        if current_price is None:
            continue

        direction = pos['direction']
        target = float(pos['target_price']) if pos['target_price'] else None
        stop = float(pos['stop_loss']) if pos['stop_loss'] else None

        if direction == 'long':
            if target and current_price >= target:
                update_position_status(pos['id'], 'target_hit', current_price)
                logger.info(f"Position {pos['id']} {ticker}: TARGET HIT @ ${current_price}")
                updated_count += 1
            elif stop and current_price <= stop:
                update_position_status(pos['id'], 'stopped_out', current_price)
                logger.info(f"Position {pos['id']} {ticker}: STOPPED OUT @ ${current_price}")
                updated_count += 1
        elif direction == 'short':
            if target and current_price <= target:
                update_position_status(pos['id'], 'target_hit', current_price)
                logger.info(f"Position {pos['id']} {ticker}: TARGET HIT @ ${current_price}")
                updated_count += 1
            elif stop and current_price >= stop:
                update_position_status(pos['id'], 'stopped_out', current_price)
                logger.info(f"Position {pos['id']} {ticker}: STOPPED OUT @ ${current_price}")
                updated_count += 1

    logger.info(f"Updated {updated_count}/{len(positions)} active positions")
    return updated_count
