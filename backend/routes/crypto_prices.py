"""
Crypto Prices Blueprint
Live cryptocurrency prices using Chainlink Price Feeds
"""

from flask import Blueprint, render_template_string, jsonify
from datetime import datetime, timezone
import logging
import os
import time
import threading

# Setup logging
logger = logging.getLogger(__name__)

crypto_prices_bp = Blueprint('crypto_prices', __name__, url_prefix='/tools/crypto-prices')

# Chainlink Price Feed contract addresses on Ethereum mainnet
PRICE_FEEDS = {
    'BTC/USD': '0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c',
    'ETH/USD': '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419',
    'LINK/USD': '0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c',
    'AVAX/USD': '0xFF3EEb22B5E3dE6e705b44749C2559d704923FD7',
    'MATIC/USD': '0x7bAC85A8a13A4BcD8abb3eB7d6b4d632c5a57676'
}

# Chainlink AggregatorV3Interface ABI (only the functions we need)
AGGREGATOR_ABI = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"internalType": "uint80", "name": "roundId", "type": "uint80"},
            {"internalType": "int256", "name": "answer", "type": "int256"},
            {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
            {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
            {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "description",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Public RPC endpoints (fallback order)
PUBLIC_RPCS = [
    "https://eth.llamarpc.com",
    "https://ethereum.publicnode.com",
    "https://1rpc.io/eth",
    "https://cloudflare-eth.com"
]

# Cache configuration
CACHE_DURATION = 30  # seconds
_price_cache = {
    'data': None,
    'timestamp': 0,
    'previous_prices': {}  # Store previous prices for change indicators
}
_cache_lock = threading.Lock()

def get_web3_connection():
    """Get Web3 connection to Ethereum mainnet"""
    try:
        from web3 import Web3

        # Try environment variable first
        rpc_url = os.getenv('ETHEREUM_RPC_URL')
        if rpc_url:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
            if w3.is_connected():
                return w3

        # Try public RPCs
        for rpc in PUBLIC_RPCS:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
                if w3.is_connected():
                    logger.info(f"Connected to Ethereum via {rpc}")
                    return w3
            except Exception as e:
                logger.warning(f"Failed to connect to {rpc}: {e}")
                continue

        logger.error("Failed to connect to any Ethereum RPC")
        return None
    except Exception as e:
        logger.error(f"Web3 connection error: {e}")
        return None

def fetch_price_from_chainlink(w3, pair, address):
    """Fetch price from a Chainlink price feed contract"""
    try:
        contract = w3.eth.contract(address=address, abi=AGGREGATOR_ABI)

        # Get latest round data
        round_data = contract.functions.latestRoundData().call()
        decimals = contract.functions.decimals().call()

        # round_data returns: (roundId, answer, startedAt, updatedAt, answeredInRound)
        raw_price = round_data[1]
        updated_at = round_data[3]

        # Convert price using decimals (typically 8 for USD pairs)
        price = raw_price / (10 ** decimals)

        return {
            'pair': pair,
            'price': price,
            'decimals': decimals,
            'updatedAt': updated_at,
            'updatedAtFormatted': datetime.fromtimestamp(updated_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            'address': address,
            'success': True
        }
    except Exception as e:
        logger.error(f"Error fetching price for {pair}: {e}")
        return {
            'pair': pair,
            'price': None,
            'error': str(e),
            'success': False
        }

def get_cached_prices():
    """Get prices from cache or fetch fresh data"""
    global _price_cache

    current_time = time.time()

    with _cache_lock:
        # Check if cache is valid
        if _price_cache['data'] and (current_time - _price_cache['timestamp']) < CACHE_DURATION:
            # Return cached data with cache info
            cache_age = int(current_time - _price_cache['timestamp'])
            cached_data = _price_cache['data'].copy()
            cached_data['cached'] = True
            cached_data['cacheAge'] = cache_age
            return cached_data

    # Fetch fresh data
    w3 = get_web3_connection()

    if not w3:
        return {
            'success': False,
            'error': 'Failed to connect to Ethereum network. All RPC endpoints are unavailable.',
            'prices': [],
            'cached': False
        }

    prices = []
    for pair, address in PRICE_FEEDS.items():
        price_data = fetch_price_from_chainlink(w3, pair, address)

        # Calculate price change if we have previous data
        with _cache_lock:
            prev_price = _price_cache['previous_prices'].get(pair)
            if prev_price is not None and price_data['success'] and price_data['price']:
                change = price_data['price'] - prev_price
                change_percent = (change / prev_price) * 100 if prev_price != 0 else 0
                price_data['priceChange'] = change
                price_data['priceChangePercent'] = change_percent
            else:
                price_data['priceChange'] = 0
                price_data['priceChangePercent'] = 0

            # Update previous price
            if price_data['success'] and price_data['price']:
                _price_cache['previous_prices'][pair] = price_data['price']

        prices.append(price_data)

    fetch_time = datetime.now(timezone.utc)
    result = {
        'success': True,
        'fetchedAt': fetch_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
        'fetchedAtTimestamp': int(fetch_time.timestamp()),
        'prices': prices,
        'cached': False,
        'cacheAge': 0
    }

    # Update cache
    with _cache_lock:
        _price_cache['data'] = result.copy()
        _price_cache['timestamp'] = current_time

    return result

@crypto_prices_bp.route('/api/prices')
def api_prices():
    """API endpoint to fetch all Chainlink prices (with caching)"""
    try:
        result = get_cached_prices()
        status_code = 200 if result['success'] else 503
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}',
            'prices': [],
            'cached': False
        }), 500

@crypto_prices_bp.route('/')
def index():
    """Main page for Chainlink Price Feeds"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chainlink Price Feeds - Web3Fuel.io</title>
        <meta name="description" content="Live cryptocurrency prices powered by Chainlink decentralized oracle network. Real-time BTC, ETH, LINK, AVAX, and MATIC prices.">
        <style>
            :root {
                --primary: #00ffea;
                --secondary: #ff00ff;
                --background: #000000;
                --text: #ffffff;
                --text-muted: #a1a1aa;
                --border-color: #27272a;
                --success: #22c55e;
                --warning: #f59e0b;
                --error: #ef4444;
                --chainlink-blue: #375bd2;
            }
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                min-height: 100vh;
                color: #e6edf3;
            }
            /* Header Styles */
            header {
                position: sticky;
                top: 0;
                z-index: 40;
                width: 100%;
                border-bottom: 1px solid var(--border-color);
                background: rgba(0, 0, 0, 0.95);
                backdrop-filter: blur(20px);
                box-shadow: 0 4px 20px rgba(0, 255, 234, 0.1);
            }
            .header-container {
                display: flex;
                height: 5rem;
                align-items: center;
                justify-content: space-between;
                max-width: 1650px;
                margin: 0 auto;
                padding: 0 1.5rem;
            }
            .logo {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                transition: transform 0.3s ease;
                text-decoration: none;
                flex-shrink: 0;
                margin-right: auto;
            }
            .logo:hover {
                transform: scale(1.05);
            }
            .logo-icon {
                color: var(--secondary);
                font-size: 2rem;
                filter: drop-shadow(0 0 10px var(--secondary));
            }
            .logo-text {
                font-size: 1.75rem;
                font-weight: bold;
                text-shadow: 0 0 15px var(--primary);
                background: linear-gradient(45deg, var(--primary), var(--secondary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .nav-desktop {
                display: none;
                gap: 0.5rem;
            }
            .nav-link {
                padding: 0.5rem 1rem;
                color: var(--text-muted);
                text-decoration: none;
                transition: all 0.3s ease;
                border-radius: 6px;
                font-weight: 500;
            }
            .nav-link:hover, .nav-link.active {
                color: var(--primary);
                background: rgba(0, 255, 234, 0.1);
            }
            .menu-button {
                display: block;
                background: transparent;
                border: none;
                color: var(--text);
                font-size: 1.5rem;
                cursor: pointer;
            }
            .mobile-menu {
                display: none;
                position: fixed;
                top: 0;
                right: 0;
                width: 100%;
                max-width: 300px;
                height: 100vh;
                background: #161b22;
                z-index: 100;
                padding: 2rem;
                transform: translateX(100%);
                transition: transform 0.3s ease;
            }
            .mobile-menu.active {
                display: block;
                transform: translateX(0);
            }
            .close-menu {
                position: absolute;
                top: 1.5rem;
                right: 1.5rem;
                background: transparent;
                border: none;
                color: var(--text);
                font-size: 1.5rem;
                cursor: pointer;
            }
            .mobile-nav-link {
                display: block;
                padding: 1rem 2rem;
                color: var(--text);
                text-decoration: none;
                border-radius: 8px;
                transition: all 0.3s ease;
            }
            .mobile-nav-link:hover {
                color: var(--primary);
                background: rgba(0, 255, 234, 0.1);
            }
            @media (min-width: 768px) {
                .nav-desktop {
                    display: flex;
                }
                .menu-button {
                    display: none;
                }
            }

            /* Main Content */
            .main-content {
                max-width: 1200px;
                margin: 0 auto;
                padding: 40px 20px;
            }

            /* Page Header */
            .page-header {
                text-align: center;
                margin-bottom: 30px;
            }
            .page-header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 15px;
                background: linear-gradient(45deg, var(--primary), var(--secondary));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .page-header .subtitle {
                color: var(--text-muted);
                font-size: 1.1rem;
                max-width: 700px;
                margin: 0 auto 20px;
                line-height: 1.6;
            }
            .oracle-explainer {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                padding: 12px 20px;
                background: rgba(55, 91, 210, 0.15);
                border: 1px solid rgba(55, 91, 210, 0.3);
                border-radius: 12px;
                color: #7b9fff;
                font-size: 0.95rem;
            }
            .oracle-explainer svg {
                flex-shrink: 0;
            }

            /* Status Bar */
            .status-bar {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(0, 0, 0, 0.6);
                border: 1px solid var(--border-color);
                border-radius: 16px;
            }
            .status-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px 15px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 10px;
            }
            .status-icon {
                width: 36px;
                height: 36px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.1rem;
            }
            .status-icon.connection {
                background: rgba(34, 197, 94, 0.2);
            }
            .status-icon.time {
                background: rgba(0, 255, 234, 0.2);
            }
            .status-icon.refresh {
                background: rgba(255, 0, 255, 0.2);
            }
            .status-content {
                flex: 1;
            }
            .status-label {
                font-size: 0.75rem;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .status-value {
                font-size: 0.95rem;
                font-weight: 600;
                color: var(--text);
            }
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: var(--success);
                animation: pulse 2s infinite;
                display: inline-block;
                margin-right: 6px;
            }
            .status-dot.error {
                background: var(--error);
                animation: none;
            }
            .status-dot.loading {
                background: var(--warning);
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(0.9); }
            }
            .refresh-btn {
                padding: 12px 24px;
                background: linear-gradient(135deg, var(--primary), var(--secondary));
                color: black;
                border: none;
                border-radius: 10px;
                font-weight: 700;
                font-size: 0.95rem;
                cursor: pointer;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
                justify-content: center;
            }
            .refresh-btn:hover:not(:disabled) {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0, 255, 234, 0.4);
            }
            .refresh-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            .refresh-btn .spinner {
                width: 16px;
                height: 16px;
                border: 2px solid transparent;
                border-top-color: black;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
                display: none;
            }
            .refresh-btn.loading .spinner {
                display: block;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }

            /* Price Cards Grid */
            .prices-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }

            /* Price Card */
            .price-card {
                background: rgba(0, 0, 0, 0.8);
                border: 2px solid var(--border-color);
                border-radius: 20px;
                padding: 24px;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            .price-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, var(--primary), var(--secondary));
            }
            .price-card:hover {
                transform: translateY(-6px);
                box-shadow: 0 12px 40px rgba(0, 255, 234, 0.2);
                border-color: var(--primary);
            }
            .price-card.loading {
                opacity: 0.7;
            }
            .price-card.error {
                border-color: var(--error);
            }
            .price-card.error::before {
                background: var(--error);
            }
            .price-card.price-up {
                border-color: var(--success);
            }
            .price-card.price-up::before {
                background: var(--success);
            }
            .price-card.price-down {
                border-color: var(--error);
            }
            .price-card.price-down::before {
                background: var(--error);
            }

            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }
            .pair-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .token-icon {
                width: 48px;
                height: 48px;
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.1);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.4rem;
            }
            .pair-name {
                font-size: 1.3rem;
                font-weight: 700;
                color: var(--text);
            }
            .pair-network {
                font-size: 0.75rem;
                color: var(--text-muted);
                margin-top: 2px;
            }
            .price-change-badge {
                display: flex;
                align-items: center;
                gap: 4px;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
            }
            .price-change-badge.up {
                background: rgba(34, 197, 94, 0.2);
                color: var(--success);
            }
            .price-change-badge.down {
                background: rgba(239, 68, 68, 0.2);
                color: var(--error);
            }
            .price-change-badge.neutral {
                background: rgba(255, 255, 255, 0.1);
                color: var(--text-muted);
            }

            .price-value {
                font-size: 2.2rem;
                font-weight: 700;
                color: var(--text);
                margin-bottom: 16px;
                font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                display: flex;
                align-items: baseline;
                gap: 8px;
            }
            .price-value .arrow {
                font-size: 1.5rem;
            }
            .price-value .arrow.up {
                color: var(--success);
            }
            .price-value .arrow.down {
                color: var(--error);
            }
            .price-value.loading {
                color: var(--text-muted);
            }

            .card-footer {
                display: flex;
                flex-direction: column;
                gap: 10px;
                padding-top: 16px;
                border-top: 1px solid var(--border-color);
            }
            .footer-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 0.85rem;
            }
            .footer-label {
                color: var(--text-muted);
            }
            .footer-value {
                color: var(--text);
                font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
            }
            .footer-value a {
                color: var(--primary);
                text-decoration: none;
                transition: opacity 0.2s;
            }
            .footer-value a:hover {
                opacity: 0.8;
                text-decoration: underline;
            }

            /* Tooltip styles */
            .tooltip-container {
                position: relative;
                display: inline-block;
            }
            .tooltip-container .tooltip {
                visibility: hidden;
                background-color: #1a1a2e;
                color: var(--text);
                text-align: center;
                padding: 8px 12px;
                border-radius: 8px;
                border: 1px solid var(--border-color);
                position: absolute;
                z-index: 10;
                bottom: 125%;
                left: 50%;
                transform: translateX(-50%);
                white-space: nowrap;
                font-size: 0.8rem;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                opacity: 0;
                transition: opacity 0.2s;
            }
            .tooltip-container .tooltip::after {
                content: "";
                position: absolute;
                top: 100%;
                left: 50%;
                margin-left: -5px;
                border-width: 5px;
                border-style: solid;
                border-color: #1a1a2e transparent transparent transparent;
            }
            .tooltip-container:hover .tooltip {
                visibility: visible;
                opacity: 1;
            }
            .docs-link {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                color: var(--chainlink-blue);
                font-size: 0.8rem;
                text-decoration: none;
                margin-top: 8px;
                padding: 4px 8px;
                background: rgba(55, 91, 210, 0.1);
                border-radius: 6px;
                transition: all 0.2s;
            }
            .docs-link:hover {
                background: rgba(55, 91, 210, 0.2);
                color: #7b9fff;
            }

            /* Error Message */
            .error-card {
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid var(--error);
                border-radius: 16px;
                padding: 30px;
                text-align: center;
                color: var(--error);
                grid-column: 1 / -1;
            }
            .error-card h3 {
                margin-bottom: 10px;
            }
            .error-card p {
                color: var(--text-muted);
            }

            /* Loading Skeleton */
            .skeleton {
                background: linear-gradient(90deg, #27272a 25%, #3f3f46 50%, #27272a 75%);
                background-size: 200% 100%;
                animation: shimmer 1.5s infinite;
                border-radius: 6px;
            }
            @keyframes shimmer {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
            .skeleton-price {
                height: 44px;
                width: 160px;
                margin-bottom: 16px;
            }
            .skeleton-text {
                height: 18px;
                width: 100%;
            }

            /* Footer Section */
            .footer-section {
                margin-top: 40px;
                padding: 30px;
                background: rgba(0, 0, 0, 0.5);
                border: 1px solid var(--border-color);
                border-radius: 20px;
            }
            .footer-section h2 {
                font-size: 1.4rem;
                margin-bottom: 20px;
                color: var(--text);
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .footer-section p {
                color: var(--text-muted);
                line-height: 1.7;
                margin-bottom: 15px;
                font-size: 0.95rem;
            }
            .footer-section a {
                color: var(--primary);
                text-decoration: none;
            }
            .footer-section a:hover {
                text-decoration: underline;
            }
            .chainlink-footer {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                margin-top: 25px;
                padding-top: 20px;
                border-top: 1px solid var(--border-color);
                color: var(--chainlink-blue);
                font-weight: 600;
            }

            /* Responsive */
            @media (max-width: 768px) {
                .page-header h1 {
                    font-size: 1.8rem;
                }
                .page-header .subtitle {
                    font-size: 1rem;
                }
                .prices-grid {
                    grid-template-columns: 1fr;
                }
                .price-value {
                    font-size: 1.8rem;
                }
                .status-bar {
                    grid-template-columns: 1fr;
                }
                .oracle-explainer {
                    flex-direction: column;
                    text-align: center;
                }
            }
            @media (max-width: 480px) {
                .main-content {
                    padding: 20px 15px;
                }
                .price-card {
                    padding: 20px;
                }
                .token-icon {
                    width: 40px;
                    height: 40px;
                }
                .pair-name {
                    font-size: 1.1rem;
                }
                .price-value {
                    font-size: 1.6rem;
                }
            }
        </style>
    </head>
    <body>
        <!-- Header -->
        <header>
            <div class="header-container">
                <a href="/" class="logo">
                    <span class="logo-icon">&#128640;</span>
                    <span class="logo-text">Web3Fuel.io</span>
                </a>
                <nav class="nav-desktop">
                    <a href="/tools" class="nav-link active">Tools</a>
                    <a href="/research" class="nav-link">Research</a>
                    <a href="/blog" class="nav-link">Blog</a>
                    <a href="/contact" class="nav-link">Contact</a>
                </nav>
                <button class="menu-button" id="menu-button">&#9776;</button>
            </div>
            <!-- Mobile Menu -->
            <div class="mobile-menu" id="mobile-menu">
                <button class="close-menu" id="close-menu">&#10005;</button>
                <nav>
                    <a href="/tools" class="mobile-nav-link active">Tools</a>
                    <a href="/research" class="mobile-nav-link">Research</a>
                    <a href="/blog" class="mobile-nav-link">Blog</a>
                    <a href="/contact" class="mobile-nav-link">Contact</a>
                </nav>
            </div>
        </header>

        <div class="main-content">
            <!-- Page Header -->
            <div class="page-header">
                <h1>Chainlink Price Feeds</h1>
                <p class="subtitle">
                    Live prices from Chainlink's decentralized oracle network. These prices are fetched directly from
                    smart contracts on Ethereum mainnet, ensuring tamper-proof and verifiable data.
                </p>
                <div class="oracle-explainer">
                    <svg width="24" height="24" viewBox="0 0 32 32" fill="currentColor">
                        <path d="M16 0l3.538 2.05v4.1L16 8.2l-3.538-2.05v-4.1L16 0zm0 23.8l-3.538-2.05v-4.1L16 15.6l3.538 2.05v4.1L16 23.8zm-6.154-10.85L6.308 14.9l-3.538-2.05v-4.1l3.538-2.05 3.538 2.05v4.1zm12.308 0v-4.1l3.538-2.05 3.538 2.05v4.1l-3.538 2.05-3.538-2.05zm-12.308 8.2l-3.538-2.05v-4.1l3.538-2.05 3.538 2.05v4.1l-3.538 2.05zm12.308 0v-4.1l3.538-2.05v4.1l-3.538 2.05-3.538-2.05v4.1l3.538 2.05zM16 32l-3.538-2.05v-4.1L16 23.8l3.538 2.05v4.1L16 32z"/>
                    </svg>
                    Decentralized oracles aggregate data from multiple premium sources
                </div>
            </div>

            <!-- Status Bar -->
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-icon connection">&#128994;</div>
                    <div class="status-content">
                        <div class="status-label">Connection</div>
                        <div class="status-value">
                            <span class="status-dot" id="status-dot"></span>
                            <span id="status-text">Connecting...</span>
                        </div>
                    </div>
                </div>
                <div class="status-item">
                    <div class="status-icon time">&#128337;</div>
                    <div class="status-content">
                        <div class="status-label">Last Refreshed</div>
                        <div class="status-value" id="last-refreshed">--</div>
                    </div>
                </div>
                <div class="status-item">
                    <div class="status-icon refresh">&#128260;</div>
                    <div class="status-content">
                        <div class="status-label">Next Update</div>
                        <div class="status-value" id="countdown">30s</div>
                    </div>
                </div>
                <button class="refresh-btn" id="refresh-btn" onclick="manualRefresh()">
                    <span class="spinner"></span>
                    <span class="btn-text">Refresh Now</span>
                </button>
            </div>

            <!-- Price Cards -->
            <div class="prices-grid" id="prices-grid">
                <!-- Cards will be populated by JavaScript -->
            </div>

            <!-- Footer Section -->
            <div class="footer-section">
                <h2>&#128279; About Chainlink Price Feeds</h2>
                <p>
                    Chainlink Price Feeds provide highly reliable, decentralized price data for cryptocurrencies and other assets.
                    Each price feed is maintained by a decentralized network of oracle nodes that aggregate data from
                    multiple premium data sources, providing high availability and protection against data manipulation.
                </p>
                <p>
                    Learn more:
                    <a href="https://data.chain.link/" target="_blank" rel="noopener">Chainlink Data Feeds</a> |
                    <a href="https://docs.chain.link/data-feeds/price-feeds" target="_blank" rel="noopener">Documentation</a> |
                    <a href="https://chain.link/" target="_blank" rel="noopener">Chainlink Website</a>
                </p>
                <div class="chainlink-footer">
                    <svg width="28" height="28" viewBox="0 0 32 32" fill="currentColor">
                        <path d="M16 0l3.538 2.05v4.1L16 8.2l-3.538-2.05v-4.1L16 0zm0 23.8l-3.538-2.05v-4.1L16 15.6l3.538 2.05v4.1L16 23.8zm-6.154-10.85L6.308 14.9l-3.538-2.05v-4.1l3.538-2.05 3.538 2.05v4.1zm12.308 0v-4.1l3.538-2.05 3.538 2.05v4.1l-3.538 2.05-3.538-2.05zm-12.308 8.2l-3.538-2.05v-4.1l3.538-2.05 3.538 2.05v4.1l-3.538 2.05zm12.308 0v-4.1l3.538-2.05v4.1l-3.538 2.05-3.538-2.05v4.1l3.538 2.05zM16 32l-3.538-2.05v-4.1L16 23.8l3.538 2.05v4.1L16 32z"/>
                    </svg>
                    Powered by Chainlink Price Feeds
                </div>
            </div>
        </div>

        <script>
            // Token icons, names, and Chainlink docs links
            const tokenData = {
                'BTC/USD': {
                    icon: '&#8383;',
                    name: 'Bitcoin',
                    docsUrl: 'https://data.chain.link/feeds/ethereum/mainnet/btc-usd'
                },
                'ETH/USD': {
                    icon: '&#926;',
                    name: 'Ethereum',
                    docsUrl: 'https://data.chain.link/feeds/ethereum/mainnet/eth-usd'
                },
                'LINK/USD': {
                    icon: '&#9830;',
                    name: 'Chainlink',
                    docsUrl: 'https://data.chain.link/feeds/ethereum/mainnet/link-usd'
                },
                'AVAX/USD': {
                    icon: '&#9650;',
                    name: 'Avalanche',
                    docsUrl: 'https://data.chain.link/feeds/ethereum/mainnet/avax-usd'
                },
                'MATIC/USD': {
                    icon: '&#9733;',
                    name: 'Polygon',
                    docsUrl: 'https://data.chain.link/feeds/ethereum/mainnet/matic-usd'
                }
            };

            // State
            const REFRESH_INTERVAL = 30;
            let countdownValue = REFRESH_INTERVAL;
            let countdownTimer = null;
            let lastFetchTime = null;
            let isRefreshing = false;

            // Format price with appropriate decimals
            function formatPrice(price) {
                if (price === null || price === undefined) return '--';
                if (price >= 1000) {
                    return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                } else if (price >= 1) {
                    return '$' + price.toFixed(4);
                } else {
                    return '$' + price.toFixed(6);
                }
            }

            // Truncate Ethereum address
            function truncateAddress(address) {
                return address.slice(0, 6) + '...' + address.slice(-4);
            }

            // Format time ago
            function formatTimeAgo(seconds) {
                if (seconds < 60) return `${seconds}s ago`;
                if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
                return `${Math.floor(seconds / 3600)}h ago`;
            }

            // Create loading card HTML
            function createLoadingCard(pair) {
                const data = tokenData[pair] || { icon: '?', name: pair };
                return `
                    <div class="price-card loading" data-pair="${pair}">
                        <div class="card-header">
                            <div class="pair-info">
                                <div class="token-icon">${data.icon}</div>
                                <div>
                                    <div class="pair-name">${pair}</div>
                                    <div class="pair-network">Ethereum Mainnet</div>
                                </div>
                            </div>
                        </div>
                        <div class="skeleton skeleton-price"></div>
                        <div class="card-footer">
                            <div class="skeleton skeleton-text"></div>
                            <div class="skeleton skeleton-text" style="width: 80%; margin-top: 8px;"></div>
                        </div>
                    </div>
                `;
            }

            // Get change class
            function getChangeClass(change) {
                if (change > 0) return 'up';
                if (change < 0) return 'down';
                return 'neutral';
            }

            // Create price card HTML
            function createPriceCard(data) {
                const pair = data.pair;
                const isError = !data.success;
                const tokenInfo = tokenData[pair] || { icon: '?', name: pair };
                const changeClass = getChangeClass(data.priceChange || 0);
                const changePercent = data.priceChangePercent || 0;
                const arrow = changeClass === 'up' ? '&#9650;' : changeClass === 'down' ? '&#9660;' : '';

                return `
                    <div class="price-card ${isError ? 'error' : ''} ${!isError && changeClass !== 'neutral' ? 'price-' + changeClass : ''}" data-pair="${pair}">
                        <div class="card-header">
                            <div class="pair-info">
                                <div class="token-icon">${tokenInfo.icon}</div>
                                <div>
                                    <div class="pair-name">${pair}</div>
                                    <div class="pair-network">Ethereum Mainnet</div>
                                </div>
                            </div>
                            ${!isError ? `
                                <div class="price-change-badge ${changeClass}">
                                    ${arrow} ${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%
                                </div>
                            ` : ''}
                        </div>
                        <div class="price-value ${isError ? 'error' : ''}">
                            ${isError ? 'Error' : formatPrice(data.price)}
                            ${!isError && changeClass !== 'neutral' ? `<span class="arrow ${changeClass}">${arrow}</span>` : ''}
                        </div>
                        <div class="card-footer">
                            ${isError ? `
                                <div class="footer-item">
                                    <span class="footer-label">Error:</span>
                                    <span class="footer-value" style="color: var(--error);">${data.error || 'Failed to fetch'}</span>
                                </div>
                            ` : `
                                <div class="footer-item">
                                    <span class="footer-label">On-chain Update</span>
                                    <span class="footer-value">${data.updatedAtFormatted || '--'}</span>
                                </div>
                                <div class="footer-item">
                                    <span class="footer-label">Contract</span>
                                    <span class="footer-value">
                                        <span class="tooltip-container">
                                            <a href="https://etherscan.io/address/${data.address}" target="_blank" rel="noopener">
                                                ${truncateAddress(data.address)} &#8599;
                                            </a>
                                            <span class="tooltip">${data.address}</span>
                                        </span>
                                    </span>
                                </div>
                                <div class="footer-item" style="justify-content: center;">
                                    <a href="${tokenInfo.docsUrl}" target="_blank" rel="noopener" class="docs-link">
                                        <svg width="14" height="14" viewBox="0 0 32 32" fill="currentColor">
                                            <path d="M16 0l3.538 2.05v4.1L16 8.2l-3.538-2.05v-4.1L16 0z"/>
                                        </svg>
                                        View on Chainlink
                                    </a>
                                </div>
                            `}
                        </div>
                    </div>
                `;
            }

            // Update status display
            function updateStatus(status, message) {
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');

                dot.className = 'status-dot ' + status;
                text.textContent = message;
            }

            // Update last refreshed time
            function updateLastRefreshed() {
                const lastRefreshed = document.getElementById('last-refreshed');
                if (lastFetchTime) {
                    const secondsAgo = Math.floor((Date.now() - lastFetchTime) / 1000);
                    lastRefreshed.textContent = formatTimeAgo(secondsAgo);
                }
            }

            // Fetch prices from API
            async function fetchPrices(manual = false) {
                if (isRefreshing) return;

                const grid = document.getElementById('prices-grid');
                const refreshBtn = document.getElementById('refresh-btn');

                isRefreshing = true;
                refreshBtn.disabled = true;
                refreshBtn.classList.add('loading');
                refreshBtn.querySelector('.btn-text').textContent = 'Fetching...';
                updateStatus('loading', 'Fetching prices...');

                // Show loading state if no cards exist
                if (grid.children.length === 0) {
                    const pairs = ['BTC/USD', 'ETH/USD', 'LINK/USD', 'AVAX/USD', 'MATIC/USD'];
                    grid.innerHTML = pairs.map(pair => createLoadingCard(pair)).join('');
                }

                try {
                    const response = await fetch('/tools/crypto-prices/api/prices');
                    const data = await response.json();

                    if (data.success) {
                        grid.innerHTML = data.prices.map(price => createPriceCard(price)).join('');
                        lastFetchTime = Date.now();
                        updateLastRefreshed();

                        const cacheNote = data.cached ? ' (cached)' : '';
                        updateStatus('', 'Connected to Ethereum' + cacheNote);
                    } else {
                        updateStatus('error', data.error || 'Failed to fetch prices');
                        grid.innerHTML = `
                            <div class="error-card">
                                <h3>&#9888; Connection Error</h3>
                                <p>${data.error || 'Failed to connect to Ethereum network'}</p>
                                <p>Please try again in a moment.</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    console.error('Fetch error:', error);
                    updateStatus('error', 'Network error');
                    grid.innerHTML = `
                        <div class="error-card">
                            <h3>&#9888; Network Error</h3>
                            <p>Failed to connect to the server. Please check your connection and try again.</p>
                        </div>
                    `;
                } finally {
                    isRefreshing = false;
                    refreshBtn.disabled = false;
                    refreshBtn.classList.remove('loading');
                    refreshBtn.querySelector('.btn-text').textContent = 'Refresh Now';

                    // Reset countdown
                    countdownValue = REFRESH_INTERVAL;
                }
            }

            // Manual refresh (resets countdown)
            function manualRefresh() {
                countdownValue = REFRESH_INTERVAL;
                fetchPrices(true);
            }

            // Update countdown display
            function updateCountdown() {
                const countdown = document.getElementById('countdown');
                countdown.textContent = countdownValue + 's';

                // Update last refreshed time
                updateLastRefreshed();

                countdownValue--;

                if (countdownValue < 0) {
                    countdownValue = REFRESH_INTERVAL;
                    fetchPrices();
                }
            }

            // Mobile menu toggle
            const menuButton = document.getElementById('menu-button');
            const mobileMenu = document.getElementById('mobile-menu');
            const closeMenu = document.getElementById('close-menu');

            if (menuButton && mobileMenu) {
                menuButton.addEventListener('click', () => {
                    mobileMenu.classList.add('active');
                    document.body.style.overflow = 'hidden';
                });

                if (closeMenu) {
                    closeMenu.addEventListener('click', () => {
                        mobileMenu.classList.remove('active');
                        document.body.style.overflow = 'auto';
                    });
                }
            }

            // Initialize
            document.addEventListener('DOMContentLoaded', () => {
                // Initial fetch
                fetchPrices();

                // Start countdown timer (updates every second)
                countdownTimer = setInterval(updateCountdown, 1000);
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)
