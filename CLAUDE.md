# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web3Fuel.io is a Flask-based web application offering dual AI-powered services: cryptocurrency trading tools and marketing solutions for financial professionals. The application demonstrates how AI algorithms originally designed for financial market prediction can be adapted for marketing intelligence.

## Common Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py

# Run production server
gunicorn --bind 0.0.0.0:8000 wsgi:application
```

## Architecture

### Blueprint Structure
The application uses Flask Blueprints for modular organization:
- **routes/home.py**: Main homepage with embedded HTML templates
- **routes/blog.py**: WordPress REST API integration with Redis caching
- **routes/contact.py**: Contact forms with EmailJS integration
- **routes/trading_suite.py**: Trading tools with Binance API integration
- **routes/research.py**: Cross-chain infrastructure research and analysis

### Template Strategy
Templates are embedded as Python strings within route files using `render_template_string()`. This approach keeps each route module self-contained with its HTML, CSS, and JavaScript.

### External Integrations
- **WordPress REST API**: Blog content with advanced caching (Redis + in-memory fallback)
- **Binance API**: Real-time cryptocurrency data for trading tools
- **EmailJS**: Client-side form submissions for contact forms

### Caching Architecture
Multi-tier caching system:
1. **Redis**: Primary cache for WordPress content and API responses
2. **In-memory fallback**: Python dictionaries when Redis unavailable
3. **Rate limiting**: Protection for external API calls

## Key Technical Details

### Entry Points
- **run.py**: Development server (Flask development server)
- **wsgi.py**: Production WSGI application entry point

### Data Processing
The application handles:
- Real-time cryptocurrency market data visualization using Plotly.js
- WordPress blog content aggregation and display
- Contact form processing with appointment scheduling
- Trading calculators (position sizing, risk/reward, P&L)

### Frontend Components
Each route contains embedded CSS/JS creating:
- Interactive 3D visualizations and matrix animations
- Responsive design with mobile-first approach
- Dynamic charts and trading calculators
- Modal popups and form validations

## Development Notes

### Route File Structure
Each route file in `routes/` contains:
1. Flask blueprint definition
2. Route handlers
3. Embedded HTML template as Python string
4. Inline CSS and JavaScript

### API Integration Patterns
- WordPress API calls include comprehensive error handling and caching
- Binance API integration for real-time market data
- EmailJS integration for contact form submissions

### Error Handling
The application implements fallback strategies:
- Cache misses fall back to direct API calls
- Redis unavailability falls back to in-memory caching
- API failures display user-friendly error messages