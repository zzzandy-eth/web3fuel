from flask import Blueprint, render_template_string, redirect, url_for, request, jsonify
from datetime import datetime

# Create the blueprint for tools
tools_bp = Blueprint('tools', __name__, url_prefix='/tools')

# Cross-chain tools data - Coming soon tools
cross_chain_tools = [
    {
        "title": "Bridge Fee Comparison Tracker",
        "description": "Compare bridging costs across all major cross-chain protocols in real-time. Our tool aggregates fee data from Hop, Stargate, Across, and Wormhole to help you find the most cost-effective route for your transactions. Save up to 60% on bridge fees by choosing the optimal protocol and timing for your cross-chain transfers.",
        "why_valuable": "Save 30-60% on bridge fees with optimal route selection",
        "technical_scope": "Real-time fee tracking across 4 major bridge protocols",
        "hiring_impact": "Shows you understand bridge economics and can build useful products",
        "tags": ["Fee Savings", "Cross-Chain", "DeFi Tools"],
        "date": datetime(2025, 9, 23),
        "slug": "bridge-fee-comparison",
        "status": "live"
    },
    {
        "title": "Cross-Chain Portfolio Dashboard",
        "description": "Unified portfolio tracking across Ethereum, Arbitrum, Polygon, Optimism, Avalanche, and BSC in a single interface. Monitor token balances, track performance, and visualize allocation across all your wallets and chains. Features real-time price feeds, historical data, and interactive charts to give you complete visibility into your multi-chain holdings.",
        "why_valuable": "Manage all crypto assets across 6+ chains in one place",
        "technical_scope": "Live price tracking with comprehensive chain coverage",
        "hiring_impact": "Demonstrates full-stack capabilities and multi-chain technical knowledge",
        "tags": ["Portfolio Tracking", "Multi-Chain", "Asset Management"],
        "date": datetime(2025, 9, 23),
        "slug": "portfolio-dashboard",
        "status": "beta"
    },
    {
        "title": "Bridge Transaction Status Monitor",
        "description": "Real-time monitoring and status tracking for cross-chain bridge transactions across all major protocols. Get instant notifications when transactions complete, fail, or get stuck in processing. Includes detailed transaction history, estimated completion times, and automatic retry suggestions for failed transfers.",
        "why_valuable": "Never lose track of bridge transactions with instant alerts",
        "technical_scope": "Smart notifications across all major bridge protocols",
        "hiring_impact": "Shows deep understanding of bridge mechanics",
        "tags": ["Transaction Alerts", "Bridge Safety", "Peace of Mind"],
        "date": datetime(2026, 1, 10),
        "slug": "transaction-monitor",
        "status": "coming_soon"
    },
    {
        "title": "Gas Price Optimizer",
        "description": "Smart gas price analysis and timing recommendations to minimize transaction costs across all EVM chains. Uses machine learning algorithms to predict optimal transaction windows based on historical patterns and network congestion. Provides personalized alerts when gas prices drop below your target thresholds for maximum savings.",
        "why_valuable": "Cut transaction costs with AI-powered gas price predictions",
        "technical_scope": "ML-based gas price forecasting and smart alerts",
        "hiring_impact": "Combines technical skills with practical user value",
        "tags": ["Gas Savings", "AI Predictions", "Cost Efficiency"],
        "date": datetime(2026, 1, 20),
        "slug": "gas-optimizer",
        "status": "coming_soon"
    },
    {
        "title": "Bridge Security Scorecard",
        "description": "Comprehensive security analysis and risk ratings for all major cross-chain bridge protocols based on extensive research and real-time monitoring. Evaluates factors including validator models, trust assumptions, attack vectors, and historical incidents to provide clear safety scores. Helps users make informed decisions about which bridges to trust with their assets.",
        "why_valuable": "Protect your assets with expert security analysis",
        "technical_scope": "Research-backed safety ratings for all bridges",
        "hiring_impact": "Connects your research expertise with practical tools",
        "tags": ["Asset Protection", "Security Research", "Risk Analysis"],
        "date": datetime(2026, 2, 1),
        "slug": "security-scorecard",
        "status": "coming_soon"
    }
]

# Tools metrics
tools_metrics = {
    "total_tools": len(cross_chain_tools),
    "protocols_integrated": 12,
    "development_hours": 1800,
    "apis_connected": 25
}

# Redirect old trading-suite URL to new tools URL for SEO
@tools_bp.route('/trading-suite')
@tools_bp.route('/trading-suite/')
def redirect_legacy_trading_suite():
    return redirect(url_for('tools.tools'), code=301)

@tools_bp.route('/<slug>')
def tool(slug):
    """Individual tool page"""
    from flask import render_template, abort

    # Find the tool by slug
    tool_data = None
    for tool in cross_chain_tools:
        if tool.get('slug') == slug:
            tool_data = tool
            break

    if not tool_data:
        abort(404)

    # Available tools with mock pages
    if slug == 'bridge-fee-comparison':
        return render_template('tools/bridge-fee-comparison.html', tool=tool_data)
    elif slug == 'portfolio-dashboard':
        return render_template('tools/portfolio-dashboard.html', tool=tool_data)
    else:
        # For other tools, show coming soon page or redirect
        abort(404)

@tools_bp.route('/')
def tools():
    """Tools page with cross-chain infrastructure tools"""
    template_str = '''
{% extends "base.html" %}

{% block title %}Cross-Chain Tools - Web3Fuel.io{% endblock %}

{% block head %}
<!-- Add EmailJS script -->
<script src="https://cdn.jsdelivr.net/npm/@emailjs/browser@3/dist/email.min.js"></script>
{% endblock %}

{% block content %}
<!-- Hero Section -->
<section class="hero">
    <div class="container">
        <div class="hero-content-centered">
            <h1>Cross-Chain:<br><span class="typewriter">Tools</span></h1>
            <h3>Compare fees, track portfolios, and monitor transactions across all major bridge protocols.</h3>
        </div>
    </div>
</section>

<!-- Tools Section -->
<section class="tools-section">
    <div class="container">
        <div class="tools-content">
            {% for tool in cross_chain_tools %}
            <article class="tool-card {% if tool.status == 'coming_soon' %}coming-soon{% endif %}">
                <div class="tool-meta">
                    <div class="tool-tags">
                        {% for tag in tool.tags %}
                        <span class="tag">{{ tag }}</span>
                        {% endfor %}
                    </div>
                </div>

                <h2 class="tool-title">{{ tool.title }}</h2>

                <div class="tool-status">
                    {% if tool.status == 'live' %}
                    <span class="status-badge live">Status: Live</span>
                    {% elif tool.status == 'beta' %}
                    <span class="status-badge beta">Status: Beta</span>
                    {% elif tool.status == 'coming_soon' %}
                    <span class="status-badge coming-soon">Status: Coming Soon</span>
                    {% endif %}
                </div>

                <div class="tool-description">
                    <p>{{ tool.description }}</p>
                </div>

                <div class="tool-details">
                    <div class="details-horizontal">
                        <span class="detail-text">💡 {{ tool.why_valuable }}</span>
                        <span class="detail-text">⚙️ {{ tool.technical_scope }}</span>
                    </div>
                </div>

                <div class="tool-actions">
                    {% if tool.status == 'live' %}
                    <a href="{{ url_for('tools.tool', slug=tool.slug) }}" class="action-btn primary" target="_blank">
                        Launch Tool
                    </a>
                    <a href="https://github.com/zzzandy-eth/web3fuel/" class="action-btn secondary" target="_blank">
                        View Source
                    </a>
                    {% elif tool.status == 'beta' %}
                    <a href="{{ url_for('tools.tool', slug=tool.slug) }}" class="action-btn primary beta" target="_blank">
                        Try Beta
                    </a>
                    <a href="/contact" class="action-btn secondary">
                        Report Issues
                    </a>
                    {% elif tool.status == 'coming_soon' %}
                    <button class="action-btn primary disabled" disabled>
                        Get Notified
                    </button>
                    <button class="action-btn secondary disabled" disabled>
                        View Roadmap
                    </button>
                    {% endif %}
                </div>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

<!-- CTA Section -->
<section class="cta">
    <div class="container">
        <div class="cta-container-horizontal">
            <div class="cta-content-horizontal">
                <div class="cta-text-horizontal">
                    <h2 class="cta-title-horizontal">Stay Updated with Cross-Chain Tools</h2>
                </div>

                <div class="email-signup-horizontal">
                    <form id="contactForm" onsubmit="sendEmail(event)">
                        <div class="email-form-horizontal">
                            <input type="email" id="email" name="email" class="email-input-horizontal" placeholder="Enter your email address" required>
                            <button type="submit" class="email-submit-horizontal">Subscribe</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</section>

<style>
/* Horizontal CTA Section Styles */
.cta {
    padding: 60px 0;
    background: transparent;
}

.cta-container-horizontal {
    background: rgba(0, 0, 0, 0.8);
    border: 2px solid var(--border-color, #27272a);
    border-radius: 16px;
    padding: 40px;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 20px rgba(0, 255, 234, 0.1);
    position: relative;
    overflow: hidden;
}

.cta-container-horizontal::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
}

.cta-content-horizontal {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
    flex-wrap: wrap;
}

.cta-text-horizontal {
    flex: 1;
    min-width: 300px;
}

.cta-title-horizontal {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
    text-shadow: 0 0 15px rgba(0, 255, 234, 0.5);
    background: linear-gradient(45deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.email-signup-horizontal {
    flex: 1;
    min-width: 300px;
}

.email-form-horizontal {
    display: flex;
    gap: 15px;
    align-items: center;
}

.email-input-horizontal {
    flex: 1;
    padding: 14px 20px;
    background: rgba(0, 0, 0, 0.5);
    border: 2px solid var(--border-color, #27272a);
    border-radius: 8px;
    color: #ffffff;
    font-size: 16px;
    transition: all 0.3s ease;
}

.email-input-horizontal:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 15px rgba(0, 255, 234, 0.3);
}

.email-input-horizontal::placeholder {
    color: var(--text-muted, #a1a1aa);
}

.email-submit-horizontal {
    padding: 14px 28px;
    background: linear-gradient(45deg, var(--primary), var(--secondary));
    color: black;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
    white-space: nowrap;
}

.email-submit-horizontal:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 255, 234, 0.4);
}

/* Responsive CTA */
@media (max-width: 768px) {
    .cta-content-horizontal {
        flex-direction: column;
        text-align: center;
        gap: 25px;
    }

    .cta-text-horizontal,
    .email-signup-horizontal {
        min-width: 100%;
    }

    .cta-title-horizontal {
        font-size: 24px;
    }

    .email-form-horizontal {
        flex-direction: column;
        gap: 15px;
    }

    .email-input-horizontal,
    .email-submit-horizontal {
        width: 100%;
    }
}

@media (max-width: 480px) {
    .cta-container-horizontal {
        padding: 30px 20px;
    }

    .cta-title-horizontal {
        font-size: 22px;
    }
}

/* Hero Section Override - More specific selector to override global styles */
.hero {
    padding: 2.5rem 0 !important;
    min-height: auto !important;
    border-bottom: none !important;
}

/* Hero Section Centered Styles */
.hero-content-centered {
    text-align: center;
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem 20px;
}

.hero-content-centered h1 {
    font-size: 64px;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 35px 0;
    line-height: 1.1;
    text-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
    position: relative;
}

.typewriter {
    color: var(--primary);
    position: relative;
    display: inline-block;
    overflow: hidden;
    white-space: nowrap;
    width: 0;
    animation: typewriter-complete 8s infinite;
}

.typewriter::after {
    content: '|';
    color: var(--primary);
    animation: blink 1s infinite;
    text-shadow: 0 0 5px var(--primary);
}

@keyframes typewriter-complete {
    /* Typing phase - 0 to 1.6 seconds */
    0% {
        width: 0;
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }
    20% {
        width: 100%;
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }

    /* Glitch phase during display - 1.6 to 5.6 seconds */
    21%, 22% {
        width: 100%;
        transform: translate(2px, 0) skew(0deg);
        text-shadow: -2px 0 var(--secondary), 2px 0 var(--primary);
    }
    23%, 24% {
        width: 100%;
        transform: translate(-2px, 0) skew(0deg);
        text-shadow: 2px 0 var(--secondary), -2px 0 var(--primary);
    }
    24.5% {
        width: 100%;
        transform: translate(0, 0) skew(5deg);
        text-shadow: 0 0 10px var(--primary);
    }

    /* Continue glitch pattern */
    30%, 31% {
        width: 100%;
        transform: translate(2px, 0) skew(0deg);
        text-shadow: -2px 0 var(--secondary), 2px 0 var(--primary);
    }
    32%, 33% {
        width: 100%;
        transform: translate(-2px, 0) skew(0deg);
        text-shadow: 2px 0 var(--secondary), -2px 0 var(--primary);
    }
    33.5% {
        width: 100%;
        transform: translate(0, 0) skew(5deg);
        text-shadow: 0 0 10px var(--primary);
    }

    /* Normal display between glitches */
    25%, 29%, 34%, 70% {
        width: 100%;
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }

    /* Backspace phase - realistic character-by-character deletion */
    75% {
        width: 80%; /* 4/5 characters - "Tool" */
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }
    82% {
        width: 60%; /* 3/5 characters - "Too" */
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }
    89% {
        width: 40%; /* 2/5 characters - "To" */
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }
    94% {
        width: 20%; /* 1/5 characters - "T" */
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }
    98%, 100% {
        width: 0; /* Fully deleted */
        transform: translate(0, 0) skew(0deg);
        text-shadow: 0 0 10px var(--primary);
    }
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

.hero-content-centered h3 {
    font-size: 28px;
    font-weight: 400;
    color: #ffffff;
    margin: 0 0 30px 0;
    line-height: 1.4;
    text-shadow: 0 0 15px rgba(255, 255, 255, 0.5);
}

/* Responsive adjustments for centered hero */
@media (max-width: 768px) {
    .hero-content-centered {
        padding: 1rem 20px;
    }

    .hero-content-centered h1 {
        font-size: 48px;
    }

    .hero-content-centered h3 {
        font-size: 20px;
    }
}

@media (max-width: 480px) {
    .hero-content-centered {
        padding: 1rem 15px;
    }

    .hero-content-centered h1 {
        font-size: 40px;
    }

    .hero-content-centered h3 {
        font-size: 18px;
    }
}

/* Tools Section Styles - Matrix Theme */
.tools-section {
    padding: 0 0 2.5rem 0;
    background: transparent;
    position: relative;
    margin-top: -1.5rem;
}

.tools-content {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 60px;
}

.tool-card {
    background: rgba(0, 0, 0, 0.8);
    border: 2px solid var(--border-color, #27272a);
    border-radius: 16px;
    padding: 40px;
    box-shadow: 0 4px 20px rgba(0, 255, 234, 0.1);
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
    position: relative;
    overflow: hidden;
}

.tool-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
}

.tool-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 30px rgba(0, 255, 234, 0.2);
    border-color: var(--primary);
}

.tool-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 15px;
}

.tool-tags {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.tag {
    background: rgba(0, 255, 234, 0.2);
    color: var(--primary);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border: 1px solid rgba(0, 255, 234, 0.3);
}

.tool-date {
    color: var(--text-muted, #a1a1aa);
    font-size: 14px;
    font-weight: 500;
}

.tool-title {
    font-size: 28px;
    font-weight: 700;
    color: var(--text, #ffffff);
    margin: 0 0 15px 0;
    line-height: 1.3;
    background: linear-gradient(45deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.tool-status {
    margin-bottom: 20px;
}

.status-badge {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.status-badge.live {
    background: rgba(34, 197, 94, 0.2);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-badge.beta {
    background: rgba(245, 158, 11, 0.2);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.3);
}

.status-badge.coming-soon {
    background: rgba(156, 163, 175, 0.2);
    color: #9ca3af;
    border: 1px solid rgba(156, 163, 175, 0.3);
}

.tool-description {
    margin-bottom: 30px;
}

.tool-description p {
    font-size: 16px;
    line-height: 1.6;
    color: var(--text, #ffffff);
    margin: 0;
}

.tool-details {
    margin-bottom: 20px;
    padding: 20px 0;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.details-horizontal {
    display: flex;
    align-items: center;
    gap: 15px;
    flex-wrap: wrap;
    font-size: 14px;
    color: #e2e8f0;
    font-weight: 500;
}

.details-horizontal .detail-text:not(:last-child):after {
    content: ' | ';
    color: var(--primary);
    margin-left: 15px;
}

.detail-text {
    color: #e2e8f0;
}

.tool-hiring-impact {
    margin-bottom: 30px;
    padding: 15px;
    background: rgba(0, 255, 234, 0.05);
    border: 1px solid rgba(0, 255, 234, 0.2);
    border-radius: 8px;
}

.tool-hiring-impact p {
    margin: 0;
    font-size: 14px;
    color: var(--primary);
    line-height: 1.5;
}

.tool-hiring-impact strong {
    color: #ffffff;
}

.tool-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}

.action-btn {
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    border: none;
    cursor: pointer;
    transition: all 0.3s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.action-btn.primary {
    background: linear-gradient(45deg, var(--primary), var(--secondary));
    color: black;
    font-weight: 700;
    box-shadow: 0 4px 15px rgba(0, 255, 234, 0.3);
}

.action-btn.primary:hover:not(.disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 255, 234, 0.5);
    color: white;
}

.action-btn.primary.beta {
    background: linear-gradient(45deg, #f59e0b, #fbbf24);
    color: black;
}

.action-btn.primary.beta:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(245, 158, 11, 0.5);
    color: white;
}

.action-btn.secondary {
    background: transparent;
    color: var(--primary);
    border: 2px solid var(--primary);
}

.action-btn.secondary:hover:not(.disabled) {
    background: var(--primary);
    color: black;
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 255, 234, 0.3);
}

.action-btn.tertiary {
    background: transparent;
    color: var(--primary);
    border: 2px solid var(--primary);
}

.action-btn.tertiary:hover {
    background: var(--primary);
    color: black;
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 255, 234, 0.3);
}

.action-btn.disabled {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-muted, #a1a1aa);
    cursor: not-allowed;
    opacity: 0.6;
    border: 2px solid rgba(255, 255, 255, 0.1);
}

/* Coming Soon Tool Styling */
.tool-card.coming-soon {
    opacity: 0.5;
    background: rgba(60, 60, 60, 0.3);
    border-color: rgba(120, 120, 120, 0.2);
}

.tool-card.coming-soon:hover {
    transform: none;
    box-shadow: 0 4px 20px rgba(0, 255, 234, 0.05);
    border-color: rgba(255, 255, 255, 0.2);
}

.tool-card.coming-soon .tool-title {
    color: #a1a1aa;
    background: none;
    -webkit-background-clip: initial;
    -webkit-text-fill-color: initial;
    background-clip: initial;
}

.tool-card.coming-soon .tool-description p {
    color: #71717a;
}

.tool-card.coming-soon .tag {
    background: rgba(255, 255, 255, 0.1);
    color: #a1a1aa;
    border-color: rgba(255, 255, 255, 0.1);
}

.tool-card.coming-soon .detail-text {
    color: #71717a;
}

.tool-card.coming-soon .details-horizontal .detail-text:not(:last-child):after {
    color: #71717a;
}

.tool-card.coming-soon .tool-hiring-impact {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
}

.tool-card.coming-soon .tool-hiring-impact p {
    color: #71717a;
}

.tool-card.coming-soon .tool-hiring-impact strong {
    color: #a1a1aa;
}

/* Responsive Design */
@media (max-width: 768px) {
    .tools-section {
        padding: 60px 0;
    }

    .tools-content {
        gap: 40px;
    }

    .tool-card {
        padding: 30px 20px;
    }

    .tool-title {
        font-size: 24px;
    }

    .tool-meta {
        flex-direction: column;
        align-items: flex-start;
    }

    .tool-actions {
        flex-direction: column;
    }

    .action-btn {
        width: 100%;
        justify-content: center;
    }

    .details-horizontal {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
}

@media (max-width: 480px) {
    .tool-card {
        padding: 25px 15px;
    }

    .tool-title {
        font-size: 22px;
    }

    .tool-description p {
        font-size: 15px;
    }
}
</style>
{% endblock %}

{% block scripts %}
{{ super() }}
<script>
    // Tools subscription form submission
    function sendEmail(event) {
        event.preventDefault();

        // Show loading state
        const submitBtn = event.target.querySelector('.email-submit-horizontal');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Subscribing...';
        submitBtn.disabled = true;

        // Initialize EmailJS with your public key
        emailjs.init("xSYgQUruN6qY2C0o2");

        const params = {
            name: 'Tools Subscriber',
            email: document.getElementById('email').value,
            tools_interests: 'all',
            message: 'Subscribed via tools updates form'
        };

        // Send email
        emailjs.send("service_gf8ewl9", "template_nad2dyc", params)
            .then(() => {
                alert("Thanks for subscribing to our tools updates! You'll receive notifications when new tools are launched.");
                document.getElementById('contactForm').reset();

                // Track newsletter subscription
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'newsletter_subscribe', {
                        'event_category': 'tools',
                        'event_label': 'tools_form'
                    });
                }
            })
            .catch((error) => {
                console.error('Error:', error);
                alert("Sorry, there was an error submitting your subscription. Please try again or reach out directly via LinkedIn.");
            })
            .finally(() => {
                // Reset button state
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            });
    }

    // Share tool function
    function shareTool(title, description) {
        if (navigator.share) {
            navigator.share({
                title: title,
                text: description,
                url: window.location.href
            }).catch(err => console.log('Error sharing:', err));
        } else {
            // Fallback for browsers without native sharing
            const url = window.location.href;
            const text = `Check out this tool: ${title} - ${description}`;

            if (navigator.clipboard) {
                navigator.clipboard.writeText(`${text}\\n\\n${url}`).then(() => {
                    alert('Tool link copied to clipboard!');
                });
            } else {
                // Final fallback
                const textArea = document.createElement('textarea');
                textArea.value = `${text}\\n\\n${url}`;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                alert('Tool link copied to clipboard!');
            }
        }

        // Track sharing
        if (typeof gtag !== 'undefined') {
            gtag('event', 'tool_share', {
                'event_category': 'tools',
                'event_label': title
            });
        }
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        // Add subtle animations to tools on load
        const tools = document.querySelectorAll('.tool-card');
        tools.forEach((tool, index) => {
            tool.style.opacity = '0';
            tool.style.transform = 'translateY(20px)';
            setTimeout(() => {
                tool.style.transition = 'all 0.6s ease';
                tool.style.opacity = '1';
                tool.style.transform = 'translateY(0)';
            }, index * 150);
        });

        // Enhance mobile touch interactions
        if ('ontouchstart' in window) {
            document.querySelectorAll('.action-btn').forEach(btn => {
                btn.style.webkitTapHighlightColor = 'rgba(0,123,255,0.2)';
            });
        }
    });
</script>
{% endblock %}
    '''
    return render_template_string(template_str, cross_chain_tools=cross_chain_tools, tools_metrics=tools_metrics)