from flask import Blueprint, render_template, jsonify
from datetime import datetime

# Create the blueprint for trading suite
trading_suite_bp = Blueprint('trading_suite', __name__, url_prefix='/trading-suite')

@trading_suite_bp.route('/api/basic_chart_data')
def basic_chart_data():
    """Basic chart data for free preview - limited to BTC/USDT 1h data"""
    try:
        import requests
        
        # Only allow BTC/USDT for basic access
        symbol = 'BTCUSDT'
        interval = '1h'
        limit = 100  # Limited data points
        
        # Binance API endpoint
        url = "https://api.binance.com/api/v3/klines"
        response = requests.get(url, params={
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        })
        
        if response.status_code != 200:
            return jsonify({'success': False, 'message': 'Failed to fetch data'})
        
        data = response.json()
        
        # Process data
        processed_data = []
        for item in data:
            processed_data.append({
                'timestamp': item[0],
                'open': float(item[1]),
                'high': float(item[2]),
                'low': float(item[3]),
                'close': float(item[4]),
                'volume': float(item[5])
            })
        
        return jsonify({
            'success': True,
            'data': processed_data,
            'symbol': symbol,
            'interval': interval,
            'message': 'Basic chart data - upgrade for advanced features'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Sample data for showcase
sample_news = [
    {
        "title": "Bitcoin Consolidates Above Key Support Level",
        "timestamp": "2 hours ago",
        "category": "Technical Analysis",
        "content": "Technical indicators suggest Bitcoin is forming a strong base above critical support, with volume patterns indicating potential continuation of current trend.",
        "premium": False
    },
    {
        "title": "DeFi Yields Show Market Resilience",
        "timestamp": "4 hours ago", 
        "category": "DeFi",
        "content": "Decentralized finance protocols maintain competitive yields despite market volatility, with total value locked remaining stable across major platforms.",
        "premium": False
    },
    {
        "title": "AI Detects Unusual Whale Movement Patterns",
        "timestamp": "1 hour ago",
        "category": "Whale Alert",
        "content": "Machine learning algorithms identify significant accumulation patterns across multiple wallets, suggesting coordinated institutional activity in...",
        "premium": True
    },
    {
        "title": "Cross-Chain Bridge Activity Surges",
        "timestamp": "3 hours ago",
        "category": "Infrastructure",
        "content": "Inter-blockchain transactions reach new highs as traders optimize for yield opportunities across different networks, with AI analysis revealing...",
        "premium": True
    }
]

@trading_suite_bp.route('/')
def trading_suite():
    return render_template('trading-suite.html', sample_news=sample_news)