"""
Claude AI analysis module for Macro Scanner.
Takes filtered macro stories + market indicators and produces trade ideas.
"""

import json
import re
import logging

import anthropic

from config import CLAUDE_API_KEY, CLAUDE_MODEL
from indicators import format_indicators_text

logger = logging.getLogger(__name__)


def _build_analysis_prompt(top3, indicators):
    """
    Build the analysis prompt for Claude.

    Args:
        top3: List of high-impact stories from Perplexity
        indicators: Dict of market indicators

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
        '    "entry": "specific price or condition (e.g. \'on pullback to $182\' or \'at market open\')",\n'
        '    "target": "specific price level with rationale",\n'
        '    "stop_loss": "specific price level that invalidates the sector thesis",\n'
        '    "timeline": "1-4 weeks with key date catalysts if any",\n'
        '    "position_note": "optional: sizing hint or options strategy if relevant"\n'
        '  },\n'
        '  "confidence": 0-5 (0 = nothing worth trading today, 1 = speculative, '
        '3 = solid setup, 5 = highest conviction)\n'
        "}\n\n"
        "CRITICAL RULES:\n"
        "- If nothing is genuinely tradeable today, return confidence: 0 with empty trade.\n"
        "- Never recommend a trade just because news exists. No trade is a valid answer.\n"
        "- Tickers must be real, liquid, and available on US exchanges.\n"
        "- Entry/target/stop must be specific dollar amounts, not percentages.\n"
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


def analyze_macro(top3, indicators):
    """
    Analyze macro stories and indicators using Claude to produce trade ideas.

    Args:
        top3: List of high-impact stories from Perplexity
        indicators: Dict of market indicators from fetch_indicators()

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

    prompt = _build_analysis_prompt(top3, indicators)

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
