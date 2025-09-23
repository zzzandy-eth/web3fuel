from flask import Blueprint, render_template_string, redirect, url_for, request, jsonify, send_file
from datetime import datetime
import os

# Create the blueprint for research
research_bp = Blueprint('research', __name__, url_prefix='/research')

# Research papers data - First article published, others coming soon
research_papers = [
    {
        "title": "Security Models in Cross-Chain Bridges: LayerZero vs Axelar vs Wormhole Analysis",
        "synopsis": "Comprehensive security analysis of leading cross-chain bridge protocols, examining trust assumptions, validator models, and attack vectors across three major infrastructure providers.",
        "tags": ["Security", "Bridge Analysis", "Comparative Study"],
        "date": datetime(2025, 9, 20),
        "pages": 24,
        "key_factors": ["Trust assumptions comparison", "Validator model analysis", "Attack vector assessment", "Security trade-offs"],
        "pdf_file": "cross-chain-bridge-security-analysis.pdf",
        "slug": "cross-chain-bridge-security-analysis",
        "coming_soon": False
    },
    {
        "title": "Economic Incentives in Cross-Chain Protocol Design",
        "synopsis": "Deep-dive analysis of tokenomics, fee structures, and economic security models that drive cross-chain protocol sustainability and adoption.",
        "tags": ["Economics", "Tokenomics", "Protocol Design"],
        "date": datetime(2025, 12, 15),
        "pages": 32,
        "key_factors": ["Fee mechanism analysis", "Token utility assessment", "Economic security models", "Sustainable incentive design"],
        "pdf_file": "economic-incentives-cross-chain.pdf",
        "slug": "economic-incentives-cross-chain",
        "coming_soon": True
    },
    {
        "title": "Cross-Chain MEV: Opportunities and Risks in Multi-Chain Arbitrage",
        "synopsis": "Investigation of maximum extractable value (MEV) in cross-chain environments, analyzing arbitrage opportunities, sandwich attacks, and front-running strategies across bridges.",
        "tags": ["MEV", "Arbitrage", "DeFi"],
        "date": datetime(2026, 1, 15),
        "pages": 28,
        "key_factors": ["Cross-chain arbitrage patterns", "MEV extraction techniques", "Bridge-specific vulnerabilities", "Mitigation strategies"],
        "pdf_file": "cross-chain-mev-analysis.pdf",
        "slug": "cross-chain-mev-analysis",
        "coming_soon": True
    },
    {
        "title": "Consensus Mechanisms in Multi-Chain Environments",
        "synopsis": "Technical analysis of how different consensus mechanisms interact in cross-chain protocols, including finality guarantees, reorg handling, and security assumptions.",
        "tags": ["Consensus", "Infrastructure", "Technical Analysis"],
        "date": datetime(2026, 2, 15),
        "pages": 36,
        "key_factors": ["Finality comparison", "Reorg resistance", "Cross-chain security", "Consensus interoperability"],
        "pdf_file": "consensus-mechanisms-cross-chain.pdf",
        "slug": "consensus-mechanisms-cross-chain",
        "coming_soon": True
    }
]

# Research metrics
research_metrics = {
    "total_papers": len(research_papers),
    "protocols_analyzed": 15,
    "research_hours": 2400,
    "security_audits": 8
}

# Redirect old marketing-solutions URL to new research URL for SEO
@research_bp.route('/marketing-solutions')
@research_bp.route('/marketing-solutions/')
def redirect_marketing_solutions():
    return redirect(url_for('research.research'), code=301)

@research_bp.route('/')
def research():
    """Research page with cross-chain infrastructure content"""
    from flask import render_template
    return render_template('research.html', research_papers=research_papers, research_metrics=research_metrics)

@research_bp.route('/<slug>')
def article(slug):
    """Individual research article page"""
    from flask import render_template, abort

    # Find the article by slug
    article = None
    for paper in research_papers:
        if paper.get('slug') == slug:
            article = paper
            break

    if not article:
        abort(404)

    if article.get('coming_soon', False):
        abort(404)  # Don't show coming soon articles

    return render_template('research_article/security.html', article=article)

@research_bp.route('/download-research/<filename>')
def download_research(filename):
    """Download research PDF files"""
    # Validate filename exists in our research data
    valid_files = [research['pdf_file'] for research in research_papers]
    if filename not in valid_files:
        return jsonify({'error': 'Research paper not found'}), 404
    
    # Serve actual PDF files from static directory
    try:
        return send_file(
            f'../frontend/static/research/pdfs/{filename}',
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except FileNotFoundError:
        return jsonify({'error': 'PDF file not found on server'}), 404

@research_bp.route('/subscribe-research', methods=['POST'])
def subscribe_research():
    """Handle research newsletter subscription"""
    email = request.json.get('email') if request.is_json else request.form.get('email')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # In production, this would integrate with email service
    # For now, return success response
    return jsonify({
        'success': True,
        'message': 'Successfully subscribed to research updates',
        'email': email
    })