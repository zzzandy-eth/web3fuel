"""
AI Context Analysis module for Polymarket Monitor.
Uses Claude API to analyze spike causes with news context.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta

import anthropic
import requests

from config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Anthropic API key (shared with reply assistant)
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')

# Claude model to use (haiku is fast and cheap, sonnet for better analysis)
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-3-haiku-20240307')

# Maximum tokens for Claude response
MAX_TOKENS = 300

# News search settings
NEWS_SEARCH_RESULTS = 5  # Number of news results to fetch
NEWS_SEARCH_TIMEOUT = 10  # Seconds

# Brave Search API (free tier: 2000 queries/month)
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY', '')


# =============================================================================
# News Search Functions
# =============================================================================

def search_news_brave(query, num_results=NEWS_SEARCH_RESULTS):
    """
    Search for recent news using Brave Search API.
    Free tier: 2000 queries/month.

    Args:
        query: Search query string
        num_results: Number of results to return

    Returns:
        List of dicts with 'title', 'description', 'url', 'age'
    """
    if not BRAVE_API_KEY:
        logger.debug("Brave API key not configured, skipping news search")
        return []

    try:
        headers = {
            'Accept': 'application/json',
            'X-Subscription-Token': BRAVE_API_KEY
        }

        params = {
            'q': query,
            'count': num_results,
            'freshness': 'pd',  # Past day
            'text_decorations': False,
            'search_lang': 'en'
        }

        response = requests.get(
            'https://api.search.brave.com/res/v1/news/search',
            headers=headers,
            params=params,
            timeout=NEWS_SEARCH_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            results = []

            for item in data.get('results', [])[:num_results]:
                results.append({
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'url': item.get('url', ''),
                    'age': item.get('age', '')
                })

            logger.info(f"Brave search returned {len(results)} results for: {query[:50]}")
            return results
        else:
            logger.warning(f"Brave search failed: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Brave search error: {e}")
        return []


def search_news_duckduckgo(query, num_results=NEWS_SEARCH_RESULTS):
    """
    Search for recent news using DuckDuckGo (no API key needed).
    Uses the duckduckgo-search library.

    Args:
        query: Search query string
        num_results: Number of results to return

    Returns:
        List of dicts with 'title', 'description', 'url'
    """
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            # Search news from the past day
            results = []
            for r in ddgs.news(query, max_results=num_results, timelimit='d'):
                results.append({
                    'title': r.get('title', ''),
                    'description': r.get('body', ''),
                    'url': r.get('url', ''),
                    'age': r.get('date', '')
                })

            logger.info(f"DuckDuckGo search returned {len(results)} results for: {query[:50]}")
            return results

    except ImportError:
        logger.warning("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return []
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []


def search_news(query, num_results=NEWS_SEARCH_RESULTS):
    """
    Search for recent news using available search providers.
    Tries Brave first (if configured), then falls back to DuckDuckGo.

    Args:
        query: Search query string
        num_results: Number of results to return

    Returns:
        List of news article dicts
    """
    # Try Brave first if API key is configured
    if BRAVE_API_KEY:
        results = search_news_brave(query, num_results)
        if results:
            return results

    # Fall back to DuckDuckGo
    return search_news_duckduckgo(query, num_results)


def extract_search_keywords(market_question):
    """
    Extract key search terms from a market question.

    Args:
        market_question: The full market question text

    Returns:
        Optimized search query string
    """
    # Remove common question patterns
    cleaned = market_question
    patterns_to_remove = [
        r'^Will\s+',
        r'^What\s+',
        r'^When\s+',
        r'^Who\s+',
        r'^How\s+',
        r'\?$',
        r'\s+by\s+\w+\s+\d+,?\s*\d*',  # "by Feb 15, 2025"
        r'\s+before\s+\w+\s+\d+,?\s*\d*',
        r'\s+in\s+\d{4}',  # "in 2025"
    ]

    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Clean up extra spaces
    cleaned = ' '.join(cleaned.split())

    # Add "news" to help find recent articles
    return f"{cleaned} news"


# =============================================================================
# Claude Analysis Functions
# =============================================================================

def analyze_spike_with_claude(spike_data, news_context=None):
    """
    Use Claude to analyze a spike and generate a hypothesis.

    Args:
        spike_data: Dict containing spike information
        news_context: Optional list of news articles for context

    Returns:
        String with AI analysis, or None on failure
    """
    if not CLAUDE_API_KEY:
        logger.warning("Claude API key not configured")
        return None

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        # Build the context
        market_question = spike_data.get('question', 'Unknown market')
        metric_type = spike_data.get('metric_type', 'unknown')
        spike_ratio = spike_data.get('spike_ratio', 0)
        baseline = spike_data.get('baseline_value', 0)
        current = spike_data.get('current_value', 0)
        yes_price = spike_data.get('yes_price')
        direction = spike_data.get('direction')  # For price momentum

        # Determine spike type description
        if metric_type == 'price_momentum':
            if direction == 'up':
                spike_description = f"Price surged UP by {spike_ratio*100:.1f} percentage points (from {baseline*100:.1f}% to {current*100:.1f}%)"
            else:
                spike_description = f"Price dropped DOWN by {spike_ratio*100:.1f} percentage points (from {baseline*100:.1f}% to {current*100:.1f}%)"
        else:
            depth_type = "bid" if "bid" in metric_type else "ask"
            spike_description = f"Orderbook {depth_type} depth spiked {spike_ratio:.1f}x (from ${baseline:,.0f} to ${current:,.0f})"

        # Format news context
        news_text = ""
        if news_context:
            news_text = "\n\nRECENT NEWS:\n"
            for i, article in enumerate(news_context[:5], 1):
                news_text += f"{i}. {article.get('title', 'No title')}\n"
                if article.get('description'):
                    news_text += f"   {article.get('description', '')[:200]}\n"
                if article.get('age'):
                    news_text += f"   ({article.get('age')})\n"

        # Build prompt
        prompt = f"""You are analyzing unusual activity on Polymarket, a prediction market platform.

MARKET QUESTION: {market_question}

DETECTED ACTIVITY:
{spike_description}
Current YES probability: {yes_price*100:.1f}% (if available: {yes_price is not None})
{news_text}

Provide a brief analysis (2-3 sentences max) explaining:
1. What likely caused this activity (news event, insider trading suspicion, whale positioning, etc.)
2. What this suggests about market sentiment

Be concise and specific. If news context is provided, reference it. If no clear cause is apparent, say so.
Do NOT include disclaimers about speculation or uncertainty - just give your best analysis."""

        # Call Claude
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        analysis = message.content[0].text.strip()
        logger.info(f"Claude analysis generated for {market_question[:50]}...")

        return analysis

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error generating Claude analysis: {e}")
        return None


# =============================================================================
# Unified Signal Analysis (Trade Suggestions + Grades)
# =============================================================================

def get_past_accuracy_stats():
    """
    Get past prediction accuracy stats grouped by grade for prompt context.

    Returns:
        Formatted string for inclusion in AI prompt, or empty string
    """
    try:
        from database import get_accuracy_by_grade
        stats = get_accuracy_by_grade(days=90)

        if not stats:
            return "No past predictions resolved yet."

        lines = []
        for grade in ['A+', 'A', 'B+', 'B', 'C']:
            if grade in stats:
                s = stats[grade]
                lines.append(f"  - {grade} calls: {s['correct']}/{s['total']} correct ({s['accuracy']}%)")

        return "\n".join(lines) if lines else "No past predictions resolved yet."

    except Exception as e:
        logger.debug(f"Could not get accuracy stats: {e}")
        return "No past predictions resolved yet."


def analyze_unified_signal(unified_alert, news_context=None):
    """
    Analyze all signals for a market and generate a trade suggestion with grade.

    Args:
        unified_alert: Dict with keys: question, yes_price, no_price, end_date,
                      signals (list of signal dicts), slug, market_id
        news_context: Optional list of news articles

    Returns:
        Dict with keys: play, grade, reasoning, key_signal, raw_analysis
        Or None on failure
    """
    if not CLAUDE_API_KEY:
        logger.debug("AI analysis disabled (no API key)")
        return None

    market_question = unified_alert.get('question', '')
    if not market_question or market_question == 'Unknown':
        return None

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        yes_price = unified_alert.get('yes_price')
        no_price = unified_alert.get('no_price')
        end_date = unified_alert.get('end_date')
        signals = unified_alert.get('signals', [])

        # Format signal descriptions
        signal_lines = []
        for sig in signals:
            sig_type = sig.get('type', 'unknown')
            if sig_type in ('orderbook_bid_depth', 'orderbook_ask_depth'):
                side = 'Bid' if 'bid' in sig_type else 'Ask'
                signal_lines.append(
                    f"- {side} Spike: {sig.get('ratio', 0):.1f}x baseline "
                    f"(${sig.get('baseline', 0):,.0f} -> ${sig.get('current', 0):,.0f})"
                )
            elif sig_type == 'price_momentum':
                direction = sig.get('direction', 'up')
                change = sig.get('ratio', 0) * 100
                signal_lines.append(
                    f"- Price Momentum: {'+' if direction == 'up' else '-'}{change:.1f}pp "
                    f"({sig.get('baseline', 0)*100:.1f}% -> {sig.get('current', 0)*100:.1f}%)"
                )
            elif sig_type == 'contrarian_whale':
                side = sig.get('contrarian_side', '?')
                signal_lines.append(
                    f"- Contrarian Whale: {sig.get('ratio', 0):.1f}x influx on {side}"
                )

        signals_text = "\n".join(signal_lines) if signal_lines else "- No specific signals"

        # Format end date
        end_date_text = "Unknown"
        if end_date:
            try:
                if hasattr(end_date, 'strftime'):
                    end_date_text = end_date.strftime("%b %d, %Y")
                else:
                    end_date_text = str(end_date)
            except Exception:
                end_date_text = str(end_date)

        # Format news
        news_text = ""
        if news_context:
            news_text = "\n\nRecent News:\n"
            for i, article in enumerate(news_context[:5], 1):
                news_text += f"{i}. {article.get('title', 'No title')}\n"
                if article.get('description'):
                    news_text += f"   {article.get('description', '')[:200]}\n"

        # Get past accuracy
        accuracy_stats = get_past_accuracy_stats()

        # Format prices
        yes_pct = f"{yes_price*100:.1f}" if yes_price is not None else "N/A"
        no_pct = f"{no_price*100:.1f}" if no_price is not None else "N/A"

        prompt = f"""You are a Polymarket trading analyst. Analyze these signals and suggest a trade.

Market: {market_question}
Current Price: {yes_pct}% YES / {no_pct}% NO
Market Ends: {end_date_text}

Detected Signals:
{signals_text}
{news_text}

Past Prediction Accuracy:
{accuracy_stats}

Respond in this exact JSON format (no markdown, no code fences, just raw JSON):
{{"play": "BUY YES" or "BUY NO" or "NO TRADE", "grade": "A+" or "A" or "B+" or "B" or "C", "reasoning": "2-3 sentences explaining the analysis", "key_signal": "which signal is most important"}}

Grade scale:
- A+ = High conviction, multiple confirming signals, strong momentum
- A = Strong setup, clear direction
- B+ = Moderate-high, some confirming signals
- B = Moderate, worth a small position
- C = Weak/speculative, signals mixed

Be concise and decisive. Do NOT hedge or add disclaimers."""

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )

        raw_response = message.content[0].text.strip()
        logger.info(f"Unified AI analysis generated for {market_question[:50]}...")

        # Parse JSON response
        try:
            # Strip code fences if present
            cleaned = raw_response
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            result['raw_analysis'] = raw_response
            return result
        except json.JSONDecodeError:
            logger.warning(f"Could not parse AI JSON response: {raw_response[:200]}")
            # Return a fallback with the raw text as reasoning
            return {
                'play': 'NO TRADE',
                'grade': 'C',
                'reasoning': raw_response[:500],
                'key_signal': 'unknown',
                'raw_analysis': raw_response
            }

    except anthropic.APIError as e:
        logger.error(f"Claude API error in unified analysis: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in unified signal analysis: {e}")
        return None


# =============================================================================
# Main Analysis Function (backward compat)
# =============================================================================

def analyze_spike(spike_data):
    """
    Main function to analyze a spike with AI context.
    Searches for relevant news and generates Claude analysis.

    Args:
        spike_data: Dict containing spike information from detector

    Returns:
        String with AI analysis, or None if analysis fails/disabled
    """
    if not CLAUDE_API_KEY:
        logger.debug("AI analysis disabled (no API key)")
        return None

    market_question = spike_data.get('question', '')
    if not market_question or market_question == 'Unknown':
        logger.debug("Skipping AI analysis - no market question")
        return None

    try:
        # Extract search keywords from market question
        search_query = extract_search_keywords(market_question)
        logger.debug(f"Searching news for: {search_query}")

        # Search for recent news
        news_results = search_news(search_query)

        # Generate Claude analysis
        analysis = analyze_spike_with_claude(spike_data, news_results)

        return analysis

    except Exception as e:
        logger.error(f"Error in spike analysis: {e}")
        return None


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("AI Context Analysis Test")
    print("=" * 60)

    # Check API key
    if not CLAUDE_API_KEY:
        print("\n[ERROR] CLAUDE_API_KEY not set in environment")
        print("        Add it to your .env file:")
        print("        CLAUDE_API_KEY=sk-ant-...")
        exit(1)

    print(f"\nClaude API Key: {'*' * 20}...{CLAUDE_API_KEY[-4:]}")
    print(f"Claude Model: {CLAUDE_MODEL}")
    print(f"Brave API Key: {'Configured' if BRAVE_API_KEY else 'Not configured (using DuckDuckGo)'}")

    # Test with sample spike data
    test_spike = {
        'market_id': 'test-123',
        'question': 'Will Trump announce military action against Iran by February 2025?',
        'metric_type': 'orderbook_bid_depth',
        'spike_ratio': 4.2,
        'baseline_value': 5000,
        'current_value': 21000,
        'yes_price': 0.35,
        'no_price': 0.65,
        'slug': 'trump-iran-military',
        'detected_at': datetime.now()
    }

    print(f"\n[TEST] Analyzing spike for: {test_spike['question'][:60]}...")
    print("-" * 60)

    # Test news search
    print("\n[1] Testing news search...")
    search_query = extract_search_keywords(test_spike['question'])
    print(f"    Search query: {search_query}")

    news = search_news(search_query)
    if news:
        print(f"    Found {len(news)} news articles:")
        for article in news[:3]:
            print(f"    - {article.get('title', 'No title')[:60]}...")
    else:
        print("    No news articles found (will analyze without news context)")

    # Test Claude analysis
    print("\n[2] Testing Claude analysis...")
    analysis = analyze_spike(test_spike)

    if analysis:
        print(f"\n[SUCCESS] AI Analysis:\n")
        print("-" * 60)
        print(analysis)
        print("-" * 60)
    else:
        print("\n[FAIL] Could not generate analysis")

    # Test price momentum
    print("\n[3] Testing price momentum analysis...")
    momentum_spike = {
        'question': 'Will Bitcoin reach $100,000 by end of 2025?',
        'metric_type': 'price_momentum',
        'spike_ratio': 0.15,  # 15 percentage point change
        'direction': 'up',
        'baseline_value': 0.45,
        'current_value': 0.60,
        'yes_price': 0.60,
        'slug': 'bitcoin-100k-2025'
    }

    analysis2 = analyze_spike(momentum_spike)
    if analysis2:
        print(f"\n[SUCCESS] Price Momentum Analysis:\n")
        print("-" * 60)
        print(analysis2)
        print("-" * 60)

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
