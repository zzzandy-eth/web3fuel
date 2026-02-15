"""
Polymarket Bridge — Cross-DB query module for Macro Scanner.
Searches the polymarket_monitor database for prediction markets related to
macro catalysts, then uses Claude to evaluate bet opportunities.
"""

import json
import re
import logging

import mysql.connector

from config import (
    POLYMARKET_DB_HOST,
    POLYMARKET_DB_USER,
    POLYMARKET_DB_PASSWORD,
    POLYMARKET_DB_NAME,
    POLYMARKET_DB_PORT,
    CLAUDE_MODEL,
)

logger = logging.getLogger(__name__)

POLYMARKET_BASE_URL = "https://polymarket.com/event"


def get_polymarket_connection():
    """
    Connect to the polymarket_monitor database.

    Returns:
        mysql.connector connection or None on failure
    """
    if not POLYMARKET_DB_PASSWORD:
        logger.debug("Polymarket DB password not configured — skipping")
        return None

    try:
        conn = mysql.connector.connect(
            host=POLYMARKET_DB_HOST,
            user=POLYMARKET_DB_USER,
            password=POLYMARKET_DB_PASSWORD,
            database=POLYMARKET_DB_NAME,
            port=POLYMARKET_DB_PORT,
            connect_timeout=10,
        )
        return conn
    except mysql.connector.Error as e:
        logger.warning(f"Could not connect to polymarket DB: {e}")
        return None


def search_related_markets(keywords, limit=5):
    """
    Search the polymarket_monitor.markets table for active markets
    matching any of the given keywords.

    Args:
        keywords: List of search keywords
        limit: Max results to return

    Returns:
        List of dicts with market info + current yes_price, sorted by relevance
    """
    conn = get_polymarket_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)

        # Build WHERE clause: match any keyword in question text
        like_clauses = []
        params = []
        for kw in keywords:
            kw = kw.strip()
            if kw:
                like_clauses.append("m.question LIKE %s")
                params.append(f"%{kw}%")

        if not like_clauses:
            return []

        where_keywords = " OR ".join(like_clauses)

        query = f"""
            SELECT
                m.market_id,
                m.question,
                m.slug,
                m.category,
                m.end_date,
                ms.yes_price,
                ms.timestamp AS snapshot_time
            FROM markets m
            INNER JOIN (
                SELECT market_id, yes_price, timestamp
                FROM market_snapshots
                WHERE (market_id, timestamp) IN (
                    SELECT market_id, MAX(timestamp)
                    FROM market_snapshots
                    GROUP BY market_id
                )
            ) ms ON m.market_id = ms.market_id
            WHERE m.active = TRUE
              AND (m.end_date IS NULL OR m.end_date > NOW())
              AND ms.yes_price BETWEEN 0.05 AND 0.95
              AND ({where_keywords})
            ORDER BY ms.timestamp DESC
            LIMIT %s
        """
        params.append(limit * 3)  # fetch extra, will re-rank by relevance

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Score by number of keyword matches in question
        for row in rows:
            q_lower = row['question'].lower()
            row['relevance'] = sum(
                1 for kw in keywords if kw.lower() in q_lower
            )

        rows.sort(key=lambda r: r['relevance'], reverse=True)

        return rows[:limit]

    except mysql.connector.Error as e:
        logger.warning(f"Polymarket market search failed: {e}")
        return []
    finally:
        conn.close()


def _extract_keywords_prompt(narrative, sector_impact):
    """Build prompt to extract search keywords from the macro catalyst."""
    return (
        "Extract 3-5 short search keywords from this macro catalyst that could match "
        "prediction market questions on Polymarket. Focus on the specific event, policy, "
        "or decision — not generic sector terms.\n\n"
        f"Narrative: {narrative}\n"
        f"Sector impact: {sector_impact}\n\n"
        "Return ONLY a JSON array of keyword strings, e.g.:\n"
        '["Fed rate cut", "March FOMC", "interest rates"]\n'
        "No commentary, just the JSON array."
    )


def _evaluate_bet_prompt(narrative, sector_impact, market):
    """Build prompt to evaluate whether a Polymarket bet is mispriced."""
    yes_pct = round(float(market['yes_price']) * 100, 1)
    return (
        "You are evaluating a prediction market bet in light of a macro catalyst.\n\n"
        f"## Macro Catalyst\n{narrative}\n\n"
        f"## Sector Impact\n{sector_impact}\n\n"
        f"## Prediction Market\n"
        f"Question: {market['question']}\n"
        f"Current YES price: {yes_pct}%\n"
        f"Category: {market.get('category', 'N/A')}\n"
        f"Resolves: {market.get('end_date', 'N/A')}\n\n"
        "Given the macro catalyst, is this market mispriced? Should a trader BUY YES or BUY NO?\n\n"
        "Return ONLY a JSON object:\n"
        "{\n"
        '  "relevant": true/false,\n'
        '  "direction": "BUY YES" or "BUY NO",\n'
        '  "edge": "1 sentence explaining why the market is mispriced given the catalyst",\n'
        '  "grade": "A+" or "A" or "B+" or "B" or "C",\n'
        '  "confidence": 1-5\n'
        "}\n\n"
        "Grade scale:\n"
        "- A+ = High conviction, catalyst directly misprices this market, strong edge\n"
        "- A = Strong setup, catalyst clearly relevant, good edge\n"
        "- B+ = Moderate-high, catalyst somewhat misprices market\n"
        "- B = Moderate, worth a small position\n"
        "- C = Weak/speculative, tenuous connection to catalyst\n\n"
        "If the market is NOT relevant to the catalyst, set relevant: false. "
        "No commentary, just JSON."
    )


def find_polymarket_bets(narrative, sector_impact, client):
    """
    Find and evaluate Polymarket bets related to a macro catalyst.

    Args:
        narrative: The macro catalyst narrative from Claude analysis
        sector_impact: Sector impact description
        client: Anthropic client instance (reused from analyzer)

    Returns:
        Dict with bet suggestion or None if no relevant match found
    """
    if not narrative:
        return None

    # Step 1: Extract search keywords via Claude
    try:
        kw_msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": _extract_keywords_prompt(narrative, sector_impact),
            }],
        )
        kw_text = kw_msg.content[0].text.strip()

        # Parse JSON array
        kw_text = re.sub(r'^```(?:json)?\s*', '', kw_text)
        kw_text = re.sub(r'\s*```$', '', kw_text)
        keywords = json.loads(kw_text)

        if not isinstance(keywords, list) or not keywords:
            logger.warning("Keyword extraction returned no usable keywords")
            return None

        logger.info(f"Polymarket search keywords: {keywords}")

    except Exception as e:
        logger.warning(f"Keyword extraction failed: {e}")
        return None

    # Step 2: Search polymarket DB
    markets = search_related_markets(keywords)

    if not markets:
        logger.info("No matching Polymarket markets found")
        return None

    logger.info(f"Found {len(markets)} candidate Polymarket market(s)")

    # Step 3: Evaluate the best match via Claude
    best = markets[0]

    try:
        eval_msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": _evaluate_bet_prompt(narrative, sector_impact, best),
            }],
        )
        eval_text = eval_msg.content[0].text.strip()

        # Parse response
        eval_text = re.sub(r'^```(?:json)?\s*', '', eval_text)
        eval_text = re.sub(r'\s*```$', '', eval_text)
        evaluation = json.loads(eval_text)

        if not evaluation.get('relevant', False):
            logger.info(f"Best match not relevant: {best['question'][:80]}")
            return None

        if evaluation.get('confidence', 0) < 2:
            logger.info(f"Polymarket bet confidence too low ({evaluation.get('confidence')})")
            return None

        # Build Polymarket URL from slug
        slug = best.get('slug', '')
        url = f"{POLYMARKET_BASE_URL}/{slug}" if slug else ""

        yes_pct = round(float(best['yes_price']) * 100, 1)

        grade = evaluation.get('grade', 'C')

        result = {
            "question": best['question'],
            "current_odds": f"{yes_pct}% YES",
            "direction": evaluation.get('direction', 'BUY YES'),
            "edge": evaluation.get('edge', ''),
            "grade": grade,
            "url": url,
            "end_date": str(best['end_date']) if best.get('end_date') else None,
            "confidence": evaluation.get('confidence', 2),
        }

        logger.info(
            f"Polymarket bet: {grade} {result['direction']} on \"{best['question'][:60]}\" "
            f"(currently {result['current_odds']})"
        )
        return result

    except Exception as e:
        logger.warning(f"Polymarket bet evaluation failed: {e}")
        return None
