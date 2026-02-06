"""
Test script to verify Polymarket API connectivity.
Run this before setting up the database to ensure APIs are reachable.
"""

import requests
import json
import sys

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"


def parse_json_field(value):
    """Parse a field that might be a JSON string or already parsed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return value if value else []


def find_active_market(events):
    """
    Find a market with active trading (prices between 0.05 and 0.95).
    Resolved markets (0 or 1 prices) don't have orderbooks.
    """
    for event in events:
        for market in event.get('markets', []):
            prices = parse_json_field(market.get('outcomePrices'))
            clob_ids = parse_json_field(market.get('clobTokenIds'))

            if prices and len(prices) >= 2 and clob_ids:
                try:
                    yes_price = float(prices[0])
                    # Skip resolved markets (price is 0 or 1)
                    if 0.05 < yes_price < 0.95:
                        return market, clob_ids[0]
                except (ValueError, TypeError):
                    continue

    return None, None


def test_gamma_api():
    """Test Gamma API connectivity and response structure."""
    print("\n" + "=" * 60)
    print("Testing Gamma API (Market Discovery)")
    print("=" * 60)

    url = f"{GAMMA_API_BASE}/events"
    params = {"active": "true", "closed": "false", "limit": 20}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        events = response.json()

        print(f"[OK] Connected to Gamma API")
        print(f"[OK] Fetched {len(events)} events")

        if events:
            event = events[0]
            print(f"\nSample event structure:")
            print(f"  - Event ID: {event.get('id')}")
            print(f"  - Title: {event.get('title', 'N/A')[:50]}...")
            print(f"  - Markets count: {len(event.get('markets', []))}")

            # Find an active market for CLOB test
            active_market, token_id = find_active_market(events)

            if active_market:
                clob_ids = parse_json_field(active_market.get('clobTokenIds'))
                outcomes = parse_json_field(active_market.get('outcomes'))
                prices = parse_json_field(active_market.get('outcomePrices'))

                print(f"\n  Active market found:")
                print(f"    - Market ID: {active_market.get('id')}")
                print(f"    - Question: {active_market.get('question', 'N/A')[:50]}...")
                print(f"    - Outcomes: {outcomes}")
                print(f"    - Prices: {prices}")
                print(f"    - CLOB Token IDs: {len(clob_ids)} tokens")

                return events, token_id
            else:
                print("\n  [WARN] No active markets found with trading activity")
                return events, None

        return [], None

    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Gamma API error: {e}")
        return [], None


def test_clob_api(token_id):
    """Test CLOB API connectivity and orderbook structure."""
    print("\n" + "=" * 60)
    print("Testing CLOB API (Orderbook Data)")
    print("=" * 60)

    if not token_id:
        print("[SKIP] No active token ID available")
        print("       (Resolved markets with 0/1 prices don't have orderbooks)")
        return False

    url = f"{CLOB_API_BASE}/book"
    params = {"token_id": token_id}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        print(f"[OK] Connected to CLOB API")
        print(f"[OK] Token ID: {token_id[:30]}...")

        bids = data.get('bids', [])
        asks = data.get('asks', [])

        print(f"\nOrderbook structure:")
        print(f"  - Bids count: {len(bids)}")
        print(f"  - Asks count: {len(asks)}")

        # Calculate depths
        bid_depth = sum(float(b.get('size', 0)) for b in bids)
        ask_depth = sum(float(a.get('size', 0)) for a in asks)

        print(f"  - Total bid depth: {bid_depth:,.2f}")
        print(f"  - Total ask depth: {ask_depth:,.2f}")

        if bids:
            print(f"\n  Sample bid: price={bids[0].get('price')}, size={bids[0].get('size')}")
        if asks:
            print(f"  Sample ask: price={asks[0].get('price')}, size={asks[0].get('size')}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"[FAIL] CLOB API error: {e}")
        return False


def main():
    """Run all API tests."""
    print("\nPolymarket API Connectivity Test")
    print("=" * 60)

    # Test Gamma API and get a token ID from an active market
    events, token_id = test_gamma_api()

    # Test CLOB API with the token ID
    clob_ok = test_clob_api(token_id)

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

    if events and clob_ok:
        print("\n[SUCCESS] Both APIs working correctly!")
        print("\nNext steps:")
        print("  1. Copy .env.example to .env")
        print("  2. Configure your MySQL credentials in .env")
        print("  3. Run: python database.py (to initialize tables)")
        print("  4. Run: python collector.py (to start collecting data)")
    elif events:
        print("\n[PARTIAL] Gamma API works, CLOB API needs investigation")
    else:
        print("\n[FAIL] API connectivity issues detected")

    print()


if __name__ == "__main__":
    main()
