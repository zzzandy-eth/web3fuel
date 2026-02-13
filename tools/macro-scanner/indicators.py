"""
Market indicators module for Macro Scanner.
Fetches key macro indicators via yfinance: DXY, VIX, SPY, VXX (VIXY), QQQ.
"""

import logging
from datetime import datetime, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

# Ticker mapping: display name -> yfinance symbol
TICKERS = {
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",
    "SPY": "SPY",
    "VXX": "VIXY",
    "QQQ": "QQQ"
}


def _fetch_single_ticker(name, symbol):
    """
    Fetch price and 6h change for a single ticker.

    Args:
        name: Display name (e.g. "DXY")
        symbol: yfinance symbol (e.g. "DX-Y.NYB")

    Returns:
        Dict with name, symbol, price, change_pct, or None on failure
    """
    try:
        ticker = yf.Ticker(symbol)
        # Fetch 2 days of 1-hour data to calculate 6h change
        hist = ticker.history(period="2d", interval="1h")

        if hist.empty:
            logger.warning(f"No data returned for {name} ({symbol})")
            return None

        current_price = float(hist['Close'].iloc[-1])

        # Calculate 6h change: compare current to ~6 hours ago
        change_pct = None
        if len(hist) >= 7:
            price_6h_ago = float(hist['Close'].iloc[-7])
            if price_6h_ago != 0:
                change_pct = ((current_price - price_6h_ago) / price_6h_ago) * 100
        elif len(hist) >= 2:
            # Fallback: use earliest available
            earliest_price = float(hist['Close'].iloc[0])
            if earliest_price != 0:
                change_pct = ((current_price - earliest_price) / earliest_price) * 100

        return {
            "name": name,
            "symbol": symbol,
            "price": round(current_price, 2),
            "change_pct": round(change_pct, 2) if change_pct is not None else None
        }

    except Exception as e:
        logger.warning(f"Error fetching {name} ({symbol}): {e}")
        return None


def fetch_indicators():
    """
    Fetch all macro indicators with 6h % changes.
    Per-ticker error handling: one failure doesn't block others.

    Returns:
        Dict with ticker names as keys, each containing price/change data.
        Example: {"DXY": {"price": 104.52, "change_pct": 0.3}, ...}
    """
    logger.info("Fetching market indicators...")
    indicators = {}

    for name, symbol in TICKERS.items():
        result = _fetch_single_ticker(name, symbol)
        if result:
            indicators[name] = result
            logger.debug(f"{name}: {result['price']} ({result['change_pct']}%)")
        else:
            indicators[name] = {
                "name": name,
                "symbol": symbol,
                "price": None,
                "change_pct": None
            }

    fetched_count = sum(1 for v in indicators.values() if v.get('price') is not None)
    logger.info(f"Fetched {fetched_count}/{len(TICKERS)} indicators successfully")

    return indicators


def format_indicators_text(indicators):
    """
    Format indicators as a compact text string for prompts and embeds.

    Args:
        indicators: Dict from fetch_indicators()

    Returns:
        Formatted string like "DXY: 104.52 (+0.3%) | VIX: 18.2 (-2.1%) | ..."
    """
    parts = []

    for name in TICKERS:
        data = indicators.get(name, {})
        price = data.get('price')

        if price is None:
            parts.append(f"{name}: N/A")
            continue

        change = data.get('change_pct')
        if change is not None:
            sign = "+" if change >= 0 else ""
            parts.append(f"{name}: {price} ({sign}{change}%)")
        else:
            parts.append(f"{name}: {price}")

    return " | ".join(parts)


def indicators_to_serializable(indicators):
    """
    Convert indicators dict to JSON-serializable format for DB storage.

    Args:
        indicators: Dict from fetch_indicators()

    Returns:
        Dict safe for json.dumps()
    """
    result = {}
    for name, data in indicators.items():
        result[name] = {
            "price": data.get("price"),
            "change_pct": data.get("change_pct")
        }
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Fetching market indicators...")
    data = fetch_indicators()
    print(f"\n{format_indicators_text(data)}")

    print("\nDetailed:")
    for name, info in data.items():
        price = info.get('price', 'N/A')
        change = info.get('change_pct')
        change_str = f"{change:+.2f}%" if change is not None else "N/A"
        print(f"  {name}: {price} ({change_str})")
