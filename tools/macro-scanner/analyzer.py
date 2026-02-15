"""
Claude AI analysis module for Macro Scanner.
Takes filtered macro stories + market indicators and produces trade ideas.
"""

import json
import re
import logging

import anthropic
import yfinance as yf

from config import CLAUDE_API_KEY, CLAUDE_MODEL
from indicators import format_indicators_text

logger = logging.getLogger(__name__)


def _format_active_positions_section(active_positions):
    """Format active positions for injection into Claude prompt."""
    if not active_positions:
        return ""

    lines = ["\n## Active Positions (evaluate if today's catalysts affect these)"]
    for pos in active_positions:
        ticker = pos['ticker']
        direction = pos['direction'].upper()
        entry = pos.get('entry_price', '?')
        target = pos.get('target_price', '?')
        stop = pos.get('stop_loss', '?')
        lines.append(f"  - {direction} {ticker} @ ${entry} (target: ${target}, stop: ${stop})")

    lines.append("")
    return '\n'.join(lines)


def get_past_accuracy_stats():
    """
    Get formatted accuracy stats for injection into Claude's prompt.

    Returns:
        Formatted string showing win rates by setup grade, or a "no data" message.
    """
    from database import get_accuracy_by_grade

    stats = get_accuracy_by_grade(days=90)
    if not stats:
        return "No past trade outcomes resolved yet."

    lines = []
    for grade in ['A+', 'A', 'B+', 'B', 'C']:
        if grade in stats:
            s = stats[grade]
            lines.append(
                f"  - {grade} trades: {s['wins']}/{s['total']} wins "
                f"({s['win_rate']}%), avg move {s['avg_move']:+.1f}%"
            )

    return '\n'.join(lines) if lines else "No past trade outcomes resolved yet."


def _build_analysis_prompt(top3, indicators, active_positions=None):
    """
    Build the analysis prompt for Claude.

    Args:
        top3: List of high-impact stories from Perplexity
        indicators: Dict of market indicators
        active_positions: Optional list of active position dicts

    Returns:
        Prompt string
    """
    # Format stories
    stories_text = ""
    for i, story in enumerate(top3, 1):
        stories_text += f"\n{i}. {story.get('headline', 'Unknown')}\n"
        stories_text += f"   Impact: {story.get('impact_score', '?')}/10 | Direction: {story.get('direction', '?')}\n"
        stories_text += f"   Sectors: {', '.join(story.get('affected_sectors', []))}\n"
        rationale = story.get('rationale') or story.get('summary', '')
        if rationale:
            stories_text += f"   {rationale}\n"
        instruments = story.get('key_instruments', [])
        if instruments:
            stories_text += f"   Key instruments: {', '.join(instruments)}\n"

    # Format indicators as market regime context
    indicators_text = format_indicators_text(indicators) if indicators else "N/A"

    return (
        "You are an elite macro trader at a top prop desk with 20+ years of experience. "
        "You manage a swing trading book (1-4 week horizon) and only take trades with "
        "clear asymmetric risk/reward.\n\n"

        "## Your Analysis Framework\n"
        "1. MARKET REGIME: Use the indicators below to determine if the broad market is "
        "trending up, down, or range-bound. SPY trend = equity regime, VIX level = fear/complacency "
        "(VIX <15 = complacent, 15-20 = normal, 20-30 = elevated fear, >30 = panic), "
        "DXY direction = dollar strength (strong USD = headwind for commodities/EM/multinational earnings), "
        "QQQ vs SPY relative strength = risk appetite.\n"
        "2. SECTOR PREDICTION: This is the core of your job. Read the macro catalysts and "
        "predict which sectors will benefit or suffer over the next 1-4 weeks. Think in terms of "
        "cause-and-effect chains:\n"
        "   - Rate cut signals → financials, real estate, growth tech\n"
        "   - Oil supply disruption → energy up, airlines/transport down\n"
        "   - Strong jobs data → consumer discretionary up, rate-sensitive down\n"
        "   - Trade war escalation → domestic small-caps up, multinationals down\n"
        "   - Dollar weakening → commodities, EM, exporters up\n"
        "   Identify the 1-2 sectors with the clearest directional catalyst.\n"
        "3. TICKER SELECTION: Within your predicted sector, pick the 1-2 best tickers to trade. "
        "Prefer sector ETFs (XLE, XLF, XLK, XBI, XHB, etc.) or high-beta leaders within the sector "
        "(e.g. OXY/SLB for energy, NVDA/AMD for semis, JPM/GS for financials). "
        "Avoid broad market ETFs like SPY/QQQ unless the catalyst is truly market-wide.\n"
        "4. TRADE CONSTRUCTION: Calculate concrete entry, target, and stop-loss levels. "
        "The stop should be at a price level that invalidates your sector thesis, "
        "not an arbitrary percentage.\n\n"

        f"## Market Indicators (6h snapshot)\n{indicators_text}\n\n"
        f"## Today's Macro Catalysts\n{stories_text}\n"

        f"\n## Your Past Track Record (last 90 days)\n"
        f"{get_past_accuracy_stats()}\n"
        "Use this to calibrate your confidence and grading. If your high-grade setups "
        "are underperforming, be more selective. If low grades are winning, you may be "
        "too conservative.\n"

        f"{_format_active_positions_section(active_positions)}"

        "\n## Output Format\n"
        "Return ONLY a JSON object:\n"
        "{\n"
        '  "narrative": "1-2 sentences: what happened and why it matters for markets",\n'
        '  "market_regime": "bullish" or "bearish" or "neutral",\n'
        '  "sector_impact": "which sector(s) this catalyst most affects and in which direction",\n'
        '  "trade": {\n'
        '    "direction": "long" or "short",\n'
        '    "tickers": ["TICKER1", "TICKER2"],\n'
        '    "thesis": "1 sentence connecting the macro catalyst → sector impact → why these specific tickers",\n'
        '    "timeline": "1-4 weeks with key date catalysts if any",\n'
        '    "position_note": "optional: sizing hint or options strategy if relevant"\n'
        '  },\n'
        '  "confidence": 0-5 (0 = nothing worth trading today, 1 = speculative, '
        '3 = solid setup, 5 = highest conviction),\n'
        '  "setup_grade": "A+" or "A" or "B+" or "B" or "C",\n'
        '  "position_alerts": [{"ticker": "XLE", "alert_text": "why this catalyst affects the position", '
        '"suggested_action": "hold" or "tighten_stop" or "take_profit" or "close"}]\n'
        "}\n\n"
        "POSITION ALERTS: Only include position_alerts if active positions exist above AND "
        "today's catalysts meaningfully affect them. Omit the field entirely otherwise.\n\n"
        "SETUP GRADE (holistic assessment of the entire opportunity):\n"
        "- A+ = Rare. Catalyst is unambiguous, regime + indicators strongly confirm direction, "
        "sector is not yet priced in, clear asymmetric R:R. Multiple signals align.\n"
        "- A = Strong. Clear catalyst with directional conviction, regime supports the trade, "
        "good sector read, solid R:R.\n"
        "- B+ = Above average. Catalyst is real but market may partially price it in, or "
        "one indicator diverges. Still worth trading.\n"
        "- B = Moderate. Decent catalyst but regime is mixed, or sector impact is unclear. "
        "Smaller position warranted.\n"
        "- C = Weak. Catalyst is ambiguous, indicators conflict, or move is likely priced in. "
        "Speculative at best.\n\n"
        "The grade should reflect the TOTAL picture: catalyst strength + regime alignment + "
        "indicator confluence + sector clarity + timing. A confidence-5 trade should be A or A+. "
        "Confidence 0-1 should be C.\n\n"
        "CRITICAL RULES:\n"
        "- If nothing is genuinely tradeable today, return confidence: 0 with empty trade.\n"
        "- Never recommend a trade just because news exists. No trade is a valid answer.\n"
        "- Tickers must be real, liquid, and available on US exchanges.\n"
        "- DO NOT include entry, target, or stop_loss prices — those will be calculated "
        "separately using live market data. Only provide tickers, direction, thesis, and timeline.\n"
        "- Consider whether the sector move is already priced in before recommending.\n"
        "- Think about which way the sector was trending BEFORE this catalyst — "
        "a catalyst that accelerates an existing trend is higher conviction than a reversal.\n"
        "- Return ONLY the JSON, no commentary."
    )


def _extract_confidence(result):
    """
    Extract confidence score from parsed analysis result.

    Args:
        result: Parsed analysis dict

    Returns:
        Integer 0-5, defaults to 1 if not found
    """
    # New format: confidence is a top-level int field
    conf = result.get('confidence')
    if isinstance(conf, int):
        return max(0, min(5, conf))

    # Fallback: try parsing from trade_idea text (legacy format)
    trade_idea = result.get('trade_idea', '')
    if not trade_idea:
        return 1

    patterns = [
        r'CONFIDENCE:\s*(\d)\s*/\s*5',
        r'[Cc]onfidence:\s*(\d)\s*/\s*5',
        r'[Cc]onf(?:idence)?[\s:]+(\d)/5',
    ]

    for pattern in patterns:
        match = re.search(pattern, str(trade_idea))
        if match:
            score = int(match.group(1))
            return max(0, min(5, score))

    return 1


# US ticker → TSX equivalent mapping (sector ETFs and common instruments)
_TSX_EQUIVALENTS = {
    # Broad market
    "SPY": "ZSP.TO",     # BMO S&P 500
    "QQQ": "ZQQ.TO",     # BMO Nasdaq 100
    "IWM": "XSU.TO",     # iShares US Small Cap
    "DIA": "ZDJ.TO",     # BMO Dow Jones
    # Sector ETFs
    "XLE": "XEG.TO",     # iShares S&P/TSX Capped Energy
    "XLF": "ZEB.TO",     # BMO Equal Weight Banks
    "XLK": "XIT.TO",     # iShares S&P/TSX Capped IT
    "XLV": "XHC.TO",     # iShares US Healthcare (CAD-hedged)
    "XLU": "ZUT.TO",     # BMO Equal Weight Utilities
    "XLP": "XST.TO",     # iShares S&P/TSX Capped Consumer Staples
    "XLI": "ZIN.TO",     # BMO Equal Weight Industrials
    "XLB": "XMA.TO",     # iShares S&P/TSX Capped Materials
    "XLRE": "ZRE.TO",    # BMO Equal Weight REITs
    # Commodities
    "GLD": "CGL.TO",     # iShares Gold (CAD-hedged)
    "SLV": "SVR.TO",     # Horizons Silver
    "USO": "HUC.TO",     # Horizons Crude Oil
    "UNG": "HUN.TO",     # Horizons Natural Gas
    # Bonds
    "TLT": "ZFL.TO",     # BMO Long Federal Bond
    "SHY": "ZST.TO",     # BMO Ultra Short-Term Bond
    # Volatility
    "VIXY": "HUV.TO",    # Horizons VIX Short-Term Futures
    "VXX": "HUV.TO",
    # Popular cross-listed stocks (trade directly on TSX)
    "CNQ": "CNQ.TO",
    "SU": "SU.TO",
    "ENB": "ENB.TO",
    "CP": "CP.TO",
    "CNR": "CNR.TO",
    "TD": "TD.TO",
    "RY": "RY.TO",
    "BNS": "BNS.TO",
    "BMO": "BMO.TO",
    "SHOP": "SHOP.TO",
    "BCE": "BCE.TO",
    "NTR": "NTR.TO",
    "ABX": "ABX.TO",
    "MFC": "MFC.TO",
}


def _find_tsx_equivalents(tickers):
    """
    Find TSX equivalents for US tickers.
    Checks curated mapping first, then probes yfinance for .TO listing.

    Args:
        tickers: List of US ticker symbols

    Returns:
        Dict of {us_ticker: tsx_ticker} for found equivalents
    """
    tsx_map = {}

    for ticker in tickers:
        # Check curated mapping first
        if ticker in _TSX_EQUIVALENTS:
            tsx_map[ticker] = _TSX_EQUIVALENTS[ticker]
            logger.debug(f"TSX mapping: {ticker} -> {_TSX_EQUIVALENTS[ticker]}")
            continue

        # Probe yfinance for .TO listing
        tsx_symbol = f"{ticker}.TO"
        try:
            t = yf.Ticker(tsx_symbol)
            hist = t.history(period="5d", interval="1d")
            if not hist.empty:
                tsx_map[ticker] = tsx_symbol
                logger.debug(f"TSX found via yfinance: {ticker} -> {tsx_symbol}")
        except Exception:
            pass  # No TSX equivalent found, that's fine

    return tsx_map


def _fetch_ticker_prices(tickers):
    """
    Fetch current prices for a list of tickers via yfinance.

    Args:
        tickers: List of ticker symbols (e.g. ["XLE", "OXY"])

    Returns:
        Dict of {ticker: price} for successfully fetched tickers
    """
    prices = {}
    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", interval="1d")
            if not hist.empty:
                prices[symbol] = round(float(hist['Close'].iloc[-1]), 2)
                logger.debug(f"Fetched {symbol}: ${prices[symbol]}")
            else:
                logger.warning(f"No price data for {symbol}")
        except Exception as e:
            logger.warning(f"Error fetching price for {symbol}: {e}")
    return prices


def _build_price_correction_prompt(result, prices):
    """
    Build a prompt to set entry/target/stop using real prices.

    Args:
        result: First-pass analysis dict from Claude
        prices: Dict of {ticker: current_price} from yfinance

    Returns:
        Prompt string
    """
    trade = result.get('trade', {})
    tickers = trade.get('tickers', [])
    direction = trade.get('direction', 'long')
    thesis = trade.get('thesis', '')
    timeline = trade.get('timeline', '')
    regime = result.get('market_regime', 'neutral')
    sector = result.get('sector_impact', '')

    price_lines = '\n'.join(f"  {t}: ${prices.get(t, 'N/A')}" for t in tickers)

    return (
        "You are setting entry, target, and stop-loss levels for a swing trade.\n\n"
        f"Direction: {direction.upper()}\n"
        f"Tickers: {', '.join(tickers)}\n"
        f"Current prices (LIVE from market data):\n{price_lines}\n"
        f"Thesis: {thesis}\n"
        f"Market regime: {regime}\n"
        f"Sector impact: {sector}\n"
        f"Timeline: {timeline}\n\n"
        "Return ONLY a JSON object with entry, target, and stop_loss for each ticker:\n"
        "{\n"
        '  "levels": {\n'
        '    "TICKER": {\n'
        '      "current_price": <from above>,\n'
        '      "entry": "specific price or condition based on the current price",\n'
        '      "target": "specific price level (use % move appropriate for swing trade)",\n'
        '      "stop_loss": "specific price level that invalidates the thesis"\n'
        '    }\n'
        '  }\n'
        "}\n\n"
        "RULES:\n"
        f"- For a {direction} trade, target should be "
        f"{'above' if direction == 'long' else 'below'} current price, "
        f"stop should be {'below' if direction == 'long' else 'above'}.\n"
        "- Use the EXACT current prices provided above. Do NOT use memorized prices.\n"
        "- Target: aim for 5-15% move for sector ETFs, 8-20% for individual stocks.\n"
        "- Stop: place at a logical support/resistance level, typically 3-7% from entry.\n"
        "- Risk/reward ratio should be at least 2:1.\n"
        "- Return ONLY JSON, no commentary."
    )


def _set_fallback_prices(trade, prices):
    """Set basic price info when the correction call fails."""
    tickers = trade.get('tickers', [])
    entries = []
    for t in tickers:
        if t in prices:
            entries.append(f"{t}: at market (${prices[t]})")
        else:
            entries.append(f"{t}: at market")
    trade['entry'] = '; '.join(entries)
    trade['target'] = 'see thesis'
    trade['stop_loss'] = 'see thesis'


def analyze_macro(top3, indicators, active_positions=None):
    """
    Analyze macro stories and indicators using Claude to produce trade ideas.

    Args:
        top3: List of high-impact stories from Perplexity
        indicators: Dict of market indicators from fetch_indicators()
        active_positions: Optional list of active position dicts

    Returns:
        Dict with top_3_stories, narrative, trade_idea, confidence
        or fallback dict on failure
    """
    if not CLAUDE_API_KEY:
        logger.warning("CLAUDE_API_KEY not configured - skipping analysis")
        return None

    if not top3:
        logger.warning("No stories to analyze")
        return None

    logger.info(f"Running Claude analysis on {len(top3)} stories...")

    prompt = _build_analysis_prompt(top3, indicators, active_positions=active_positions)

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = message.content[0].text

        # Parse JSON response
        result = _parse_analysis_response(content)

        if result:
            result['confidence'] = _extract_confidence(result)
            logger.info(f"Analysis complete. Confidence: {result['confidence']}/5")

            # Step 2: Fetch real prices and correct entry/target/stop
            trade = result.get('trade', {})
            tickers = trade.get('tickers', [])
            if tickers and result['confidence'] >= 2:
                logger.info(f"Fetching live prices for {tickers}...")
                prices = _fetch_ticker_prices(tickers)

                if prices:
                    logger.info(f"Live prices: {prices}")
                    correction_prompt = _build_price_correction_prompt(result, prices)

                    try:
                        correction_msg = client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=800,
                            messages=[
                                {"role": "user", "content": correction_prompt}
                            ]
                        )
                        correction_content = correction_msg.content[0].text
                        levels = _parse_analysis_response(correction_content)

                        if levels and 'levels' in levels:
                            # Merge price levels into trade object
                            all_entries = []
                            all_targets = []
                            all_stops = []

                            for ticker in tickers:
                                t_levels = levels['levels'].get(ticker, {})
                                if t_levels:
                                    price_str = f"${prices.get(ticker, '?')}"
                                    entry = t_levels.get('entry', f'at market ({price_str})')
                                    target = t_levels.get('target', 'N/A')
                                    stop = t_levels.get('stop_loss', 'N/A')

                                    all_entries.append(f"{ticker}: {entry}")
                                    all_targets.append(f"{ticker}: {target}")
                                    all_stops.append(f"{ticker}: {stop}")

                            if all_entries:
                                trade['entry'] = '; '.join(all_entries)
                                trade['target'] = '; '.join(all_targets)
                                trade['stop_loss'] = '; '.join(all_stops)
                                result['trade'] = trade
                                logger.info("Price levels corrected with live data")
                        else:
                            logger.warning("Could not parse price correction response")
                            _set_fallback_prices(trade, prices)
                            result['trade'] = trade

                    except Exception as e:
                        logger.warning(f"Price correction call failed: {e}")
                        _set_fallback_prices(trade, prices)
                        result['trade'] = trade
                else:
                    logger.warning("Could not fetch any live prices")

            # Step 3: Find TSX equivalents
            if tickers:
                logger.info(f"Looking up TSX equivalents for {tickers}...")
                tsx_map = _find_tsx_equivalents(tickers)
                if tsx_map:
                    # Fetch TSX prices
                    tsx_prices = _fetch_ticker_prices(list(tsx_map.values()))
                    tsx_alternatives = {}
                    for us_ticker, tsx_ticker in tsx_map.items():
                        tsx_price = tsx_prices.get(tsx_ticker)
                        tsx_alternatives[us_ticker] = {
                            "ticker": tsx_ticker,
                            "price": tsx_price
                        }
                    trade['tsx_alternatives'] = tsx_alternatives
                    result['trade'] = trade
                    logger.info(f"TSX equivalents: {tsx_map}")

            # Step 4: Find related Polymarket bets
            try:
                from polymarket_bridge import find_polymarket_bets
                polymarket_bet = find_polymarket_bets(
                    result.get('narrative', ''),
                    result.get('sector_impact', ''),
                    client,
                )
                if polymarket_bet:
                    result['polymarket_bet'] = polymarket_bet
            except Exception as e:
                logger.warning(f"Polymarket bridge failed (non-fatal): {e}")

            return result

        # Fallback: use raw text
        logger.warning("Could not parse Claude response as JSON, using raw text")
        return {
            'top_3_stories': top3,
            'narrative': content[:500],
            'trade_idea': content[500:1000] if len(content) > 500 else content,
            'confidence': 1
        }

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in Claude analysis: {e}")
        return None


def _parse_analysis_response(content):
    """
    Parse Claude's analysis response into structured data.

    Args:
        content: Raw response text

    Returns:
        Parsed dict or None
    """
    if not content:
        return None

    # Strip markdown code fences
    cleaned = content.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: find JSON object in text
    match = re.search(r'\{[\s\S]*\}', content)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test with dummy data
    test_stories = [
        {
            "headline": "Fed signals potential rate cut in March",
            "impact_score": 9,
            "direction": "bullish",
            "affected_sectors": ["financials", "tech", "real_estate"],
            "rationale": "Market pricing shifted significantly on dovish Fed commentary"
        }
    ]

    test_indicators = {
        "DXY": {"price": 104.52, "change_pct": -0.3},
        "VIX": {"price": 18.2, "change_pct": -2.1},
        "SPY": {"price": 502.30, "change_pct": 0.8}
    }

    print("Running Claude analysis test...")
    result = analyze_macro(test_stories, None, test_indicators)

    if result:
        print(f"\nNarrative: {result.get('narrative', 'N/A')}")
        print(f"Trade Idea: {result.get('trade_idea', 'N/A')}")
        print(f"Confidence: {result.get('confidence', 'N/A')}/5")
    else:
        print("Analysis failed (check CLAUDE_API_KEY)")
