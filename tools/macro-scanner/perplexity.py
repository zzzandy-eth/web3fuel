"""
Macro news scanning module.
Supports three modes (in priority order):
  1. scan_input.json - Written by Comet MCP via Claude Code (free)
  2. Perplexity API fallback - sonar model for automated cron ($0.05/scan)
  3. Sample data - for testing only

get_top_macro_items() tries mode 1, then mode 2 automatically.
"""

import json
import re
import logging
import time
from pathlib import Path

import requests

from config import (
    PERPLEXITY_API_KEY,
    PERPLEXITY_API_URL,
    PERPLEXITY_MODEL,
    REQUEST_TIMEOUT
)

logger = logging.getLogger(__name__)

# Comet prompt to use in Claude Code sessions:
COMET_PROMPT = (
    "Top macroeconomic market-moving news from the last 6 hours: "
    "Fed/central bank policy, inflation, employment, GDP/PMI, FX, "
    "energy/geopolitics, and notable political posts affecting markets. "
    "Return a JSON array of at most 5 items, each with: "
    "title, source, url, impact_score (1-10), sectors (list), "
    "direction (bullish/bearish/mixed), summary (1-2 sentences)."
)

# Path for file-based input (Comet writes here)
_SCAN_INPUT_FILE = Path(__file__).resolve().parent / "scan_input.json"

# Max age for scan_input.json before falling back to API (seconds)
_SCAN_INPUT_MAX_AGE = 16 * 3600  # 16 hours (covers overnight gap between 5:30pm and 8:30am scans)


def normalize_item(item):
    """
    Normalize a scan item to the format expected by the rest of the pipeline.
    Handles both Comet fields (title/sectors/summary) and API fields (headline/affected_sectors/rationale).
    """
    return {
        "headline": item.get("title", item.get("headline", "Unknown")),
        "impact_score": item.get("impact_score", 5),
        "direction": item.get("direction", "mixed"),
        "affected_sectors": item.get("sectors", item.get("affected_sectors", [])),
        "rationale": item.get("summary", item.get("rationale", "")),
        "key_instruments": item.get("key_instruments", []),
        "source": item.get("source", ""),
        "url": item.get("url", ""),
        "macro_theme": item.get("macro_theme", ""),
        "confidence": item.get("confidence", 3),
        "affects_positions": item.get("affects_positions", False),
    }


def _load_from_file():
    """
    Try to load scan results from scan_input.json.
    Only uses the file if it's less than 6 hours old.

    Returns:
        List of normalized items, or None if file missing/stale
    """
    if not _SCAN_INPUT_FILE.exists():
        return None

    # Check file age
    age = time.time() - _SCAN_INPUT_FILE.stat().st_mtime
    if age > _SCAN_INPUT_MAX_AGE:
        logger.info(f"scan_input.json is {age/3600:.1f}h old (stale), skipping")
        return None

    try:
        with open(_SCAN_INPUT_FILE, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list) or not data:
            return None

        items = [normalize_item(item) for item in data]
        items.sort(key=lambda x: x.get("impact_score", 0), reverse=True)
        items = items[:5]

        logger.info(f"Loaded {len(items)} items from scan_input.json ({age/60:.0f}m old)")
        return items

    except Exception as e:
        logger.warning(f"Error reading scan_input.json: {e}")
        return None


def _parse_json_response(content):
    """Parse JSON array from API response, stripping markdown fences."""
    if not content:
        return None

    cleaned = content.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    match = re.search(r'\[[\s\S]*\]', content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _get_active_position_tickers():
    """Return list of tickers from active positions, or empty list."""
    try:
        from database import get_active_positions
        positions = get_active_positions()
        return list({p['ticker'] for p in positions})
    except Exception:
        return []


def _fetch_from_api():
    """
    Fallback: fetch top macro items via Perplexity API (sonar model).
    Cost: ~$0.05/call.

    Returns:
        List of normalized items, or None on failure
    """
    if not PERPLEXITY_API_KEY:
        logger.info("No PERPLEXITY_API_KEY configured - API fallback unavailable")
        return None

    logger.info(f"Fetching macro news via Perplexity API ({PERPLEXITY_MODEL})...")

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    user_content = (
        "Act as a professional macro/markets analyst. "
        "From the last 24 hours of global news and data, identify the most "
        "market-moving developments for financial markets.\n\n"
        "Focus on: central bank policy (Fed/ECB/BoJ/BoE), inflation and jobs data, "
        "GDP/PMI, FX regime shifts, energy/geopolitics, major earnings surprises, "
        "credit stress, and volatility shocks.\n\n"
        "Return a JSON array with up to 10 items. For each item include:\n"
        "- headline: concise title\n"
        "- impact_score: 1-10 for GLOBAL macro/market impact (10 = very high)\n"
        "- confidence: 1-5 for your confidence in this impact assessment\n"
        "- macro_theme: one of 'rates','inflation','growth','credit','policy','geopolitics','liquidity'\n"
        "- direction: 'bullish','bearish', or 'mixed'\n"
        "- affected_sectors: list, e.g. ['equities','rates','fx','energy','credit','volatility','crypto']\n"
        "- key_instruments: the most directly affected tickers/instruments "
        "  (e.g. ['SPY','QQQ','TLT','DXY','VIX','CL=F','GC=F'])\n"
        "- summary: 1-2 sentences focused on trading implications (1-4 week horizon)\n"
        "- source: main news source domain (e.g. 'wsj.com','reuters.com')\n"
        "- url: canonical article URL\n\n"
        "VALIDATION RULES:\n"
        "- For each item, cross-check: does the financial market reaction "
        "(price moves, futures, bond yields) confirm the headline's implied direction? "
        "If market data contradicts the headline narrative, lower your confidence score. "
        "If price action confirms it, raise it.\n"
        "- Distinguish between 'news the market has already priced in' vs "
        "'news that is actively moving prices.' Only score impact_score >= 7 "
        "for items where price action is still unfolding.\n\n"
        "Return ONLY the JSON array, sorted by impact_score DESC."
    )

    # Append active position tickers or macro proxy fallback
    position_tickers = _get_active_position_tickers()
    if position_tickers:
        user_content += (
            f"\n\nI currently hold these active positions: {', '.join(position_tickers)}. "
            "If any of your items have a non-trivial impact on these, "
            "set a field `affects_positions: true` and mention them by ticker in key_instruments."
        )
    else:
        user_content += (
            "\n\nPay particular attention to instruments commonly used as macro proxies: "
            "SPY, QQQ, TLT, DXY, EURUSD, USDJPY, VIX, CL=F, GC=F, BTC-USD."
        )

    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Professional macro/markets analyst. "
                    "Return ONLY a JSON array, no other text."
                )
            },
            {
                "role": "user",
                "content": user_content
            }
        ],
        "max_tokens": 1500,
        "search_recency_filter": "day"
    }

    try:
        response = requests.post(
            PERPLEXITY_API_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            logger.warning("Empty response from Perplexity API")
            return None

        result = _parse_json_response(content)
        if not result:
            logger.warning("Could not parse Perplexity response as JSON")
            return None

        items = [normalize_item(item) for item in result]

        # Filter out low-confidence items before ranking
        before_count = len(items)
        items = [i for i in items if i.get('confidence', 3) >= 3]
        if before_count > len(items):
            logger.info(f"Filtered {before_count - len(items)} low-confidence items")

        items.sort(key=lambda x: x.get("impact_score", 0), reverse=True)
        items = items[:5]

        logger.info(f"Got {len(items)} items from Perplexity API")
        return items

    except requests.exceptions.Timeout:
        logger.error(f"Perplexity API timed out after {REQUEST_TIMEOUT}s")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Perplexity API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error from Perplexity API: {e}")
        return None


def get_top_macro_items():
    """
    Get top macro items. Tries sources in order:
      1. scan_input.json (from Comet, if fresh)
      2. Perplexity API (sonar, if API key configured)

    Returns:
        List of normalized item dicts, or empty list
    """
    # Try Comet file first
    items = _load_from_file()
    if items:
        return items

    # Fallback to Perplexity API
    items = _fetch_from_api()
    if items:
        return items

    logger.warning("No macro news available from any source")
    return []


def get_top_macro_items_from_comet(comet_json):
    """
    Process Comet MCP scan results into pipeline-ready format.
    Called from Claude Code after using comet_ask.

    Args:
        comet_json: List of dicts from Comet, or JSON string

    Returns:
        List of normalized item dicts, sorted by impact_score desc, max 5
    """
    if isinstance(comet_json, str):
        try:
            comet_json = json.loads(comet_json)
        except json.JSONDecodeError:
            logger.error("Could not parse Comet JSON string")
            return []

    if not isinstance(comet_json, list):
        logger.error(f"Expected list from Comet, got {type(comet_json).__name__}")
        return []

    items = [normalize_item(item) for item in comet_json]
    items.sort(key=lambda x: x.get("impact_score", 0), reverse=True)
    items = items[:5]

    logger.info(f"Processed {len(items)} items from Comet")
    return items


def save_scan_input(items):
    """
    Save scan results to scan_input.json for the pipeline to consume.
    Called by Claude Code after a Comet scan.
    """
    with open(_SCAN_INPUT_FILE, 'w') as f:
        json.dump(items, f, indent=2)
    logger.info(f"Saved {len(items)} items to {_SCAN_INPUT_FILE}")


# Deep-dive prompt template for Comet MCP research
COMET_DEEP_DIVE_PROMPT = (
    'Deep research on: "{headline}"\n'
    'Context: {rationale}\n'
    'Direction: {direction} | Sectors: {sectors} | Instruments: {instruments}\n'
    '\n'
    'Provide: historical precedent, second-order effects, timeline/key dates, '
    'specific trade setups (entries/exits/sizing), and risk factors. '
    'Focus on swing trading (1-4 week horizon).'
)


def build_deep_dive_prompt(queue_item):
    """
    Build a deep-dive research prompt from a queue item.

    Args:
        queue_item: Dict from deep_dive_queue table

    Returns:
        Formatted prompt string for Comet MCP
    """
    sectors = queue_item.get('sectors', [])
    if isinstance(sectors, str):
        try:
            sectors = json.loads(sectors)
        except (json.JSONDecodeError, TypeError):
            sectors = []

    instruments = queue_item.get('key_instruments', [])
    if isinstance(instruments, str):
        try:
            instruments = json.loads(instruments)
        except (json.JSONDecodeError, TypeError):
            instruments = []

    return COMET_DEEP_DIVE_PROMPT.format(
        headline=queue_item.get('headline', 'Unknown'),
        rationale=queue_item.get('rationale', 'N/A'),
        direction=queue_item.get('direction', 'mixed'),
        sectors=', '.join(sectors) if sectors else 'N/A',
        instruments=', '.join(instruments) if instruments else 'N/A'
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("COMET SCAN PROMPT (use in Claude Code):")
    print("=" * 60)
    print(COMET_PROMPT)
    print()

    items = get_top_macro_items()
    if items:
        print(f"Got {len(items)} items:")
        for item in items:
            print(f"  [{item['impact_score']}] {item['headline']}")
    else:
        print("No items from any source.")
