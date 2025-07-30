from flask import Flask, render_template_string
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.blog import blog_bp
from routes.contact import contact_bp
from routes.trading_suite import trading_suite_bp
from routes.marketing_solutions import marketing_solutions_bp

app = Flask(__name__)

# Register blueprints
app.register_blueprint(blog_bp)
app.register_blueprint(contact_bp)
app.register_blueprint(trading_suite_bp)
app.register_blueprint(marketing_solutions_bp)

# HTML template as a string
template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web3Fuel.io - Financial Technology Solutions</title>
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
            --success: #22c55e;
            --warning: #f59e0b;
            --gradient-1: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --gradient-2: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --gradient-3: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            background-color: var(--background);
            color: var(--text);
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
            margin: 0;
            overflow-x: hidden;
            position: relative;
            line-height: 1.5;
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

        .container {
            max-width: 90%;
            margin: 0 auto;
            padding: 0 1rem;
            position: relative;
            z-index: 1;
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

        .nav-link.active {
            color: var(--background);
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 25px rgba(0, 255, 234, 0.5);
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

        /* Hero Section */
        .hero {
            position: relative;
            overflow: hidden;
            padding: 5rem 0;
            border-bottom: 1px solid var(--border-color);
            min-height: 80vh;
            display: flex;
            align-items: center;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 3rem;
        }

        .hero-grid > div:first-child {
            margin-left: 0;
        }

        .hero h1 {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            line-height: 1.2;
        }

        .hero-accent {
            color: var(--primary);
            text-shadow: 0 0 10px var(--primary);
            animation: glitch 2s infinite, glitch-text 2s infinite;
            position: relative;
            display: inline-block;
        }

        /* Updated hero subtitle */
        .hero-subtitle {
            color: #e2e8f0;
            font-size: 1.55rem;
            margin-bottom: 2rem;
            max-width: 32rem;
            line-height: 1.6;
        }

        /* Homepage2 style hero stats */
        .hero-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 3rem;
            margin-bottom: 0.1rem;
        }

        .stat-card {
            background: rgba(0, 0, 0, 0.6);
            border: 2px solid var(--border-color);
            border-radius: 1rem;
            padding: 1rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--gradient-3);
        }

        .stat-card:hover {
            border-color: var(--primary);
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 255, 234, 0.2);
        }

        .stat-value {
            font-size: 1.7rem;
            font-weight: 900;
            color: var(--primary);
            margin-bottom: 0.3rem;
            text-shadow: 0 0 20px var(--primary);
        }

        .stat-label {
            font-size: 1rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .hero-visual {
            position: relative;
            width: 100%;
            height: 350px;
            perspective: 1000px;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .cube {
            width: 250px;
            height: 250px;
            position: relative;
            transform-style: preserve-3d;
            animation: rotate 15s infinite linear;
        }
        
        .cube-face {
            position: absolute;
            width: 250px;
            height: 250px;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 2.5rem;
            background: rgba(0, 0, 0, 0.7);
            border: 2px solid var(--primary);
            color: var(--primary);
            box-shadow: 0 0 15px var(--primary);
        }
        
        .face-front { transform: translateZ(125px); }
        .face-back { transform: rotateY(180deg) translateZ(125px); }
        .face-right { transform: rotateY(90deg) translateZ(125px); }
        .face-left { transform: rotateY(-90deg) translateZ(125px); }
        .face-top { transform: rotateX(90deg) translateZ(125px); }
        .face-bottom { transform: rotateX(-90deg) translateZ(125px); }

        /* Services Section - Using Homepage2 Style */
        .services-section {
            padding: 6rem 0;
            border-bottom: 1px solid var(--border-color);
        }

        .services-header {
            text-align: center;
            margin-bottom: 3rem;
        }

        .services-title {
            font-size: 2.8rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            text-align: center;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .services-subtitle {
            text-align: center;
            font-size: 1.2rem;
            color: #e2e8f0;
            margin-bottom: 4rem;
            max-width: 700px;
            margin-left: auto;
            margin-right: auto;
            line-height: 1.6;
        }

        .products-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 3rem;
            margin-top: 3rem;
        }

        .product-card {
            background: var(--card-bg);
            border: 2px solid var(--border-color);
            border-radius: 1.5rem;
            padding: 3rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .product-card.trading {
            background: linear-gradient(135deg, rgba(0, 255, 234, 0.05) 0%, rgba(0, 0, 0, 0.8) 100%);
        }

        .product-card.marketing {
            background: linear-gradient(135deg, rgba(255, 0, 255, 0.05) 0%, rgba(0, 0, 0, 0.8) 100%);
        }

        .product-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 5px;
        }

        .product-card.trading::before {
            background: var(--gradient-3);
        }

        .product-card.marketing::before {
            background: var(--gradient-2);
        }

        .product-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 20px 40px rgba(0, 255, 234, 0.15);
        }

        .product-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .product-icon {
            font-size: 3rem;
            filter: drop-shadow(0 0 15px currentColor);
        }

        .product-title {
            font-size: 2rem;
            font-weight: 700;
        }

        .product-card.trading .product-title {
            color: var(--primary);
        }

        .product-card.marketing .product-title {
            color: var(--secondary);
        }

        .product-description {
            font-size: 1.3rem;
            color: #e2e8f0;
            margin-bottom: 2rem;
            line-height: 1.6;
        }

        .product-features {
            list-style: none;
            margin-bottom: 2.5rem;
        }

        .product-features li {
            padding: 0.75rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-muted);
            font-size: 1.15rem;
            position: relative;
            padding-left: 2rem;
        }

        .product-features li::before {
            content: '✓';
            position: absolute;
            left: 0;
            color: var(--success);
            font-weight: bold;
            font-size: 1.2rem;
        }

        .product-cta {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 1rem 2rem;
            border-radius: 0.75rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            font-size: 1.1rem;
        }

        .product-card.trading .product-cta {
            background: var(--gradient-3);
            color: black;
        }

        .product-card.marketing .product-cta {
            background: var(--gradient-2);
            color: black;
        }

        .product-cta:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 255, 234, 0.3);
        }

        /* AI Intelligence Section - V0 Style */
        .ai-intelligence-section {
            padding: 6rem 0;
            border-bottom: 1px solid var(--border-color);
        }

        .ai-intelligence-title {
            font-size: 2.8rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 1.5rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .ai-intelligence-subtitle {
            text-align: center;
            font-size: 1.4rem;
            color: #e2e8f0;
            margin-bottom: 4rem;
            max-width: 700px;
            margin-left: auto;
            margin-right: auto;
            line-height: 1.6;
        }

        .ai-solutions-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 3rem;
        }

        .solution-category {
            text-align: left;
        }

        .solution-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .solution-icon {
            font-size: 2rem;
            filter: drop-shadow(0 0 10px currentColor);
            margin-left: 0;
        }

        .solution-title {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .trading-category .solution-title {
            color: var(--primary);
        }

        .marketing-category .solution-title {
            color: var(--secondary);
        }

        .solution-items {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .solution-item {
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            text-align: left;
            background: rgba(255, 255, 255, 0.02);
            padding: 1.5rem;
            border-radius: 1rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }

        .solution-item:hover {
            background: rgba(255, 255, 255, 0.05);
            transform: translateX(5px);
        }

        .solution-item-icon {
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            font-size: 1.25rem;
        }

        .trading-category .solution-item-icon {
            background: rgba(0, 255, 234, 0.2);
            color: var(--primary);
        }

        .marketing-category .solution-item-icon {
            background: rgba(255, 0, 255, 0.2);
            color: var(--secondary);
        }

        .solution-item-content h4 {
            font-weight: 600;
            font-size: 1.3rem;
            color: var(--text);
            margin-bottom: 0.25rem;
        }

        .solution-item-content p {
            color: var(--text-muted);
            font-size: 1.15rem;
            line-height: 1.4;
        }

        /* Split-Screen Comparison Cards */
        .comparison-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 4rem;
            margin-top: 3rem;
        }

        .comparison-card {
            background: var(--card-bg);
            border: 2px solid var(--border-color);
            border-radius: 1.5rem;
            padding: 3rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .comparison-card.trading {
            border-left: 5px solid var(--primary);
        }

        .comparison-card.marketing {
            border-left: 5px solid var(--secondary);
        }

        .comparison-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 20px 40px rgba(0, 255, 234, 0.15);
        }

        .comparison-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .comparison-badge {
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
        }

        .comparison-card.trading .comparison-badge {
            background: rgba(0, 255, 234, 0.2);
            color: var(--primary);
        }

        .comparison-card.marketing .comparison-badge {
            background: rgba(255, 0, 255, 0.2);
            color: var(--secondary);
        }

        .comparison-quote {
            font-size: 1.3rem;
            font-style: italic;
            color: #e2e8f0;
            margin-bottom: 1rem;
            line-height: 1.5;
        }

        .comparison-result {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 2rem;
        }

        .comparison-card.trading .comparison-result {
            color: var(--success);
        }

        .comparison-card.marketing .comparison-result {
            color: var(--success);
        }

        .feature-list {
            list-style: none;
        }

        .feature-list li {
            padding: 0.75rem 0;
            color: var(--text-muted);
            position: relative;
            padding-left: 2rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            font-size: 1.15rem;
        }

        .feature-list li::before {
            content: '▶';
            position: absolute;
            left: 0;
            font-size: 0.8rem;
        }

        .comparison-card.trading .feature-list li::before {
            color: var(--primary);
        }

        .comparison-card.marketing .feature-list li::before {
            color: var(--secondary);
        }

        /* Additional cards from homepage2 */
        .ai-showcase-cards {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
            margin-top: 3rem;
        }

        .showcase-card {
            background: var(--card-bg);
            padding: 1.5rem;
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.1);
            text-decoration: none !important;
        }

        .showcase-card:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.2);
        }

        .showcase-card h3 {
            color: var(--secondary);
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
            text-shadow: 0 0 10px var(--secondary);
            text-decoration: none !important;
        }

        .showcase-card p {
            color: var(--text);
            font-size: 1.15rem;
            text-decoration: none !important;
        }

        /* Final CTA Section */
        .ai-cta-section {
            text-align: center;
            margin-top: 4rem;
            padding: 3rem 2rem;
            background: linear-gradient(135deg, rgba(0, 0, 0, 0.8) 0%, rgba(20, 20, 30, 0.9) 100%);
            border-radius: 2rem;
            border: 2px solid var(--border-color);
            position: relative;
            overflow: hidden;
        }

        .ai-cta-section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 5px;
            background: linear-gradient(90deg, var(--primary), var(--secondary), #7c3aed);
        }

        .ai-cta-title {
            font-size: 1.7rem;
            font-weight: 700;
            margin-bottom: 1rem;
            color: var(--text);
        }

        .ai-cta-description {
            color: #e2e8f0;
            margin-bottom: 2rem;
            line-height: 1.6;
            font-size: 1.2rem;
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
        }

        .ai-cta-button {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 1rem 2rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            color: black;
            text-decoration: none;
            border-radius: 0.5rem;
            font-weight: 600;
            transition: all 0.3s ease;
            font-size: 1.2rem;
        }

        .ai-cta-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 255, 234, 0.4);
        }

        /* Contact Section */
        .cta {
            padding: 4rem 0;
        }

        .cta-container {
            background: linear-gradient(to right, rgba(0, 0, 0, 0.8), rgba(20, 20, 30, 0.9)), url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="none"/><path d="M0,0 L100,100 M0,100 L100,0" stroke="rgba(124, 58, 237, 0.1)" stroke-width="1"/></svg>');
            border-radius: 1rem;
            padding: 3rem 2rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 0 30px rgba(124, 58, 237, 0.2);
        }

        .cta-content {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }

        .cta-text {
            text-align: left;
            padding: 2rem;
        }

        .cta-title {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 1rem;
            color: var(--primary);
        }

        .cta-description {
            color: #e2e8f0;
            margin-bottom: 1rem;
            line-height: 1.6;
            font-size: 1.2rem;
            margin-top: 2rem;
        }

        .contact-form {
            background: rgba(0, 0, 0, 0.3);
            padding: 2rem;
            border-radius: 0.5rem;
            border: 1px solid var(--border-color);
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            color: #e2e8f0;
            font-size: 0.875rem;
        }

        .form-input {
            width: 100%;
            padding: 0.75rem;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            color: white;
            font-size: 1rem;
            transition: border-color 0.2s;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(0, 255, 234, 0.1);
        }

        .form-textarea {
            min-height: 120px;
            resize: vertical;
        }

        .form-submit {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.75rem 1.5rem;
            background-color: var(--primary);
            color: black;
            font-weight: 600;
            border-radius: 0.375rem;
            cursor: pointer;
            border: none;
            transition: all 0.3s ease;
            width: 100%;
            font-size: 1rem;
            margin-top: 0.5rem;
        }

        .form-submit:hover {
            background-color: #00d6c4;
            transform: translateY(-2px);
        }

        .appointment-toggle {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 2rem;
            padding: 1rem;
            background: rgba(0, 255, 234, 0.05);
            border: 1px solid rgba(0, 255, 234, 0.2);
            border-radius: 0.5rem;
        }

        .toggle-checkbox {
            width: 1.25rem;
            height: 1.25rem;
            accent-color: var(--primary);
            cursor: pointer;
        }

        .toggle-label {
            color: var(--text);
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
        }

        .appointment-fields {
            display: none;
            background: rgba(0, 255, 234, 0.05);
            border: 1px solid rgba(0, 255, 234, 0.2);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .appointment-fields.show {
            display: block;
        }

        .appointment-header {
            color: var(--primary);
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            text-align: center;
        }

        /* Date/time picker styling */
        input[type="datetime-local"] {
            cursor: pointer;
            position: relative;
            color: #a1a1aa;
        }

        input[type="datetime-local"]::-webkit-calendar-picker-indicator {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            width: auto;
            height: auto;
            background: transparent;
            cursor: pointer;
        }

        input[type="datetime-local"]:focus {
            color: white;
        }

        input[type="datetime-local"]:valid {
            color: white;
        }

        /* Fixed dropdown styling */
        select.form-input {
            background: rgba(0, 0, 0, 0.8);
            color: white;
        }

        select.form-input option {
            background: rgba(0, 0, 0, 0.95);
            color: white;
            padding: 0.5rem;
        }

        select.form-input option:hover {
            background: rgba(0, 255, 234, 0.2);
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

        /* Animations */
        @keyframes pulse {
            0%, 100% {
                filter: drop-shadow(0 0 10px var(--secondary));
            }
            50% {
                filter: drop-shadow(0 0 20px var(--secondary));
            }
        }

        @keyframes rotate {
            0% { transform: rotateX(0) rotateY(0) rotateZ(0); }
            100% { transform: rotateX(360deg) rotateY(360deg) rotateZ(360deg); }
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

        /* Media Queries */
        @media (min-width: 768px) {
            .nav-desktop {
                display: flex;
                align-items: center;
                gap: 1.5rem;
            }
            
            .menu-button {
                display: none;
            }
            
            .hero h1 {
                font-size: 3.5rem;
            }
            
            .hero-grid {
                grid-template-columns: 1fr 1fr;
                align-items: center;
            }
            
            .products-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .ai-solutions-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .comparison-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .cta-content {
                grid-template-columns: 1fr 1fr;
                align-items: center;
            }

            .footer-main {
                flex-direction: row;
                align-items: flex-start;
            }
            
            .footer-bottom {
                justify-content: space-between;
            }
        }

        /* Mobile Menu Styles */
        .mobile-menu {
            position: fixed;
            top: 0;
            right: -100%;
            width: 100%;
            height: 100vh;
            background: rgba(0, 0, 0, 0.95);
            backdrop-filter: blur(20px);
            transition: right 0.3s ease;
            z-index: 50;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 2rem;
        }

        .mobile-menu.active {
            right: 0;
        }

        .mobile-nav-link {
            color: var(--text);
            text-decoration: none;
            font-size: 1.5rem;
            font-weight: 600;
            padding: 1rem;
            transition: color 0.3s ease;
        }

        .mobile-nav-link:hover {
            color: var(--primary);
        }

        .close-menu {
            position: absolute;
            top: 2rem;
            right: 2rem;
            background: none;
            border: none;
            color: var(--text);
            font-size: 2rem;
            cursor: pointer;
        }

        @media (max-width: 767px) {
            .container {
                max-width: 95%;
                padding: 0 1rem;
            }
            
            .hero h1 {
                font-size: 2rem;
                line-height: 1.1;
            }
            
            .hero-subtitle {
                font-size: 1.2rem;
            }
            
            .hero-visual {
                height: 250px;
            }
            
            .cube {
                width: 180px;
                height: 180px;
            }
            
            .cube-face {
                width: 180px;
                height: 180px;
                font-size: 1.8rem;
            }
            
            .face-front { transform: translateZ(90px); }
            .face-back { transform: rotateY(180deg) translateZ(90px); }
            .face-right { transform: rotateY(90deg) translateZ(90px); }
            .face-left { transform: rotateY(-90deg) translateZ(90px); }
            .face-top { transform: rotateX(90deg) translateZ(90px); }
            .face-bottom { transform: rotateX(-90deg) translateZ(90px); }
            
            .services-title,
            .ai-intelligence-title {
                font-size: 2rem;
            }
            
            .product-title {
                font-size: 1.5rem;
            }
            
            .product-description {
                font-size: 1.1rem;
            }
            
            .contact-form {
                padding: 1.5rem;
            }
            
            .cta-title {
                font-size: 1.5rem;
            }
            
            .cta-description {
                font-size: 1rem;
            }
            
            .social-links {
                gap: 1rem;
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

            .cta-content {
                grid-template-columns: 1fr;
            }
            
            .form-submit {
                width: 100%;
            }
        }

        @media (min-width: 768px) {
            .container {
                max-width: 85%;
            }
            
            .hero-grid > div:first-child {
                margin-left: 2.5rem;
            }
            
            .solution-icon {
                margin-left: 8rem;
            }
        }

        @media (min-width: 1200px) {
            .container {
                max-width: 70%;
            }
            
            .nav-desktop {
                gap: 0.75rem;
            }
        }
        
        @media (min-width: 1920px) {
            .container {
                max-width: 1600px;
            }
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
                <a href="/trading-suite" class="nav-link">Trading Suite</a>
                <a href="/marketing-solutions" class="nav-link">Marketing Solutions</a>
                <a href="/blog" class="nav-link">Blog</a>
                <a href="/contact" class="nav-link contact-highlight">Contact</a>
            </nav>
            
            <button class="menu-button" id="menu-button">☰</button>
        </div>
        
        <!-- Mobile Menu -->
        <div class="mobile-menu" id="mobile-menu">
            <button class="close-menu" id="close-menu">✕</button>
            <nav>
                <a href="/trading-suite" class="mobile-nav-link">Trading Suite</a>
                <a href="/marketing-solutions" class="mobile-nav-link">Marketing Solutions</a>
                <a href="/blog" class="mobile-nav-link">Blog</a>
                <a href="/contact" class="mobile-nav-link">Contact</a>
            </nav>
        </div>
    </header>
    
    <!-- Hero Section -->
    <section class="hero">
        <div class="container">
            <div class="hero-grid">
                <div>
                    <h1>One AI Engine. <span class="hero-accent">Two Powerful</span><br>Solutions.</h1>
                    <p class="hero-subtitle">The same AI algorithms that predict market breakouts also identify leads most likely to convert. Whether you're trading Bitcoin or closing clients, success comes from data-driven decisions.</p>
                </div>
                
                <div class="hero-visual">
                    <div class="cube">
                        <div class="cube-face face-front">AI</div>
                        <div class="cube-face face-back">BTC</div>
                        <div class="cube-face face-right">SEO</div>
                        <div class="cube-face face-left">SPY</div>
                        <div class="cube-face face-top">PPC</div>
                        <div class="cube-face face-bottom">DATA</div>
                    </div>
                </div>
            </div>
            
            <!-- Hero stats spanning full width -->
            <div class="hero-stats">
                <div class="stat-card">
                    <div class="stat-value">68.4%</div>
                    <div class="stat-label">Trading Win Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">+212%</div>
                    <div class="stat-label">ROI on AI Marketing</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">40+</div>
                    <div class="stat-label">Automated Conversions Delivered</div>
                </div>
            </div>
        </div>
    </section>
    
    <!-- Services Section - Homepage2 Style -->
    <section class="services-section">
        <div class="container">
            <h2 class="services-title">Choose Your AI-Powered Edge</h2>
            
            <div class="products-grid">
                <!-- AI Trading Suite -->
                <div class="product-card trading">
                    <div class="product-header">
                        <span class="product-icon">🧠</span>
                        <h3 class="product-title">AI Trading Suite</h3>
                    </div>
                    <p class="product-description">Get the edge with real-time analysis, price prediction models, and automated trading tools — built for crypto traders and powered by machine learning.</p>
                    
                    <ul class="product-features">
                        <li>24/7 live charting & analytics</li>
                        <li>AI-driven market forecasts</li>
                        <li>Portfolio tracking & trade automation</li>
                        <li>Risk assessment algorithms</li>
                    </ul>
                    
                    <div style="text-align: center;">
                        <a href="/trading-suite" class="product-cta">
                            Explore the Trading Suite →
                        </a>
                    </div>
                </div>
                
                <!-- AI Marketing Solutions -->
                <div class="product-card marketing">
                    <div class="product-header">
                        <span class="product-icon">🎯</span>
                        <h3 class="product-title">AI Marketing Solutions</h3>
                    </div>
                    <p class="product-description">Attract more clients and convert leads faster with AI-powered marketing systems designed for regulated, trust-based industries.</p>
                    
                    <ul class="product-features">
                        <li>Predictive lead scoring</li>
                        <li>AI-powered chatbots & onboarding</li>
                        <li>SEO, content, and ad automation</li>
                        <li>Conversion optimization systems</li>
                    </ul>
                    
                    <div style="text-align: center;">
                        <a href="/marketing-solutions" class="product-cta">
                            Discover Marketing Solutions →
                        </a>
                    </div>
                </div>
            </div>
            <div class="ai-cta-section">
                <h3 class="ai-cta-title">The Same Intelligence, Different Applications</h3>
                <p class="ai-cta-description">
                    Whether you're timing a market trade or optimizing funnels, <br>success comes from data-driven decisions.
                </p>
                <a href="#contact" class="ai-cta-button">
                    Schedule a Consultation →
                </a>
            </div>
        </div>
    </section>
    
    <!-- AI-Powered Intelligence Section - V0 Style with Homepage2 Cards -->
    <section class="ai-intelligence-section">
        <div class="container">
            <h2 class="ai-intelligence-title">AI-Powered Intelligence in Action</h2>
            <p class="ai-intelligence-subtitle">See how the same AI strategies that beat the market <br>can also transform client acquisition.</p>
            
            <div class="ai-solutions-grid">
                <!-- Cryptocurrency Trading -->
                <div class="solution-category trading-category">
                    <div class="solution-header">
                        <span class="solution-icon">📈</span>
                        <h3 class="solution-title">Cryptocurrency Trading</h3>
                    </div>
                    <div class="solution-items">
                        <div class="solution-item">
                            <div class="solution-item-icon">🧠</div>
                            <div class="solution-item-content">
                                <h4>Market Intelligence</h4>
                                <p>AI-powered market sentiment analysis and trend forecasting</p>
                            </div>
                        </div>
                        <div class="solution-item">
                            <div class="solution-item-icon">🛡️</div>
                            <div class="solution-item-content">
                                <h4>Risk Management</h4>
                                <p>Portfolio volatility modeling and risk management tools</p>
                            </div>
                        </div>
                        <div class="solution-item">
                            <div class="solution-item-icon">⚡</div>
                            <div class="solution-item-content">
                                <h4>Automatic Trading</h4>
                                <p>Real-time alerts and scheduled trading strategies</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Professional Services -->
                <div class="solution-category marketing-category">
                    <div class="solution-header">
                        <span class="solution-icon">🎯</span>
                        <h3 class="solution-title">Professional Services</h3>
                    </div>
                    <div class="solution-items">
                        <div class="solution-item">
                            <div class="solution-item-icon">🎯</div>
                            <div class="solution-item-content">
                                <h4>Lead Generation</h4>
                                <p>AI-powered customer targeting and qualification</p>
                            </div>
                        </div>
                        <div class="solution-item">
                            <div class="solution-item-icon">💬</div>
                            <div class="solution-item-content">
                                <h4>Content Optimization</h4>
                                <p>Personalized messaging and SEO strategy</p>
                            </div>
                        </div>
                        <div class="solution-item">
                            <div class="solution-item-icon">📊</div>
                            <div class="solution-item-content">
                                <h4>Conversion Tracking</h4>
                                <p>Real-time analytics and A/B testing</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Split-Screen Comparison -->
            <div class="comparison-grid">
                <!-- Trading Use Case -->
                <div class="comparison-card trading">
                    <div class="comparison-header">
                        <span class="comparison-badge">Trading Use Case</span>
                    </div>
                    <p class="comparison-quote">"When Bitcoin hit $100,000, our AI predicted the breakout 72 hours early"</p>
                    <p class="comparison-result">→ Result: 23% portfolio gain in 5 days</p>
                    
                    <ul class="feature-list">
                        <li>Tracks 500+ crypto pairs</li>
                        <li>Volatility models with 78%+ accuracy</li>
                        <li>Automated portfolio rebalancing</li>
                    </ul>
                </div>
                
                <!-- Marketing Use Case -->
                <div class="comparison-card marketing">
                    <div class="comparison-header">
                        <span class="comparison-badge">Marketing Use Case</span>
                    </div>
                    <p class="comparison-quote">"When a lead visited 3+ pages, our AI predicted 89% conversion probability"</p>
                    <p class="comparison-result">→ Result: Insurance agent closed 3 deals that week</p>
                    
                    <ul class="feature-list">
                        <li>Lead generation up +247%</li>
                        <li>Conversion funnels improved +189%</li>
                        <li>Chatbots qualifying leads 24/7</li>
                    </ul>
                </div>
            </div>
        </div>
    </section>
    
    <!-- CTA Section -->
    <section class="cta" id="contact">
        <div class="container">
            <div class="cta-container">
                <div class="cta-content">
                    <div class="cta-text">
                        <h2 class="cta-title">Ready to Apply Financial-Grade AI <br>to Your Business?</h2>
                        <p class="cta-description">Whether you're looking to automate trades or acquire clients, we apply the same high-performance AI systems to grow your bottom line. No long-term commitments required.</p>
                    </div>
                    
                    <div class="contact-form">
                        <form id="contactForm" onsubmit="sendEmail(event)">
                            <div class="form-group">
                                <label for="name" class="form-label">Name</label>
                                <input type="text" id="name" name="name" class="form-input" required>
                            </div>
                            
                            <div class="form-group">
                                <label for="email" class="form-label">Email</label>
                                <input type="email" id="email" name="email" class="form-input" required>
                            </div>

                            <div class="appointment-toggle">
                                <input type="checkbox" id="appointmentToggle" class="toggle-checkbox" onchange="toggleAppointmentFields()">
                                <label for="appointmentToggle" class="toggle-label">Click here to schedule an appointment during this inquiry</label>
                            </div>

                            <!-- Appointment Fields (Hidden by default) -->
                            <div class="appointment-fields" id="appointmentFields">
                                <div class="appointment-header">📅 Schedule Your Meeting</div>
                                <div class="form-group">
                                    <label for="datetime" class="form-label">Preferred Date & Time (EST)</label>
                                    <input type="datetime-local" id="datetime" name="datetime" class="form-input">
                                </div>
                            </div>
                            
                            <div class="form-group">
                                <label for="message" class="form-label">Message</label>
                                <textarea id="message" name="message" class="form-input form-textarea" required></textarea>
                            </div>
                            
                            <button type="submit" class="form-submit">Send Message</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </section>

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
                                <path d="M 386.160156 141.550781 C 383.457031 140.15625 380.832031 138.625 378.285156 136.964844 C 370.878906 132.070312 364.085938 126.300781 358.058594 119.785156 C 342.976562 102.523438 337.339844 85.015625 335.265625 72.757812 L 335.351562 72.757812 C 333.617188 62.582031 334.332031 56 334.441406 56 L 265.742188 56 L 265.742188 321.648438 C 265.742188 325.214844 265.742188 328.742188 265.589844 332.226562 C 265.589844 332.660156 265.550781 333.058594 265.523438 333.523438 C 265.523438 333.714844 265.523438 333.917969 265.484375 334.117188 C 265.484375 334.167969 265.484375 334.214844 265.484375 334.265625 C 264.011719 353.621094 253.011719 370.976562 236.132812 380.566406 C 227.472656 385.496094 217.675781 388.078125 207.707031 388.066406 C 175.699219 388.066406 149.757812 361.964844 149.757812 329.734375 C 149.757812 297.5 175.699219 271.398438 207.707031 271.398438 C 213.765625 271.394531 219.789062 272.347656 225.550781 274.226562 L 225.632812 204.273438 C 190.277344 199.707031 154.621094 210.136719 127.300781 233.042969 C 115.457031 243.328125 105.503906 255.605469 97.882812 269.316406 C 94.984375 274.316406 84.042969 294.410156 82.714844 327.015625 C 81.882812 345.523438 87.441406 364.699219 90.089844 372.625 L 90.089844 372.792969 C 91.757812 377.457031 98.214844 393.382812 108.742188 406.808594 C 117.230469 417.578125 127.253906 427.035156 138.5 434.882812 L 138.5 434.714844 L 138.667969 434.882812 C 171.925781 457.484375 208.800781 456 208.800781 456 C 215.183594 455.742188 236.566406 456 260.851562 444.492188 C 287.785156 431.734375 303.117188 412.726562 303.117188 412.726562 C 312.914062 401.367188 320.703125 388.425781 326.148438 374.449219 C 332.367188 358.109375 334.441406 338.507812 334.441406 330.675781 L 334.441406 189.742188 C 335.273438 190.242188 346.375 197.582031 346.375 197.582031 C 346.375 197.582031 362.367188 207.832031 387.316406 214.507812 C 405.214844 219.257812 429.332031 220.257812 429.332031 220.257812 L 429.332031 152.058594 C 420.882812 152.976562 403.726562 150.308594 386.160156 141.550781 Z M 386.160156 141.550781"></path>
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
                    <h3 class="newsletter-title">Join to Stay Updated with AI Market Insights</h3>
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
                    <a href="#contact" class="footer-links">Contact</a>
                </div>
                <div class="footer-right">
                    <a href="/terms-of-service" class="footer-links">Terms of Service</a>
                </div>
            </div>
        </div>
    </footer>

    <script>
        // Matrix Canvas Background
        const canvas = document.getElementById('matrix');
        const ctx = canvas.getContext('2d');

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const letters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const fontSize = 16;
        const columns = canvas.width / fontSize;

        const drops = [];
        for (let i = 0; i < columns; i++) {
            drops[i] = Math.floor(Math.random() * canvas.height / fontSize);
        }

        function draw() {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.fillStyle = '#00ffea';
            ctx.font = fontSize + 'px Courier New';

            for (let i = 0; i < drops.length; i++) {
                const text = letters[Math.floor(Math.random() * letters.length)];
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);

                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }

                drops[i] += 0.5;
            }
        }

        setInterval(draw, 50);

        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
        
        // Mobile Menu Toggle
        const menuButton = document.getElementById('menu-button');
        const mobileMenu = document.getElementById('mobile-menu');
        const closeMenu = document.getElementById('close-menu');
        
        if (menuButton && mobileMenu) {
            menuButton.addEventListener('click', () => {
                mobileMenu.classList.add('active');
                document.body.style.overflow = 'hidden'; // Prevent body scroll when menu is open
            });
            
            if (closeMenu) {
                closeMenu.addEventListener('click', () => {
                    mobileMenu.classList.remove('active');
                    document.body.style.overflow = 'auto'; // Restore body scroll
                });
            }
            
            // Close menu when clicking on mobile nav links
            const mobileNavLinks = document.querySelectorAll('.mobile-nav-link');
            mobileNavLinks.forEach(link => {
                link.addEventListener('click', () => {
                    mobileMenu.classList.remove('active');
                    document.body.style.overflow = 'auto';
                });
            });
            
            // Close menu when clicking outside of it
            mobileMenu.addEventListener('click', (e) => {
                if (e.target === mobileMenu) {
                    mobileMenu.classList.remove('active');
                    document.body.style.overflow = 'auto';
                }
            });
        }
        
        // Cube rotation interaction
        document.addEventListener('DOMContentLoaded', function() {
            const cube = document.querySelector('.cube');
            const heroSection = document.querySelector('.hero');
            
            if (cube && heroSection) {
                let rotateX = 0;
                let rotateY = 0;
                let isAutoRotating = true;
                let autoRotateInterval;
                
                function startAutoRotate() {
                    isAutoRotating = true;
                    autoRotateInterval = setInterval(() => {
                        rotateX += 0.3;
                        rotateY += 0.3;
                        updateCubeRotation();
                    }, 50);
                }
                
                function stopAutoRotate() {
                    isAutoRotating = false;
                    clearInterval(autoRotateInterval);
                }
                
                function updateCubeRotation() {
                    cube.style.transform = 'rotateX(' + rotateX + 'deg) rotateY(' + rotateY + 'deg)';
                }
                
                heroSection.addEventListener('mousemove', function(e) {
                    if (isAutoRotating) {
                        stopAutoRotate();
                    }
                    
                    const xAxis = (window.innerWidth / 2 - e.pageX) / 25;
                    const yAxis = (window.innerHeight / 2 - e.pageY) / 25;
                    
                    rotateX = yAxis;
                    rotateY = -xAxis;
                    
                    updateCubeRotation();
                });
                
                heroSection.addEventListener('mouseleave', function() {
                    startAutoRotate();
                });
                
                startAutoRotate();
            }

            // Set minimum date to today for datetime picker
            const datetimeInput = document.getElementById('datetime');
            if (datetimeInput) {
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                datetimeInput.min = now.toISOString().slice(0, 16);
            }
        });

        // Toggle appointment fields
        function toggleAppointmentFields() {
            const checkbox = document.getElementById('appointmentToggle');
            const fields = document.getElementById('appointmentFields');
            const datetimeInput = document.getElementById('datetime');
            
            if (checkbox.checked) {
                fields.classList.add('show');
                datetimeInput.required = true;
                
                // Set minimum date to today for datetime picker
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                datetimeInput.min = now.toISOString().slice(0, 16);
            } else {
                fields.classList.remove('show');
                datetimeInput.required = false;
                datetimeInput.value = '';
            }
        }

        // Alert Functions
        function showAlert(message, type) {
            const alertContainer = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type} show`;
            alert.textContent = message;
            
            alertContainer.innerHTML = '';
            alertContainer.appendChild(alert);
            
            setTimeout(() => {
                alert.classList.remove('show');
                setTimeout(() => alertContainer.innerHTML = '', 300);
            }, 5000);
        }
        
        // Contact form submission
        function sendEmail(event) {
            event.preventDefault();
            
            const submitBtn = document.getElementById('submitBtn');
            const originalText = submitBtn.textContent;
            
            // Disable button and show loading state
            submitBtn.disabled = true;
            submitBtn.textContent = 'Sending...';
            
            // Initialize EmailJS with your public key
            emailjs.init("xSYgQUruN6qY2C0o2");
            
            // Check if appointment is requested
            const appointmentRequested = document.getElementById('appointmentToggle').checked;
            let estDateTime = 'No appointment requested';
            
            if (appointmentRequested) {
                const datetimeInput = document.getElementById('datetime').value;
                if (datetimeInput) {
                    const selectedDate = new Date(datetimeInput);
                    estDateTime = selectedDate.toLocaleString("en-US", {
                        timeZone: "America/New_York",
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                    }) + " EST";
                }
            }
            
            const params = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                message: document.getElementById('message').value,
                appointment_requested: appointmentRequested ? 'Yes' : 'No',
                preferred_datetime: estDateTime
            };
            
            // Send email
            emailjs.send("service_gf8ewl9", "template_nad2dyc", params)
                .then(() => {
                    if (appointmentRequested) {
                        showAlert("Thanks for your message and appointment request! We'll get back to you within 24 hours with a meeting invite.", 'success');
                    } else {
                        showAlert("Thanks for your message! We'll get back to you within 24 hours.", 'success');
                    }
                    document.getElementById('contactForm').reset();
                    document.getElementById('appointmentFields').classList.remove('show');
                })
                .catch((error) => {
                    console.error('Error:', error);
                    showAlert("Sorry, there was an error sending your message. Please try again.", 'error');
                })
                .finally(() => {
                    // Re-enable button
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                });
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/@emailjs/browser@3/dist/email.min.js"></script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(template)

if __name__ == '__main__':
    app.run(debug=True)