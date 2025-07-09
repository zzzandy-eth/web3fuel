from flask import Blueprint, render_template_string, jsonify
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

template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Suite - Web3Fuel.io</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        :root {
            --primary: #00ffea;
            --secondary: #ff00ff;
            --accent: #7c3aed;
            --background: #000000;
            --card-bg: rgba(0, 0, 0, 0.7);
            --text: #ffffff;
            --text-muted: #a1a1aa;
            --border-color: #27272a;
            --success: #00ff88;
            --danger: #ff4444;
            --warning: #ffaa00;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--background);
            color: var(--primary);
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            line-height: 1.6;
        }

        canvas {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            opacity: 0.3;
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
            animation: pulse 2s infinite;
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
            align-items: center;
            gap: 0.5rem;
            margin-left: auto;
            flex-shrink: 0;
        }

        .nav-link {
            color: var(--text);
            text-decoration: none;
            font-size: 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
            padding: 0.625rem 1rem;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            border: 1px solid transparent;
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(10px);
            white-space: nowrap;
        }

        .nav-link::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 234, 0.2), transparent);
            transition: left 0.5s ease;
        }

        .nav-link:hover::before {
            left: 100%;
        }

        .nav-link:hover {
            color: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.3);
            transform: translateY(-2px);
            background: rgba(0, 255, 234, 0.1);
        }

        .nav-link.active {
            color: var(--background);
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 25px rgba(0, 255, 234, 0.5);
        }

        .nav-link.contact-highlight {
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            background-clip: padding-box;
            border: 2px solid transparent;
            position: relative;
            overflow: hidden;
        }

        .nav-link.contact-highlight::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            padding: 2px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 8px;
            z-index: -1;
            -webkit-mask: 
                linear-gradient(#fff 0 0) content-box, 
                linear-gradient(#fff 0 0);
            -webkit-mask-composite: destination-out;
            mask-composite: subtract;
            box-sizing: border-box;
        }

        .nav-link.contact-highlight:hover {
            background: linear-gradient(135deg, rgba(0, 255, 234, 0.2), rgba(255, 0, 255, 0.2));
            color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.3);
            transform: translateY(-2px);
        }

        .menu-button {
            background: rgba(0, 255, 234, 0.1);
            border: 2px solid var(--primary);
            color: var(--primary);
            cursor: pointer;
            font-size: 1.25rem;
            padding: 0.625rem;
            border-radius: 8px;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            flex-shrink: 0;
        }

        .menu-button:hover {
            background: var(--primary);
            color: var(--background);
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.4);
        }

        @keyframes pulse {
            0%, 100% {
                filter: drop-shadow(0 0 10px var(--secondary));
            }
            50% {
                filter: drop-shadow(0 0 20px var(--secondary));
            }
        }

        @media (min-width: 768px) {
            .nav-desktop {
                display: flex;
            }
            
            .menu-button {
                display: none;
            }
            
            .header-container {
                padding: 0 3rem;
                max-width: 1650px;
            }
        }

        /* Page Header */
        .page-header {
            padding: 4rem 0;
            position: relative;
            border-bottom: 1px solid var(--border-color);
            background: none;
        }

        .hero-container {
            max-width: 75%;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr;
            gap: 3rem;
            align-items: center;
            padding: 0 2rem;
        }

        .hero-content {
            text-align: left;
        }

        .page-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            line-height: 1.2;
            color: #ffffff;
        }

        .hero-accent {
            color: var(--primary);
            text-shadow: 0 0 10px var(--primary);
            animation: glitch 2s infinite, glitch-text 2s infinite;
            position: relative;
            display: inline-block;
        }

        .hero-description {
            color: #e2e8f0;
            font-size: 1.25rem;
            line-height: 1.6;
            margin-bottom: 2rem;
            max-width: 600px;
        }

        .hero-stats-mini {
            display: flex;
            gap: 2rem;
            margin-top: 2rem;
        }

        .mini-stat {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }

        .mini-stat-value {
            color: var(--primary);
            font-size: 1.5rem;
            font-weight: 700;
            text-shadow: 0 0 10px rgba(0, 255, 234, 0.5);
        }

        .mini-stat-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.25rem;
        }

        .hero-visual {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-left: 3.5rem;
        }

        .trading-dashboard-preview {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            width: 100%;
            max-width: 400px;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.1);
            position: relative;
            overflow: hidden;
        }

        .trading-dashboard-preview::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }

        .dashboard-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }

        .dash-title {
            color: var(--text);
            font-weight: 600;
            font-size: 1.1rem;
        }

        .dash-status {
            color: var(--success);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .dashboard-content {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .chart-preview {
            height: 80px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 1rem;
            position: relative;
        }

        .chart-svg {
            width: 100%;
            height: 100%;
        }

        .dashboard-metrics {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
            margin-top: 2rem;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
        }

        .metric-label {
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .metric-value {
            color: var(--text);
            font-weight: 600;
            font-size: 1rem;
        }

        .metric-value.positive {
            color: var(--success);
        }

        /* Animation for the chart */
        @keyframes drawLine {
            from {
                stroke-dasharray: 1000;
                stroke-dashoffset: 1000;
            }
            to {
                stroke-dasharray: 1000;
                stroke-dashoffset: 0;
            }
        }

        .chart-svg polyline {
            animation: drawLine 3s ease-in-out infinite alternate;
        }

        /* Pulsing effect for online status */
        @keyframes pulse-green {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.6;
            }
        }

        .dash-status {
            animation: pulse-green 2s infinite;
        }

        /* Container - FIXED */
        .container {
            max-width: 75%;
            margin: 0 auto;
            padding: 2rem;
            position: relative;
        }

        /* Tab Navigation - FIXED */
        .tab-navigation {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0; 
            margin: 0 auto 3rem auto;
            padding: 1rem 0;
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
            overflow-x: auto;
            scrollbar-width: thin;
            width: 100%;
        }

        .tab-navigation::-webkit-scrollbar {
            height: 4px;
        }

        .tab-navigation::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.1);
        }

        .tab-navigation::-webkit-scrollbar-thumb {
            background: var(--primary);
            border-radius: 2px;
        }

        .tab-label {
            color: #ff00ff;
            font-size: 1.8rem; /* Increased from 1.1rem */
            font-weight: 700; /* Increased from 600 for more prominence */
            white-space: nowrap;
            opacity: 0.95; /* Slightly increased opacity */
            display: flex;
            align-items: center;
            gap: 0.75rem; /* Space between text and arrow */
            padding-left: 11rem;
        }

        .tab-label::after {
            content: '▶'; /* Thick right-pointing arrow */
            color: var(--primary);
            font-size: 1.5rem;
            font-weight: bold;
            text-shadow: 0 0 8px rgba(0, 255, 234, 0.5);
            padding-left: 0.5rem;
            animation: pulse-arrow 2s infinite;
        }
        
        @keyframes pulse-arrow {
            0%, 100% {
                transform: scale(1);
                opacity: 1;
            }
            50% {
                transform: scale(1.1);
                opacity: 0.8;
            }
        }

        .tab-buttons {
            display: flex;
            align-items: center;
            gap: 1rem;
            flex: 1;
            padding-right: 5rem;
            justify-content: flex-end;
        }
        
        @media (max-width: 768px) {
            .tab-navigation {
                flex-direction: column;
                align-items: stretch;
                gap: 1.5rem;
                padding: 1.5rem 1rem;
            }
            
            .tab-label {
                justify-content: center;
                font-size: 1.2rem;
                padding-left: 0;
            }
            
            .tab-buttons {
                justify-content: center;
                flex-wrap: wrap;
                padding-right: 0;
            }
        }

        .tab-btn {
            background: rgba(0, 0, 0, 0.3);
            color: var(--text-muted);
            border: 1px solid var(--border-color);
            padding: 1rem 2rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .tab-btn.active {
            background: var(--primary);
            color: black;
            border-color: var(--primary);
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.3);
        }

        .tab-btn:hover:not(.active) {
            background: rgba(0, 255, 234, 0.1);
            border-color: var(--primary);
            color: var(--primary);
        }

        /* Tab Content */
        .tab-content {
            display: none;
            animation: fadeIn 0.5s ease;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Section Styles */
        .section-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
        }

        .section-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            opacity: 0.8;
        }

        .section-title {
            color: var(--primary);
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* Market Intelligence Styles */
        .news-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
        }

        .news-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .news-card:hover {
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(0, 255, 234, 0.2);
            transform: translateY(-5px);
        }

        .news-title {
            color: var(--text);
            font-size: 1.2rem;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .news-meta {
            display: flex;
            gap: 1rem;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        .category-tag {
            background: rgba(0, 255, 234, 0.15);
            color: var(--primary);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            border: 1px solid rgba(0, 255, 234, 0.3);
        }

        .news-content {
            color: #e2e8f0;
            line-height: 1.6;
        }

        /* Technical Analysis Styles */
        .chart-placeholder {
            height: 400px;
            background: rgba(0, 0, 0, 0.3);
            border: 2px dashed var(--border-color);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 1rem;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .chart-placeholder:hover {
            border-color: var(--primary);
            background: rgba(0, 255, 234, 0.05);
        }

        .chart-placeholder::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 234, 0.1), transparent);
            animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }

        .chart-icon {
            font-size: 4rem;
            color: var(--primary);
            opacity: 0.5;
        }

        .chart-text {
            text-align: center;
            color: var(--text-muted);
        }

        .chart-text h3 {
            color: var(--primary);
            margin-bottom: 0.5rem;
        }

        /* Trading Tools Styles */
        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .tool-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }

        .tool-card:hover {
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(0, 255, 234, 0.2);
        }

        .tool-title {
            color: var(--text);
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }

        .tool-description {
            color: var(--text-muted);
            margin-bottom: 1.5rem;
            line-height: 1.5;
        }

        .tool-placeholder {
            background: rgba(0, 0, 0, 0.5);
            border: 1px dashed var(--border-color);
            border-radius: 6px;
            padding: 2rem;
            text-align: center;
            color: var(--text-muted);
            min-height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 1rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .tool-placeholder:hover {
            border-color: var(--primary);
            background: rgba(0, 255, 234, 0.05);
            color: var(--primary);
        }

        .placeholder-icon {
            font-size: 2.5rem;
            opacity: 0.5;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .form-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            font-weight: 500;
        }

        .form-input {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 0.75rem;
            color: var(--text);
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(0, 255, 234, 0.2);
        }

        .calculator-form {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .result-display {
            background: rgba(0, 255, 234, 0.1);
            border: 1px solid var(--primary);
            border-radius: 6px;
            padding: 1rem;
            margin-top: 1rem;
            display: none;
        }

        .result-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }

        .result-value {
            color: var(--primary);
            font-size: 1.2rem;
            font-weight: bold;
        }

        /* Chart Container Styles */
        .chart-container {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 2rem;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.1);
        }

        .controls-section {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .control-group label {
            color: var(--text);
            font-weight: 500;
            font-size: 0.9rem;
        }

        select, button {
            background: transparent;
            color: var(--primary);
            border: 1px solid var(--border-color);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }

        select:hover, button:hover {
            background: rgba(0, 255, 234, 0.1);
            border-color: var(--primary);
        }

        select:focus, button:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(0, 255, 234, 0.2);
        }

        .upgrade-notice {
            background: rgba(255, 165, 0, 0.1);
            border: 1px solid var(--warning);
            color: var(--warning);
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            text-align: center;
            font-size: 0.9rem;
        }

        .upgrade-btn {
            background: var(--warning);
            color: black;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            margin-left: 0.5rem;
            transition: all 0.3s ease;
        }

        .upgrade-btn:hover {
            background: #ffcc00;
            transform: translateY(-1px);
        }

        /* Access Gate Modal */
        .access-gate {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            backdrop-filter: blur(10px);
            z-index: 1000;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }

        .access-gate.show {
            display: flex;
        }

        .gate-content {
            background: var(--card-bg);
            border: 2px solid var(--primary);
            border-radius: 16px;
            padding: 3rem;
            max-width: 500px;
            width: 100%;
            text-align: center;
            box-shadow: 0 0 50px rgba(0, 255, 234, 0.3);
            position: relative;
        }

        .gate-icon {
            font-size: 4rem;
            color: var(--primary);
            margin-bottom: 1rem;
            animation: bounce 2s infinite;
        }

        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% {
                transform: translateY(0);
            }
            40% {
                transform: translateY(-10px);
            }
            60% {
                transform: translateY(-5px);
            }
        }

        .gate-title {
            color: var(--primary);
            font-size: 1.8rem;
            margin-bottom: 1rem;
            font-weight: 700;
        }

        .gate-message {
            color: var(--text);
            margin-bottom: 2rem;
            line-height: 1.6;
        }

        .gate-buttons {
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }

        .gate-btn {
            padding: 0.75rem 2rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .gate-btn.primary {
            background: var(--primary);
            color: black;
            border: 2px solid var(--primary);
        }

        .gate-btn.primary:hover {
            background: #00d6c4;
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 255, 234, 0.3);
        }

        .gate-btn.secondary {
            background: transparent;
            color: var(--text);
            border: 2px solid var(--border-color);
        }

        .gate-btn.secondary:hover {
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(0, 255, 234, 0.1);
        }

        .close-gate {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
            transition: color 0.3s ease;
        }

        .close-gate:hover {
            color: var(--primary);
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-box {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
        }

        .stat-box:hover {
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(0, 255, 234, 0.2);
        }

        .stat-label {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-size: 1.4rem;
            font-weight: bold;
            color: var(--primary);
        }

        /* Footer Styles */
        .custom-footer {
            background: rgba(0, 0, 0, 0.7);
            padding: 3rem 0 2rem 0;
            text-align: center;
            margin-top: 3rem;
            border-top: 1px solid var(--border-color);
        }

        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1rem;
        }

        .footer-main {
            display: flex;
            flex-direction: column;
            gap: 3rem;
            margin-bottom: 2rem;
        }

        .social-section {
            flex: 1;
            text-align: center;
        }

        .social-title {
            color: #ffffff;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }

        .social-links {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
            gap: 2rem;
        }

        .social-links a {
            transition: all 0.3s ease;
            margin: 5px;
        }

        .social-links a:hover {
            transform: scale(1.2);
            filter: drop-shadow(0 0 15px #00ffea);
        }

        .social-links svg {
            transition: fill 0.3s ease;
        }

        .social-links a:hover svg {
            fill: #00ffea !important;
        }

        .newsletter-section {
            flex: 1;
            text-align: center;
        }

        .newsletter-title {
            color: #ffffff;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }

        .newsletter-form {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-width: 400px;
            margin: 0 auto;
        }

        .newsletter-input {
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #27272a;
            border-radius: 0.375rem;
            color: #ffffff;
            font-size: 0.875rem;
            transition: border-color 0.3s ease;
            text-align: center;
        }

        .newsletter-input::placeholder {
            color: #a1a1aa;
            text-align: center;
        }

        .newsletter-input:focus {
            outline: none;
            border-color: #00ffea;
            box-shadow: 0 0 10px rgba(0, 255, 234, 0.2);
        }

        .newsletter-button {
            background: #00ffea;
            color: #000000;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 0.375rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .newsletter-button:hover {
            background: #00d6c4;
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 255, 234, 0.3);
        }

        .footer-divider {
            width: 100%;
            height: 1px;
            background: #27272a;
            margin: 2rem 0 1.5rem 0;
        }

        .footer-bottom {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .footer-left {
            flex: 1;
            text-align: left;
        }

        .footer-center {
            flex: 1;
            text-align: center;
        }

        .footer-right {
            flex: 1;
            text-align: right;
        }

        .footer-links {
            color: #a1a1aa;
            text-decoration: none;
            font-size: 1rem;
            transition: color 0.3s ease;
        }

        .footer-links:hover {
            color: #00ffea;
        }

        .copyright {
            color: #a1a1aa;
            font-size: 1rem;
            margin: 0;
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
        }

        /* Responsive Design - FIXED */
        @media (min-width: 768px) {
            .nav-desktop {
                display: flex;
            }
            
            .menu-button {
                display: none;
            }
            
            .header-container {
                padding: 0 3rem;
                max-width: 1650px;
            }
            
            .page-header {
                padding: 4rem 2rem;
            }
            
            .page-title {
                font-size: 3.5rem;
            }
            
            .hero-container {
                grid-template-columns: 1fr 1fr;
                gap: 4rem;
                max-width: 75%;
            }
            
            .hero-content {
                text-align: left;
            }
            
            .hero-stats-mini {
                gap: 3rem;
            }
            
            .dashboard-metrics {
                grid-template-columns: 1fr;
            }
            
            .news-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .container {
                padding: 3rem;
                max-width: 75%;
            }

            .gate-content {
                padding: 4rem;
            }

            .newsletter-form {
                flex-direction: row;
            }
            
            .newsletter-input {
                flex: 1;
            }

            .footer-main {
                flex-direction: row;
                align-items: flex-start;
            }
            
            .footer-bottom {
                justify-content: space-between;
            }
        }

        @media (min-width: 1024px) {
            .page-header {
                padding: 5rem 2rem;
            }
            
            .page-title {
                font-size: 4rem;
            }
            
            .hero-description {
                font-size: 1.3rem;
            }
            
            .hero-container {
                max-width: 75%;
            }
            
            .container {
                max-width: 75%;
            }
            
            .news-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 767px) {
            .social-links {
                gap: 1.5rem;
            }
            
            .footer-bottom {
                flex-direction: column;
                text-align: center;
                gap: 1rem;
            }

            .footer-left,
            .footer-center,
            .footer-right {
                text-align: center;
            }

            .footer-links {
                font-size: 1rem;
            }
            
            .copyright {
                order: 1;
            }
        }

        @keyframes glitch {
            2%, 64% { transform: translate(2px, 0) skew(0deg); }
            4%, 60% { transform: translate(-2px, 0) skew(0deg); }
            62% { transform: translate(0, 0) skew(5deg); }
        }

        @keyframes glitch-text {
            0% { text-shadow: 0 0 10px var(--primary); }
            2%, 64% { text-shadow: -2px 0 var(--secondary), 2px 0 var(--primary); }
            4%, 60% { text-shadow: 2px 0 var(--secondary), -2px 0 var(--primary); }
            62% { text-shadow: 0 0 10px var(--primary); }
        }
    </style>
</head>
<body>
    <canvas id="matrix"></canvas>
    
    <!-- Header -->
    <header>
        <div class="header-container">
            <a href="/" class="logo">
                <span class="logo-icon">🚀</span>
                <span class="logo-text">Web3Fuel.io</span>
            </a>
            
            <nav class="nav-desktop">
                <a href="/trading-suite" class="nav-link active">Trading Suite</a>
                <a href="/marketing-solutions" class="nav-link">Marketing Solutions</a>
                <a href="/blog" class="nav-link">Blog</a>
                <a href="/contact" class="nav-link contact-highlight">Contact</a>
            </nav>
            
            <button class="menu-button" id="menu-button">☰</button>
        </div>
    </header>
    
    <!-- Page Header -->
    <div class="page-header">
        <div class="hero-container">
            <div class="hero-content">
                <h1 class="page-title">Master the Markets with <span class="hero-accent">AI-Powered</span> Trading Intelligence</h1>
                <p class="hero-description">
                    Leverage cutting-edge AI algorithms to gain unprecedented market insights, automate trading strategies, and maximize your crypto portfolio returns.
                </p>
                <div class="hero-stats-mini">
                    <div class="mini-stat">
                        <span class="mini-stat-value">100+</span>
                        <span class="mini-stat-label">Indicators</span>
                    </div>
                    <div class="mini-stat">
                        <span class="mini-stat-value">24/7</span>
                        <span class="mini-stat-label">Market Analysis</span>
                    </div>
                    <div class="mini-stat">
                        <span class="mini-stat-value"><50ms</span>
                        <span class="mini-stat-label">Latency</span>
                    </div>
                </div>
            </div>
            
            <div class="hero-visual">
                <div class="trading-dashboard-preview">
                    <div class="dashboard-header">
                        <div class="dash-title">Live Trading Dashboard</div>
                        <div class="dash-status">🟢 Online</div>
                    </div>
                    <div class="dashboard-content">
                        <div class="chart-preview">
                            <div class="chart-line">
                                <svg viewBox="0 0 200 80" class="chart-svg">
                                    <polyline points="0,60 20,55 40,45 60,35 80,30 100,25 120,20 140,15 160,10 180,5 200,8" 
                                            fill="none" stroke="#00ffea" stroke-width="2"/>
                                    <polyline points="0,70 20,65 40,62 60,58 80,55 100,52 120,48 140,45 160,42 180,40 200,38" 
                                            fill="none" stroke="#ff00ff" stroke-width="1.5" opacity="0.6"/>
                                </svg>
                            </div>
                        </div>
                        <div class="dashboard-metrics">
                            <div class="metric">
                                <span class="metric-label">Total Value</span>
                                <span class="metric-value positive">$24,567.89</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Today's P&L</span>
                                <span class="metric-value positive">+$1,234.56</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Win Rate</span>
                                <span class="metric-value">78.4%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <!-- Tab Navigation -->
        <div class="tab-navigation">
            <div class="tab-label">Select Platform:</div>
            <div class="tab-buttons">
                <button class="tab-btn active" data-tab="valuation-lab">
                    <span>📊</span> Chart Analytics
                </button>
                <button class="tab-btn" data-tab="market-intelligence">
                    <span>📰</span> Market Research
                </button>
                <button class="tab-btn" data-tab="trading-tools">
                    <span>🤖</span> Trading Tools
                </button>
            </div>
        </div>

        <!-- Market Intelligence Tab -->
        <div class="tab-content" id="market-intelligence">
            <div class="section-card">
                <h2 class="section-title">📈 Real-Time Market Overview</h2>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-label">Total Market Cap</div>
                        <div class="stat-value">$1.2T</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">24h Change</div>
                        <div class="stat-value" style="color: var(--success);">+2.4%</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">24h Volume</div>
                        <div class="stat-value">$45.6B</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">BTC Dominance</div>
                        <div class="stat-value">53.2%</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Fear & Greed Index</div>
                        <div class="stat-value" style="color: var(--warning);">68</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Active Traders</div>
                        <div class="stat-value">1.2M</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">AI Confidence Score</div>
                        <div class="stat-value" style="color: var(--success);">87%</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Whale Activity</div>
                        <div class="stat-value" style="color: var(--warning);">High</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Network Health</div>
                        <div class="stat-value">98.2%</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">DeFi TVL</div>
                        <div class="stat-value">$78.4B</div>
                    </div>
                </div>
            </div>

            <div class="section-card">
                <h2 class="section-title">🔥 Breaking Market News</h2>
                <div class="news-grid">
                    {% for item in sample_news %}
                    {% if not item.premium %}
                    <article class="news-card">
                        <h3 class="news-title">{{ item.title }}</h3>
                        <div class="news-meta">
                            <span>🕒 {{ item.timestamp }}</span>
                            <span class="category-tag">{{ item.category }}</span>
                        </div>
                        <div class="news-content">{{ item.content }}</div>
                    </article>
                    {% else %}
                    <article class="news-card" style="opacity: 0.6; position: relative; cursor: pointer;" onclick="showAccessGate()">
                        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; border-radius: 8px;">
                            <div style="text-align: center; color: var(--primary);">
                                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔒</div>
                                <div style="font-weight: 600;">Premium Content</div>
                                <div style="font-size: 0.9rem; margin-top: 0.25rem;">Click to unlock</div>
                            </div>
                        </div>
                        <h3 class="news-title">{{ item.title }}</h3>
                        <div class="news-meta">
                            <span>🕒 {{ item.timestamp }}</span>
                            <span class="category-tag">{{ item.category }}</span>
                        </div>
                        <div class="news-content">{{ item.content }}</div>
                    </article>
                    {% endif %}
                    {% endfor %}
                </div>
                
                <div class="upgrade-notice" style="margin-top: 1.5rem;">
                    📰 Free tier: Limited to 2 recent articles. 
                    <button class="upgrade-btn" onclick="showAccessGate()">Upgrade for full news feed</button>
                </div>
            </div>

            <div class="section-card">
                <h2 class="section-title">🎯 AI Sentiment Analysis</h2>
                <div class="chart-placeholder" onclick="showAccessGate()">
                    <div class="chart-icon">📊</div>
                    <div class="chart-text">
                        <h3>Advanced Sentiment Dashboard</h3>
                        <p>Real-time social media sentiment, news impact analysis, and market momentum indicators</p>
                        <p style="margin-top: 1rem; color: var(--primary);">Click to access full analytics suite</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Valuation Lab Tab -->
        <div class="tab-content active" id="valuation-lab">
            <div class="section-card">
                <h2 class="section-title">📊 Advanced Chart Analysis</h2>
                
                <!-- Basic Controls (Free Tier) -->
                <div class="controls-section">
                    <div class="controls">
                        <div class="control-group">
                            <label for="symbol-select">Trading Pair</label>
                            <select id="symbol-select">
                                <option value="BTCUSDT">BTC/USDT (Free)</option>
                                <option value="ETHUSDT" disabled>ETH/USDT (Pro)</option>
                                <option value="SOLUSDT" disabled>SOL/USDT (Pro)</option>
                                <option value="ADAUSDT" disabled>ADA/USDT (Pro)</option>
                            </select>
                        </div>
                        
                        <div class="control-group">
                            <label for="interval-select">Timeframe</label>
                            <select id="interval-select">
                                <option value="1h">1 Hour (Free)</option>
                                <option value="4h" disabled>4 Hours (Pro)</option>
                                <option value="1d" disabled>1 Day (Pro)</option>
                                <option value="1w" disabled>1 Week (Pro)</option>
                            </select>
                        </div>
                        
                        <div class="control-group">
                            <label>&nbsp;</label>
                            <button id="refresh-btn">🔄 Refresh Data</button>
                        </div>
                    </div>
                    
                    <div class="upgrade-notice">
                        ⚡ Free tier: BTC/USDT 1h data only. 
                        <button class="upgrade-btn" onclick="showAccessGate()">Upgrade for full access</button>
                    </div>
                </div>
                
                <!-- Chart Container -->
                <div class="chart-container">
                    <div id="price-chart" style="width:100%; height:400px; position: relative;"></div>
                    <div class="loading" id="loading-indicator" style="display: none;">
                        <div class="spinner"></div>
                        <div>Loading market data...</div>
                    </div>
                </div>
                
                <!-- Basic Stats -->
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-label">Current Price</div>
                        <div class="stat-value" id="current-price">Loading...</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">24h Change</div>
                        <div class="stat-value" id="price-change">Loading...</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">24h Volume</div>
                        <div class="stat-value" id="volume">Loading...</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Market Cap</div>
                        <div class="stat-value">$1.27T</div>
                    </div>
                </div>
                
                <!-- Premium Features Preview -->
                <div style="margin-top: 2rem; padding: 1.5rem; background: rgba(0, 255, 234, 0.05); border: 1px solid rgba(0, 255, 234, 0.2); border-radius: 8px;">
                    <h4 style="color: var(--primary); margin-bottom: 1rem;">🚀 Premium Features Preview</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; color: var(--text-muted);">
                        <div>✨ All Trading Pairs</div>
                        <div>🤖 AI Predictions</div>
                        <div>🔔 Price Alerts</div>
                        <div>📱 Mobile App</div>
                        <div>📊 Technical Indicators</div>
                        <div>🎯 Support/Resistance</div>
                        <div>📈 Multiple Timeframes</div>
                        <div>⚡ Real-time Updates</div>
                        <div>💰 Portfolio Tracking</div>
                        <div>🌐 Global Markets</div>
                    </div>
                    <button style="margin-top: 1rem; background: var(--primary); color: black; border: none; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; font-weight: 600;" onclick="showAccessGate()">
                        Unlock Premium Features
                    </button>
                </div>
            </div>

            <div class="section-card">
                <h2 class="section-title">🔮 AI Prediction Models</h2>
                <div class="chart-placeholder" onclick="showAccessGate()">
                    <div class="chart-icon">🤖</div>
                    <div class="chart-text">
                        <h3>Machine Learning Price Predictions</h3>
                        <p>Neural network analysis, volatility forecasting, and trend prediction algorithms</p>
                        <p style="margin-top: 1rem; color: var(--primary);">Click to access AI prediction suite</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Trading Tools Tab -->
        <div class="tab-content" id="trading-tools">
            <!-- Basic Tools (Free Tier) -->
            <div class="section-card">
                <h2 class="section-title">🔧 Basic Tools (Free)</h2>
                <div class="tools-grid">
                    <!-- Position Size Calculator -->
                    <div class="tool-card">
                        <h3 class="tool-title">📏 Position Size Calculator</h3>
                        <p class="tool-description">Calculate optimal position sizes based on account balance and risk tolerance for trades.</p>
                        <form class="calculator-form" id="position-calculator">
                            <div class="form-group">
                                <label class="form-label">Account Balance ($)</label>
                                <input type="number" class="form-input" id="account-balance" placeholder="10000">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Risk Percentage (%)</label>
                                <input type="number" class="form-input" id="risk-percent" placeholder="2" step="0.1">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Entry Price ($)</label>
                                <input type="number" class="form-input" id="entry-price" placeholder="50000" step="0.01">
                            </div>
                            <button type="button" class="btn" onclick="calculatePosition()">Calculate Position</button>
                            <div class="result-display" id="position-result">
                                <div class="result-label">Recommended Position Size:</div>
                                <div class="result-value" id="position-value">-</div>
                            </div>
                        </form>
                    </div>

                    <!-- Risk/Reward Calculator -->
                    <div class="tool-card">
                        <h3 class="tool-title">⚡ Risk/Reward Calculator</h3>
                        <p class="tool-description">Analyze risk-to-reward ratios for informed trading decisions.</p>
                        <form class="calculator-form" id="risk-reward-calculator">
                            <div class="form-group">
                                <label class="form-label">Entry Price ($)</label>
                                <input type="number" class="form-input" id="rr-entry" placeholder="50000" step="0.01">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Stop Loss ($)</label>
                                <input type="number" class="form-input" id="rr-stop" placeholder="48000" step="0.01">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Take Profit ($)</label>
                                <input type="number" class="form-input" id="rr-target" placeholder="56000" step="0.01">
                            </div>
                            <button type="button" class="btn" onclick="calculateRiskReward()">Calculate R:R</button>
                            <div class="result-display" id="rr-result">
                                <div class="result-label">Risk/Reward Ratio:</div>
                                <div class="result-value" id="rr-value">-</div>
                            </div>
                        </form>
                    </div>

                    <!-- P&L Calculator -->
                    <div class="tool-card">
                        <h3 class="tool-title">💰 P&L Calculator</h3>
                        <p class="tool-description">Calculate potential profits and losses for your positions.</p>
                        <form class="calculator-form" id="pnl-calculator">
                            <div class="form-group">
                                <label class="form-label">Position Size (Coins)</label>
                                <input type="number" class="form-input" id="pnl-size" placeholder="0.5" step="0.001">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Entry Price ($)</label>
                                <input type="number" class="form-input" id="pnl-entry" placeholder="50000" step="0.01">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Current/Exit Price ($)</label>
                                <input type="number" class="form-input" id="pnl-current" placeholder="52000" step="0.01">
                            </div>
                            <button type="button" class="btn" onclick="calculatePnL()">Calculate P&L</button>
                            <div class="result-display" id="pnl-result">
                                <div class="result-label">Profit/Loss:</div>
                                <div class="result-value" id="pnl-value">-</div>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Automated Crypto Trading Bots (Premium) -->
            <div class="section-card">
                <h2 class="section-title">🤖 Automated Crypto Trading Bots</h2>
                <div class="tools-grid">
                    <div class="tool-card">
                        <h3 class="tool-title">🎯 Smart Crypto DCA Bot</h3>
                        <p class="tool-description">Automated dollar-cost averaging with AI-optimized entry points and dynamic position sizing for cryptocurrencies.</p>
                        <div class="tool-placeholder" onclick="showAccessGate()">
                            <div class="placeholder-icon">🤖</div>
                            <div>Click to configure DCA strategy</div>
                        </div>
                    </div>
                    
                    <div class="tool-card">
                        <h3 class="tool-title">⚡ Crypto Grid Trading Bot</h3>
                        <p class="tool-description">Profit from cryptocurrency volatility with intelligent grid trading strategies and risk management.</p>
                        <div class="tool-placeholder" onclick="showAccessGate()">
                            <div class="placeholder-icon">📊</div>
                            <div>Click to setup grid parameters</div>
                        </div>
                    </div>
                    
                    <div class="tool-card">
                        <h3 class="tool-title">🛡️ Crypto Stop-Loss Manager</h3>
                        <p class="tool-description">Advanced stop-loss and take-profit automation with trailing stops and risk optimization for crypto trades.</p>
                        <div class="tool-placeholder" onclick="showAccessGate()">
                            <div class="placeholder-icon">🛡️</div>
                            <div>Click to manage risk settings</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Crypto Portfolio Management (Premium) -->
            <div class="section-card">
                <h2 class="section-title">👛 Portfolio Management</h2>
                <div class="tools-grid">
                    <div class="tool-card">
                        <h3 class="tool-title">📊 Multi-Chain Crypto Wallet Tracker</h3>
                        <p class="tool-description">Real-time cryptocurrency portfolio tracking across multiple exchanges and DeFi protocols. Receive mobile alerts at set prices.</p>
                        <div class="tool-placeholder" onclick="showAccessGate()">
                            <div class="placeholder-icon">👛</div>
                            <div>Click to connect wallets</div>
                        </div>
                    </div>
                    
                    <div class="tool-card">
                        <h3 class="tool-title">⚖️ Rebalancing Assistant</h3>
                        <p class="tool-description">Automated cryptocurrency portfolio rebalancing based on target allocations and market conditions.</p>
                        <div class="tool-placeholder" onclick="showAccessGate()">
                            <div class="placeholder-icon">⚖️</div>
                            <div>Click to set rebalancing rules</div>
                        </div>
                    </div>
                    
                    <div class="tool-card">
                        <h3 class="tool-title">📈 Trading Performance Analytics</h3>
                        <p class="tool-description">Comprehensive cryptocurrency trading performance analysis with profit/loss tracking and strategy optimization.</p>
                        <div class="tool-placeholder" onclick="showAccessGate()">
                            <div class="placeholder-icon">📈</div>
                            <div>Click to view analytics dashboard</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    <!-- Access Gate Modal -->
    <div class="access-gate" id="accessGate">
        <div class="gate-content">
            <button class="close-gate" onclick="hideAccessGate()">✕</button>
            <div class="gate-icon">🔒</div>
            <h2 class="gate-title">Oops! You don't have access yet.</h2>
            <p class="gate-message">
                Our advanced AI trading suite is currently in exclusive beta. Get early access to cutting-edge tools including automated trading bots, advanced analytics, and professional-grade risk management systems.
            </p>
            <div class="gate-buttons">
                <a href="/contact" class="gate-btn primary">
                    <span>🚀</span> Get Early Access
                </a>
                <button class="gate-btn secondary" onclick="hideAccessGate()">
                    <span>👀</span> Continue Browsing
                </button>
            </div>
        </div>
    </div>

    <script>
        // Enhanced Matrix animation with trading symbols
        const canvas = document.getElementById('matrix');
        const ctx = canvas.getContext('2d');

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const symbols = '₿ΞΔΣΠ∑∏∫0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ$%+-=';
        const fontSize = 14;
        const columns = canvas.width / fontSize;

        const drops = [];
        for (let i = 0; i < columns; i++) {
            drops[i] = Math.floor(Math.random() * canvas.height / fontSize);
        }

        function draw() {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.08)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            for (let i = 0; i < drops.length; i++) {
                const text = symbols[Math.floor(Math.random() * symbols.length)];
                const x = i * fontSize;
                const y = drops[i] * fontSize;
                
                // Gradient effect
                const gradient = ctx.createLinearGradient(0, y - 20, 0, y + 20);
                gradient.addColorStop(0, 'rgba(0, 255, 234, 0.8)');
                gradient.addColorStop(1, 'rgba(0, 255, 234, 0.2)');
                
                ctx.fillStyle = gradient;
                ctx.font = fontSize + 'px monospace';
                ctx.fillText(text, x, y);

                if (y > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }

                drops[i] += Math.random() * 0.8 + 0.3;
            }
        }

        setInterval(draw, 50);

        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });

        // Tab functionality
        document.addEventListener('DOMContentLoaded', function() {
            const tabBtns = document.querySelectorAll('.tab-btn');
            const tabContents = document.querySelectorAll('.tab-content');

            tabBtns.forEach(btn => {
                btn.addEventListener('click', function() {
                    const tabId = this.getAttribute('data-tab');
                    
                    // Remove active class from all tabs and content
                    tabBtns.forEach(b => b.classList.remove('active'));
                    tabContents.forEach(c => c.classList.remove('active'));
                    
                    // Add active class to clicked tab and corresponding content
                    this.classList.add('active');
                    document.getElementById(tabId).classList.add('active');
                });
            });
        });

        // Basic chart functionality for Valuation Lab
        document.addEventListener('DOMContentLoaded', function() {
            const priceChart = document.getElementById('price-chart');
            const refreshBtn = document.getElementById('refresh-btn');
            const loadingIndicator = document.getElementById('loading-indicator');
            const currentPriceEl = document.getElementById('current-price');
            const priceChangeEl = document.getElementById('price-change');
            const volumeEl = document.getElementById('volume');
            
            // Only initialize if we're on valuation lab tab
            if (priceChart) {
                fetchBasicChartData();
                
                refreshBtn.addEventListener('click', fetchBasicChartData);
                
                // Auto-refresh every 5 minutes
                setInterval(fetchBasicChartData, 300000);
            }
            
            async function fetchBasicChartData() {
                if (!priceChart) return;
                
                loadingIndicator.style.display = 'block';
                
                try {
                    const response = await fetch('/trading-suite/api/basic_chart_data');
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        renderBasicChart(data.data);
                        updateBasicStats(data.data);
                    } else {
                        console.error('Failed to fetch chart data:', data.message);
                    }
                } catch (error) {
                    console.error('Error fetching chart data:', error);
                } finally {
                    loadingIndicator.style.display = 'none';
                }
            }
            
            function renderBasicChart(chartData) {
                console.log('Chart container width:', priceChart.offsetWidth);
                console.log('Chart container parent width:', priceChart.parentElement.offsetWidth);
                
                const times = chartData.map(item => new Date(item.timestamp));
                const closes = chartData.map(item => item.close);
                
                const trace = {
                    type: 'scatter',
                    x: times,
                    y: closes,
                    line: {color: '#00ffea', width: 2},
                    name: 'BTC/USDT',
                    hovertemplate: 'Price: $%{y:,.2f}<br>Time: %{x}<extra></extra>'
                };
                
                const layout = {
                    title: {
                        text: 'BTC/USDT - 1 Hour (Free Tier)',
                        font: {color: '#00ffea', size: 16}
                    },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0.2)',
                    font: {color: '#00ffea', family: 'Inter, Arial, sans-serif'},
                    xaxis: {
                        title: 'Time',
                        type: 'date',
                        gridcolor: 'rgba(0, 255, 234, 0.15)'
                    },
                    yaxis: {
                        title: 'Price (USDT)',
                        gridcolor: 'rgba(0, 255, 234, 0.15)'
                    },
                    margin: {l: 60, r: 30, t: 60, b: 40},
                    hovermode: 'x'
                };
                
                Plotly.newPlot(priceChart, [trace], layout, {
                    responsive: true,
                    displayModeBar: false
                });

                setTimeout(() => {
                    Plotly.Plots.resize(priceChart);
                }, 100);
            }

            function updateBasicStats(chartData) {
                if (chartData.length === 0) return;
                
                const latest = chartData[chartData.length - 1];
                const oldest = chartData[0];
                
                // Calculate 24h change
                const priceChange = ((latest.close - oldest.close) / oldest.close) * 100;
                
                // Update DOM
                currentPriceEl.textContent = `$${latest.close.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                priceChangeEl.textContent = `${priceChange.toFixed(2)}%`;
                priceChangeEl.style.color = priceChange >= 0 ? '#00ff88' : '#ff4444';
                
                // Format volume
                const volume = latest.volume;
                let formattedVolume;
                if (volume >= 1e9) {
                    formattedVolume = `${(volume / 1e9).toFixed(2)}B`;
                } else if (volume >= 1e6) {
                    formattedVolume = `${(volume / 1e6).toFixed(2)}M`;
                } else {
                    formattedVolume = volume.toFixed(0);
                }
                volumeEl.textContent = formattedVolume;
            }
        });
        
        // Access gate functions
        function showAccessGate() {
            document.getElementById('accessGate').classList.add('show');
            document.body.style.overflow = 'hidden';
        }

        function hideAccessGate() {
            document.getElementById('accessGate').classList.remove('show');
            document.body.style.overflow = 'auto';
        }

        // Close modal when clicking outside
        document.getElementById('accessGate').addEventListener('click', function(e) {
            if (e.target === this) {
                hideAccessGate();
            }
        });

        // Escape key to close modal
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                hideAccessGate();
            }
        });

        // Mobile menu functionality
        const menuButton = document.getElementById('menu-button');
        if (menuButton) {
            menuButton.addEventListener('click', function() {
                // Add mobile menu functionality here if needed
                console.log('Mobile menu clicked');
            });
        }

        // Add subtle animations to cards on load
        document.addEventListener('DOMContentLoaded', function() {
            const cards = document.querySelectorAll('.section-card, .tool-card, .news-card, .stat-box');
            cards.forEach((card, index) => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    card.style.transition = 'all 0.6s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, index * 50);
            });
        });

        // Simulate real-time data updates
        function updateMarketData() {
            const marketCap = document.querySelector('.stat-value');
            if (marketCap && marketCap.textContent.includes('$1.2T')) {
                // Simulate slight variations in market data
                const variations = ['$1.2T', '$1.21T', '$1.19T', '$1.22T'];
                const randomIndex = Math.floor(Math.random() * variations.length);
                marketCap.textContent = variations[randomIndex];
            }
        }

        // Update market data every 30 seconds
        setInterval(updateMarketData, 30000);

        // Add interactive hover effects for tool placeholders
        document.querySelectorAll('.tool-placeholder').forEach(placeholder => {
            placeholder.addEventListener('mouseenter', function() {
                this.style.borderColor = 'var(--primary)';
                this.style.backgroundColor = 'rgba(0, 255, 234, 0.05)';
            });
            
            placeholder.addEventListener('mouseleave', function() {
                this.style.borderColor = 'var(--border-color)';
                this.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
            });
        });

        // Add click tracking for analytics
        document.querySelectorAll('[onclick*="showAccessGate"]').forEach(element => {
            element.addEventListener('click', function() {
                // Track which tool was clicked for analytics
                const toolName = this.closest('.tool-card')?.querySelector('.tool-title')?.textContent || 
                                this.closest('.section-card')?.querySelector('.section-title')?.textContent || 
                                'Unknown Tool';
                console.log('Access requested for:', toolName);
                
                // You could send this data to your analytics service here
                // gtag('event', 'tool_access_requested', { tool_name: toolName });
            });
        });

        // Trading Calculator Functions
        function calculatePosition() {
            const balance = parseFloat(document.getElementById('account-balance').value);
            const riskPercent = parseFloat(document.getElementById('risk-percent').value);
            const entryPrice = parseFloat(document.getElementById('entry-price').value);
            const stopLoss = parseFloat(document.getElementById('stop-loss').value);

            if (!balance || !riskPercent || !entryPrice || !stopLoss) {
                alert('Please fill in all fields');
                return;
            }

            const riskAmount = balance * (riskPercent / 100);
            const priceRisk = Math.abs(entryPrice - stopLoss);
            const positionSize = riskAmount / priceRisk;

            document.getElementById('position-result').style.display = 'block';
            document.getElementById('position-value').textContent = `${positionSize.toFixed(6)} units ($${(positionSize * entryPrice).toLocaleString()})`;
        }

        function calculateRiskReward() {
            const entry = parseFloat(document.getElementById('rr-entry').value);
            const stopLoss = parseFloat(document.getElementById('rr-stop').value);
            const target = parseFloat(document.getElementById('rr-target').value);

            if (!entry || !stopLoss || !target) {
                alert('Please fill in all fields');
                return;
            }

            const risk = Math.abs(entry - stopLoss);
            const reward = Math.abs(target - entry);
            const ratio = reward / risk;

            document.getElementById('rr-result').style.display = 'block';
            document.getElementById('rr-value').textContent = `1:${ratio.toFixed(2)} ${ratio >= 2 ? '✅' : ratio >= 1.5 ? '⚠️' : '❌'}`;
        }

        function calculatePnL() {
            const size = parseFloat(document.getElementById('pnl-size').value);
            const entry = parseFloat(document.getElementById('pnl-entry').value);
            const current = parseFloat(document.getElementById('pnl-current').value);

            if (!size || !entry || !current) {
                alert('Please fill in all fields');
                return;
            }

            const pnl = (current - entry) * size;
            const pnlPercent = ((current - entry) / entry) * 100;

            document.getElementById('pnl-result').style.display = 'block';
            const resultEl = document.getElementById('pnl-value');
            resultEl.textContent = `$${pnl.toFixed(2)} (${pnlPercent.toFixed(2)}%)`;
            resultEl.style.color = pnl >= 0 ? 'var(--success)' : 'var(--danger)';
        }
    </script>
    
    <!-- Footer -->
    <footer class="custom-footer">
        <div class="footer-content">
            <!-- Main Footer Content -->
            <div class="footer-main">
                <!-- Social Media Section (Left) -->
                <div class="social-section">
                    <h3 class="social-title">Follow Here</h3>
                    <div class="social-links">
                        <!-- YouTube -->
                        <a href="https://www.youtube.com/@web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:50px;height:50px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-youtube" style="display:block;fill:currentColor" data-donate="true" data-tag="you" data-name="YouTube" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>YouTube social icon</title>
                                <path d="M422.6 193.6c-5.3-45.3-23.3-51.6-59-54 -50.8-3.5-164.3-3.5-215.1 0 -35.7 2.4-53.7 8.7-59 54 -4 33.6-4 91.1 0 124.8 5.3 45.3 23.3 51.6 59 54 50.9 3.5 164.3 3.5 215.1 0 35.7-2.4 53.7-8.7 59-54C426.6 284.8 426.6 227.3 422.6 193.6zM222.2 303.4v-94.6l90.7 47.3L222.2 303.4z"></path>
                            </svg>
                        </a>
                        
                        <!-- LinkedIn -->
                        <a href="https://www.linkedin.com/in/web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:45px;height:45px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-linkedin" style="display:block;fill:currentColor" data-donate="true" data-tag="lin" data-name="LinkedIn" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>LinkedIn social icon</title>
                                <path d="M186.4 142.4c0 19-15.3 34.5-34.2 34.5 -18.9 0-34.2-15.4-34.2-34.5 0-19 15.3-34.5 34.2-34.5C171.1 107.9 186.4 123.4 186.4 142.4zM181.4 201.3h-57.8V388.1h57.8V201.3zM273.8 201.3h-55.4V388.1h55.4c0 0 0-69.3 0-98 0-26.3 12.1-41.9 35.2-41.9 21.3 0 31.5 15 31.5 41.9 0 26.9 0 98 0 98h57.5c0 0 0-68.2 0-118.3 0-50-28.3-74.2-68-74.2 -39.6 0-56.3 30.9-56.3 30.9v-25.2H273.8z"></path>
                            </svg>
                        </a>
                        
                        <!-- TikTok -->
                        <a href="https://www.tiktok.com/@web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:42px;height:42px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-tiktok" style="display:block;fill:currentColor" data-donate="true" data-tag="tic" data-name="TikTok" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>TikTok social icon</title>
                                <path d="M 386.160156 141.550781 C 383.457031 140.15625 380.832031 138.625 378.285156 136.964844 C 370.878906 132.070312 364.085938 126.300781 358.058594 119.785156 C 342.976562 102.523438 337.339844 85.015625 335.265625 72.757812 L 335.351562 72.757812 C 333.617188 62.582031 334.332031 56 334.441406 56 L 265.742188 56 L 265.742188 321.648438 C 265.742188 325.214844 265.742188 328.742188 265.589844 332.226562 C 265.589844 332.660156 265.550781 333.058594 265.523438 333.523438 C 265.523438 333.714844 265.523438 333.917969 265.484375 334.117188 C 265.484375 334.167969 265.484375 334.214844 265.484375 334.265625 C 264.011719 353.621094 253.011719 370.976562 236.132812 380.566406 C 227.472656 385.496094 217.675781 388.078125 207.707031 388.066406 C 175.699219 388.066406 149.757812 361.964844 149.757812 329.734375 C 149.757812 297.5 175.699219 271.398438 207.707031 271.398438C 213.765625 271.394531 219.789062 272.347656 225.550781 274.226562 L 225.632812 204.273438 C 190.277344 199.707031 154.621094 210.136719 127.300781 233.042969 C 115.457031 243.328125 105.503906 255.605469 97.882812 269.316406 C 94.984375 274.316406 84.042969 294.410156 82.714844 327.015625 C 81.882812 345.523438 87.441406 364.699219 90.089844 372.625 L 90.089844 372.792969 C 91.757812 377.457031 98.214844 393.382812 108.742188 406.808594 C 117.230469 417.578125 127.253906 427.035156 138.5 434.882812 L 138.5 434.714844 L 138.667969 434.882812 C 171.925781 457.484375 208.800781 456 208.800781 456 C 215.183594 455.742188 236.566406 456 260.851562 444.492188 C 287.785156 431.734375 303.117188 412.726562 303.117188 412.726562 C 312.914062 401.367188 320.703125 388.425781 326.148438 374.449219 C 332.367188 358.109375 334.441406 338.507812 334.441406 330.675781 L 334.441406 189.742188 C 335.273438 190.242188 346.375 197.582031 346.375 197.582031 C 346.375 197.582031 362.367188 207.832031 387.316406 214.507812 C 405.214844 219.257812 429.332031 220.257812 429.332031 220.257812 L 429.332031 152.058594 C 420.882812 152.976562 403.726562 150.308594 386.160156 141.550781 Z M 386.160156 141.550781"></path>
                            </svg>
                        </a>
                        
                        <!-- X (Twitter) -->
                        <a href="https://x.com/web3fuel/" target="_blank" rel="noopener noreferrer" style="text-decoration:none;border:0;width:40px;height:40px;padding:2px;margin:5px;color:#11CBE9;border-radius:50%;background-color:#000000;">
                            <svg class="niftybutton-twitterx" style="display:block;fill:currentColor" data-donate="true" data-tag="twix" data-name="TwitterX" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">
                                <title>Twitter X social icon</title>
                                <path d="M 304.757 216.824 L 495.394 0 L 450.238 0 L 284.636 188.227 L 152.475 0 L 0 0 L 199.902 284.656 L 0 512 L 45.16 512 L 219.923 313.186 L 359.525 512 L 512 512 M 61.456 33.322 L 130.835 33.322 L 450.203 480.317 L 380.811 480.317 "></path>
                            </svg>
                        </a>
                    </div>
                </div>

                <!-- Newsletter Section (Right) -->
                <div class="newsletter-section">
                    <h3 class="newsletter-title">Join to Stay Updated with Market Insights</h3>
                    <form class="newsletter-form" onsubmit="event.preventDefault(); alert('Newsletter signup coming soon!');">
                        <input 
                            type="email" 
                            class="newsletter-input" 
                            placeholder="Enter your email address" 
                            required
                        >
                        <button type="submit" class="newsletter-button">
                            Subscribe
                        </button>
                    </form>
                </div>
            </div>

            <!-- Footer Bottom -->
            <div class="footer-divider"></div>
            <div class="footer-bottom">
                <div class="footer-left">
                    <p class="copyright">© 2025 Web3Fuel. All rights reserved.</p>
                </div>
                <div class="footer-center">
                    <a href="/contact" class="footer-links">Contact</a>
                </div>
                <div class="footer-right">
                    <a href="/terms-of-service" class="footer-links">Terms of Service</a>
                </div>
            </div>
        </div>
    </footer>
</body>
</html>
'''

# Blueprint route for trading suite
@trading_suite_bp.route('/')
def trading_suite():
    return render_template_string(template, sample_news=sample_news)