"""
Resolution checker for Polymarket Monitor AI predictions.
Checks markets that have passed their end date and resolves predictions.
"""

import logging
from datetime import datetime

from database import get_connection, get_unresolved_predictions, resolve_prediction

logger = logging.getLogger(__name__)


def get_latest_price(market_id):
    """
    Get the most recent yes_price for a market from snapshots.

    Args:
        market_id: The market identifier

    Returns:
        Float price (0.0 to 1.0), or None if not available
    """
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT yes_price
            FROM market_snapshots
            WHERE market_id = %s
              AND yes_price IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """, (market_id,))

        result = cursor.fetchone()
        if result and result[0] is not None:
            return float(result[0])
        return None

    except Exception as e:
        logger.error(f"Error getting latest price for {market_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def determine_outcome(price):
    """
    Determine market outcome from current price.

    Args:
        price: Current yes_price (0.0 to 1.0)

    Returns:
        'YES', 'NO', or None if not yet resolved
    """
    if price is None:
        return None
    if price > 0.95:
        return 'YES'
    if price < 0.05:
        return 'NO'
    return None  # Not yet resolved


def check_prediction_correct(suggested_play, outcome):
    """
    Check if an AI prediction was correct.

    Args:
        suggested_play: 'BUY YES' or 'BUY NO'
        outcome: 'YES' or 'NO'

    Returns:
        Boolean or None if can't determine
    """
    if not suggested_play or not outcome:
        return None

    if suggested_play == 'BUY YES' and outcome == 'YES':
        return True
    if suggested_play == 'BUY NO' and outcome == 'NO':
        return True
    if suggested_play == 'BUY YES' and outcome == 'NO':
        return False
    if suggested_play == 'BUY NO' and outcome == 'YES':
        return False

    return None


def check_resolutions():
    """
    Check all unresolved predictions whose market end date has passed.
    For each, fetch current market price and determine if resolved.

    Returns:
        Number of predictions resolved
    """
    predictions = get_unresolved_predictions()

    if not predictions:
        logger.info("No unresolved predictions past their end date")
        return 0

    logger.info(f"Checking {len(predictions)} unresolved predictions...")
    resolved_count = 0

    for pred in predictions:
        prediction_id = pred['id']
        market_id = pred['market_id']
        suggested_play = pred.get('suggested_play', '')
        question = pred.get('question', 'Unknown')

        price = get_latest_price(market_id)
        outcome = determine_outcome(price)

        if outcome is None:
            logger.debug(f"Prediction {prediction_id} ({question[:40]}...): price={price}, not yet resolved")
            continue

        correct = check_prediction_correct(suggested_play, outcome)

        if correct is None:
            logger.debug(f"Prediction {prediction_id}: could not determine correctness")
            continue

        if resolve_prediction(prediction_id, outcome, correct):
            status = "CORRECT" if correct else "WRONG"
            logger.info(
                f"Resolved prediction {prediction_id}: {suggested_play} -> {outcome} [{status}] "
                f"({question[:50]}...)"
            )
            resolved_count += 1

    logger.info(f"Resolution check complete: {resolved_count}/{len(predictions)} resolved")
    return resolved_count


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("AI Prediction Resolution Checker")
    print("=" * 60)

    count = check_resolutions()
    print(f"\nResolved {count} prediction(s)")
