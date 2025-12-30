# Web3Fuel.io

[![GitHub](https://img.shields.io/github/license/zzzandy-eth/web3fuel)](https://github.com/zzzandy-eth/web3fuel)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)](https://flask.palletsprojects.com/)
[![Cross-Chain](https://img.shields.io/badge/Focus-Cross--Chain%20Infrastructure-orange)](https://web3fuel.io)

> **Cross-chain infrastructure research, analysis, and practical tools for the multi-chain future.**

Web3Fuel is a comprehensive platform dedicated to advancing cross-chain interoperability through in-depth research, security analysis, and practical tools. We focus on bridge security, protocol comparisons, and building the infrastructure needed for a truly connected multi-chain ecosystem.

**Live Site**: [web3fuel.io](https://web3fuel.io)
**Repository**: [github.com/zzzandy-eth/web3fuel](https://github.com/zzzandy-eth/web3fuel)

---

## Project Overview

Web3Fuel addresses the critical challenges of cross-chain interoperability by providing:

- **Security Analysis**: Comprehensive research on bridge protocols and their security models
- **Practical Tools**: Real-world utilities for cross-chain operations and portfolio management
- **Protocol Comparisons**: Data-driven analysis of different cross-chain solutions
- **Educational Resources**: Research papers and insights for developers and users

The platform serves as both a resource hub for cross-chain research and a toolkit for practical multi-chain operations.

---

## Features

### Research & Analysis
- **Bridge Security Reports**: In-depth analysis of LayerZero, Axelar, Wormhole, and other protocols
- **Comparative Studies**: Risk assessments and security model comparisons
- **Research Papers**: Downloadable PDF reports with technical findings
- **Protocol Documentation**: Comprehensive coverage of cross-chain infrastructure

### Cross-Chain Tools
- **Chainlink Price Feeds**: Live cryptocurrency prices from Chainlink decentralized oracles
- **Bridge Fee Comparison**: Real-time comparison of bridging costs across protocols
- **Portfolio Dashboard**: Multi-chain portfolio tracking and analytics
- **Gas Optimization**: Tools for efficient cross-chain transactions
- **Risk Assessment**: Security scoring and risk analysis for bridge operations

### User Experience
- **Responsive Design**: Optimized for desktop, tablet, and mobile devices
- **Interactive Dashboards**: Dynamic charts and real-time data visualization
- **Professional UI**: Clean, modern interface with accessibility features
- **Fast Performance**: Optimized loading and caching for better user experience

---

## Technologies Used

### Backend
- **[Python 3.8+](https://python.org)** - Core programming language
- **[Flask 2.0+](https://flask.palletsprojects.com/)** - Web framework
- **[Gunicorn](https://gunicorn.org/)** - WSGI HTTP Server for production

### Frontend
- **HTML5 & CSS3** - Modern web standards
- **Vanilla JavaScript** - Client-side interactivity
- **[Chart.js](https://chartjs.org)** - Data visualization
- **[Plotly.js](https://plotly.com/javascript/)** - Advanced charting

### External Services
- **[WordPress REST API](https://developer.wordpress.org/rest-api/)** - Blog content management
- **[EmailJS](https://emailjs.com)** - Contact form handling
- **[Redis](https://redis.io)** - Caching layer (optional)

### Architecture
- **Blueprint Structure** - Modular Flask application design
- **Template String Rendering** - Self-contained route modules
- **Multi-tier Caching** - Redis + in-memory fallback system
- **API Integration** - External service connectivity

---

## Local Setup Instructions

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/zzzandy-eth/web3fuel.git
   cd web3fuel
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration** (Optional)
   ```bash
   # Create .env file for environment variables
   cp .env.example .env

   # Edit .env with your configuration
   # SECRET_KEY=your-secret-key-here
   # FLASK_ENV=development
   ```

5. **Run development server**
   ```bash
   python run.py
   ```

6. **Access the application**
   - Open your browser to `http://localhost:5000`
   - The application will be running in development mode

### Production Deployment

For production deployment using Gunicorn:

```bash
gunicorn --bind 0.0.0.0:8000 wsgi:application
```

---

## Project Structure

```
web3fuel/
├── backend/
│   ├── __init__.py                 # Flask application factory
│   ├── config.py                   # Configuration settings
│   └── routes/
│       ├── __init__.py             # Blueprint registration
│       ├── home.py                 # Homepage route
│       ├── tools.py                # Cross-chain tools index
│       ├── crypto_prices.py        # Chainlink Price Feeds tool
│       ├── reply_assistant.py      # AI Reply Assistant tool
│       ├── research.py             # Research articles
│       ├── blog.py                 # Blog integration
│       └── contact.py              # Contact forms
├── frontend/
│   ├── static/
│   │   └── css/
│   │       └── globals.css         # Global styles
│   └── templates/
│       ├── base.html               # Base template
│       ├── components/             # Reusable components
│       │   ├── header.html
│       │   └── footer.html
│       ├── tools/                  # Tool-specific templates
│       │   ├── bridge-fee-comparison.html
│       │   └── portfolio-dashboard.html
│       └── research_article/       # Research templates
│           └── security.html
├── run.py                          # Development server entry point
├── wsgi.py                         # Production WSGI entry point
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore rules
└── README.md                       # Project documentation
```

### Key Components

- **`backend/routes/`** - Modular route handlers using Flask Blueprints
- **`frontend/templates/`** - Jinja2 templates with embedded CSS/JS
- **`backend/config.py`** - Environment-based configuration management
- **Template Strategy** - Self-contained routes with embedded templates

---

## Chainlink Price Feeds Tool

Live cryptocurrency prices powered by Chainlink's decentralized oracle network.

**Live URL**: [web3fuel.io/tools/crypto-prices](https://web3fuel.io/tools/crypto-prices)

### How It Works

Chainlink Price Feeds are decentralized oracle networks that aggregate price data from multiple premium data sources. The prices are stored on-chain in smart contracts on Ethereum mainnet, ensuring tamper-proof and verifiable data.

Our tool fetches prices directly from these smart contracts using the Web3.py library:

```
User Request → Flask API → Web3.py → Ethereum RPC → Chainlink Contract → Price Data
```

### Supported Price Feeds

| Asset | Contract Address | Chainlink Page |
|-------|------------------|----------------|
| BTC/USD | `0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c` | [View](https://data.chain.link/feeds/ethereum/mainnet/btc-usd) |
| ETH/USD | `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419` | [View](https://data.chain.link/feeds/ethereum/mainnet/eth-usd) |
| LINK/USD | `0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c` | [View](https://data.chain.link/feeds/ethereum/mainnet/link-usd) |
| AVAX/USD | `0xFF3EEb22B5E3dE6e705b44749C2559d704923FD7` | [View](https://data.chain.link/feeds/ethereum/mainnet/avax-usd) |
| MATIC/USD | `0x7bAC85A8a13A4BcD8abb3eB7d6b4d632c5a57676` | [View](https://data.chain.link/feeds/ethereum/mainnet/matic-usd) |

### Features

- **Real-time Prices**: Fetched directly from Chainlink smart contracts
- **Auto-refresh**: Updates every 30 seconds automatically
- **Price Change Indicators**: Visual arrows and colors showing price movement
- **30-second Caching**: Prevents excessive RPC calls while maintaining freshness
- **On-chain Timestamps**: Shows when each price was last updated on-chain
- **Contract Links**: Direct links to Etherscan and Chainlink data pages
- **Mobile Responsive**: Optimized for all device sizes

### Configuration

Add your Ethereum RPC endpoint to `.env`:

```bash
# Using Alchemy (recommended)
ETHEREUM_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# Or Infura
ETHEREUM_RPC_URL=https://mainnet.infura.io/v3/YOUR_PROJECT_ID
```

If no RPC is configured, the tool falls back to public RPC endpoints (LlamaRPC, PublicNode, etc.).

### Testing Locally

```bash
# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run Flask development server
python run.py

# Open in browser
# http://localhost:5000/tools/crypto-prices
```

### API Endpoint

```
GET /tools/crypto-prices/api/prices
```

Returns JSON with all price data:
```json
{
  "success": true,
  "cached": false,
  "fetchedAt": "2025-12-30 16:30:00 UTC",
  "prices": [
    {
      "pair": "BTC/USD",
      "price": 88532.0781,
      "decimals": 8,
      "updatedAt": 1735574447,
      "updatedAtFormatted": "2025-12-30 15:50:47 UTC",
      "address": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
      "priceChange": 0,
      "priceChangePercent": 0,
      "success": true
    }
  ]
}
```

### Technical Details

- **Backend**: Flask blueprint at `backend/routes/crypto_prices.py`
- **Web3 Library**: web3.py >= 6.0.0
- **ABI**: Chainlink AggregatorV3Interface (latestRoundData, decimals)
- **Decimals**: All USD pairs use 8 decimals (divide by 10^8)
- **Caching**: Thread-safe in-memory cache with 30-second TTL

---

## Future Roadmap

### Phase 1: Enhanced Analytics (Q2 2025)
- [ ] Real-time bridge monitoring dashboard
- [ ] Advanced fee prediction algorithms
- [ ] Multi-chain gas tracker integration
- [ ] Bridge health scoring system

### Phase 2: Developer Tools (Q3 2025)
- [ ] Cross-chain testing framework
- [ ] Bridge integration SDK
- [ ] API for third-party developers
- [ ] Webhook notifications for bridge events

### Phase 3: Community Features (Q4 2025)
- [ ] User accounts and personalization
- [ ] Community-driven bridge reviews
- [ ] Bridge performance leaderboards
- [ ] Educational certification programs

### Phase 4: Advanced Infrastructure (2026)
- [ ] Custom bridge protocol development
- [ ] Decentralized bridge validation network
- [ ] Cross-chain governance tools
- [ ] Institutional-grade analytics platform

---

## Contributing

We welcome contributions from the cross-chain community! Here's how you can help:

### Ways to Contribute
- **Bug Reports**: Submit issues with detailed reproduction steps
- **Feature Requests**: Propose new tools or research areas
- **Research**: Contribute bridge analysis or security findings
- **Code**: Submit pull requests with improvements
- **Documentation**: Help improve guides and explanations

### Development Process
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards
- Follow PEP 8 for Python code
- Use meaningful commit messages
- Include tests for new features
- Update documentation as needed

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contact Information

### Project Maintainer
- **GitHub**: [@zzzandy-eth](https://github.com/zzzandy-eth)
- **Project**: [Web3Fuel.io](https://web3fuel.io)

### Connect With Us
- **Website**: [web3fuel.io](https://web3fuel.io)
- **Email**: [Contact Form](https://web3fuel.io/contact)
- **Twitter**: [@web3fuel](https://x.com/web3fuel)
- **LinkedIn**: [Web3Fuel](https://linkedin.com/in/web3fuel)
- **Discord**: [Community Server](https://discord.com/users/zzzandy)

### Research Collaboration
Interested in collaborating on cross-chain research? We welcome partnerships with:
- Academic institutions
- Security research firms
- Protocol development teams
- Cross-chain infrastructure projects

---

## Acknowledgments

- Thanks to the open-source community for the excellent tools and frameworks
- Appreciation to the cross-chain protocols that make this research possible
- Gratitude to the security researchers advancing bridge safety
- Recognition of the developers building the multi-chain future

---

<div align="center">

**Building the infrastructure for a connected multi-chain world**

[Star this project](https://github.com/zzzandy-eth/web3fuel) if you find it valuable!

</div>