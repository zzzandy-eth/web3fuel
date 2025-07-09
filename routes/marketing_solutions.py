from flask import Blueprint, render_template_string
from datetime import datetime

# Create the blueprint for marketing solutions
marketing_solutions_bp = Blueprint('marketing_solutions', __name__, url_prefix='/marketing-solutions')

# Sample data for showcase
sample_success_stories = [
    {
        "client": "Independent Life Insurance Agent",
        "industry": "Insurance",
        "challenge": "Competing against Northwestern Mutual in local market",
        "solution": "Local SEO optimization + educational content strategy",
        "results": {
            "traffic_increase": "150%",
            "leads_increase": "240%",
            "conversion_rate": "+85%",
            "google_ranking": "Top 3 for 'life insurance [city]'"
        },
        "timeframe": "6 months",
        "featured": True
    },
    {
        "client": "Real Estate Professional",
        "industry": "Real Estate", 
        "challenge": "Low online visibility in competitive market",
        "solution": "Neighborhood authority building + property showcase optimization",
        "results": {
            "traffic_increase": "200%",
            "leads_increase": "180%",
            "conversion_rate": "+65%",
            "google_ranking": "Top 5 for neighborhood searches"
        },
        "timeframe": "4 months",
        "featured": False
    },
    {
        "client": "Financial Advisor",
        "industry": "Financial Services",
        "challenge": "Building trust with retirement planning prospects",
        "solution": "Educational content + compliance-safe lead magnets", 
        "results": {
            "traffic_increase": "120%",
            "leads_increase": "160%",
            "conversion_rate": "+45%",
            "google_ranking": "Page 1 for retirement planning"
        },
        "timeframe": "5 months",
        "featured": False
    }
]

# HTML template as a string - UPDATED TEMPLATE
template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Marketing Solutions - Web3Fuel.io</title>
    
    <!-- Add EmailJS script -->
    <script src="https://cdn.jsdelivr.net/npm/@emailjs/browser@3/dist/email.min.js"></script>
    
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
            --insurance-blue: #0066cc;
            --insurance-gold: #ffd700;
            --emerald: #10b981;
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
            max-width: 70%;
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

        /* Hero Section */
        .hero {
            position: relative;
            overflow: hidden;
            padding: 5rem 0;
            border-bottom: 1px solid var(--border-color);
            min-height: 85vh;
            display: flex;
            align-items: center;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 3rem;
        }

        .hero-grid > div:first-child {
            padding-left: 2rem;
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

        .hero-subtitle {
            color: #e2e8f0;
            font-size: 1.25rem;
            margin-bottom: 2rem;
            max-width: 32rem;
            line-height: 1.6;
        }

        .hero-buttons {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            margin: 2rem 0;
        }

        .hero-subtext {
            color: var(--text);
            font-style: italic;
            margin-top: 2rem;
            font-size: 1.2rem;
            font-weight: 500;
        }

        .hero-checkpoints {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-top: 1rem;
            font-size: 1.1rem;
            color: var(--text-muted);
        }

        .hero-checkpoint {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .hero-checkpoint .checkmark {
            color: var(--success);
            font-weight: bold;
        }

        .hero-visual {
            position: relative;
            width: 100%;
            height: 300px;
            perspective: 1000px;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .marketing-dashboard {
            width: 100%;
            max-width: 600px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.1);
            position: relative;
            overflow: hidden;
        }

        .marketing-dashboard::before {
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
            animation: pulse-green 2s infinite;
        }

        .dashboard-metrics {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
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

        .metric-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .metric-label-text {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-muted);
        }

        .metric-value-text {
            font-size: 0.875rem;
            font-weight: 700;
            color: var(--primary);
        }

        .metric-bar {
            width: 100%;
            height: 0.75rem;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 0.375rem;
            overflow: hidden;
        }

        .metric-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            border-radius: 0.375rem;
            transition: width 0.8s ease;
        }

        .metric-item {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }

        @keyframes pulse-green {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.6;
            }
        }

        /* CTA Button Styles */
        .cta-button {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 2rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            color: black;
            text-decoration: none;
            border-radius: 0.5rem;
            font-weight: 600;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            font-size: 1rem;
        }

        .cta-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 255, 234, 0.3);
        }

        .cta-button.secondary {
            background: linear-gradient(135deg, rgba(0, 255, 234, 0.1), rgba(255, 0, 255, 0.1));
            color: var(--text);
            border: 2px solid transparent;
            background-clip: padding-box;
            position: relative;
            overflow: hidden;
            padding-right: 3.5rem;
        }

        .cta-button.secondary::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 0.5rem;
            padding: 2px;
            mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            mask-composite: subtract;
            -webkit-mask-composite: destination-out;
            z-index: -1;
        }

        .cta-button.secondary::after {
            content: '🤖';
            position: absolute;
            right: 0.75rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1.2rem;
            animation: bounce 2s infinite;
        }

        .cta-button.secondary:hover {
            border-color: var(--primary);
            background: linear-gradient(135deg, rgba(0, 255, 234, 0.2), rgba(255, 0, 255, 0.2));
            color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.3);
            transform: translateY(-3px) scale(1.02);
        }

        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% {
                transform: translateY(-50%);
            }
            40% {
                transform: translateY(-60%);
            }
            60% {
                transform: translateY(-55%);
            }
        }

        /* Demo Popup Styles */
        .demo-popup {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }

        .demo-popup.show {
            display: flex;
        }

        .demo-content {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
            margin: 1rem;
            box-shadow: 0 0 50px rgba(0, 255, 234, 0.2);
        }

        .demo-close {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: none;
            border: none;
            color: var(--text);
            font-size: 1.5rem;
            cursor: pointer;
            width: 2rem;
            height: 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: all 0.3s ease;
        }

        .demo-close:hover {
            background: var(--primary);
            color: black;
        }

        .demo-title {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 2rem;
            text-align: center;
        }

        .demo-visual-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }

        .demo-card {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
        }

        .demo-card:hover {
            border-color: var(--primary);
            box-shadow: 0 0 20px rgba(0, 255, 234, 0.2);
        }

        .demo-icon {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            display: block;
        }

        .demo-card h3 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 0.75rem;
        }

        .demo-card p {
            color: var(--text-muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }

        .demo-highlight {
            background: rgba(0, 255, 234, 0.1);
            border: 1px solid rgba(0, 255, 234, 0.3);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin: 2rem 0;
            text-align: center;
        }

        .demo-highlight h4 {
            color: var(--primary);
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }

        .demo-highlight p {
            color: var(--text);
            font-size: 1rem;
            line-height: 1.6;
        }

        .demo-comparison {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin: 2rem 0;
        }

        .comparison-item {
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
        }

        .comparison-old {
            background: rgba(255, 0, 0, 0.1);
            border: 1px solid rgba(255, 0, 0, 0.3);
        }

        .comparison-new {
            background: rgba(0, 255, 0, 0.1);
            border: 1px solid rgba(0, 255, 0, 0.3);
        }

        .comparison-item h5 {
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .comparison-old h5 {
            color: #ff6b6b;
        }

        .comparison-new h5 {
            color: #51cf66;
        }

        /* Who We Help Section */
        .who-we-help-section {
            padding: 4rem 0;
            border-bottom: 1px solid var(--border-color);
        }

        .who-we-help-header {
            text-align: center;
            margin-bottom: 3rem;
        }

        .who-we-help-title {
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 1rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .who-we-help-subtitle {
            color: var(--text);
            font-size: 1.25rem;
            max-width: 50rem;
            margin: 2rem auto 0 auto;
            line-height: 1.6;
            text-align: center;
        }

        .why-ai-content {
            max-width: 50rem;
            margin: 0 auto;
            text-align: center;
        }

        .why-ai-intro {
            font-size: 1.25rem;
            color: var(--text);
            margin-bottom: 2rem;
        }

        .challenges-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.5rem;
            margin: 2rem 0;
            max-width: 60rem;
            margin-left: auto;
            margin-right: auto;
        }

        .challenge-item {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1.5rem;
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.15), rgba(0, 255, 234, 0.1));
            border: 2px solid rgba(124, 58, 237, 0.4);
            border-radius: 1rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(124, 58, 237, 0.15);
        }

        .challenge-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 234, 0.15), transparent);
            transition: left 0.6s ease;
        }

        .challenge-item:hover::before {
            left: 100%;
        }

        .challenge-item:hover {
            border-color: var(--primary);
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 255, 234, 0.25);
        }

        .challenge-icon {
            font-size: 2rem;
            flex-shrink: 0;
            filter: drop-shadow(0 0 5px rgba(0, 255, 234, 0.5));
        }

        .challenge-text {
            color: var(--text);
            font-weight: 600;
            font-size: 1.1rem;
        }

        .why-ai-solution {
            font-size: 1.25rem;
            color: var(--text);
            margin: 2rem 0;
            line-height: 1.6;
        }

        .professionals-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
            margin: 3rem auto;
            max-width: 60rem;
        }

        .professional-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .professional-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }

        .professional-card:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.2);
        }

        .professional-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            filter: drop-shadow(0 0 10px currentColor);
        }

        .professional-card h3 {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.5rem;
        }

        .closing-statement {
            text-align: center;
            margin-top: 3rem;
            max-width: 50rem;
            margin-left: auto;
            margin-right: auto;
        }

        .closing-text {
            font-size: 1.25rem;
            color: var(--text);
            font-weight: 600;
            line-height: 1.6;
            font-style: italic;
        }

        /* Solutions Section */
        .solutions-section {
            padding: 4rem 0;
            border-bottom: 1px solid var(--border-color);
        }

        .solutions-header {
            text-align: center;
            margin-bottom: 3rem;
        }

        .solutions-title {
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 1rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .solutions-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
            margin-top: 3rem;
        }

        .solution-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .solution-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }

        .solution-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.2);
            border-color: var(--primary);
        }

        .solution-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .solution-icon {
            width: 3rem;
            height: 3rem;
            background: rgba(0, 255, 234, 0.1);
            border-radius: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: var(--primary);
            border: 1px solid rgba(0, 255, 234, 0.3);
        }

        .solution-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
        }

        .solution-description {
            color: var(--text-muted);
            margin-bottom: 1.5rem;
            font-size: 1.15rem;
            line-height: 1.6;
        }

        .solution-features {
            list-style: none;
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }

        .solution-features li {
            display: flex;
            align-items: center;
            padding: 0.5rem;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            transition: all 0.3s ease;
        }

        .solution-features li:hover {
            border-color: var(--primary);
            background: rgba(0, 255, 234, 0.05);
        }

        .solution-features li::before {
            content: '✓';
            color: var(--success);
            font-weight: bold;
            margin-right: 0.75rem;
            font-size: 1.1rem;
            width: 1.5rem;
            text-align: center;
        }

        /* What Makes Us Different + How It Works Combined Section */
        .different-works-section {
            padding: 4rem 0;
            border-bottom: 1px solid var(--border-color);
        }

        .different-works-header {
            text-align: center;
            margin-bottom: 3rem;
        }

        .different-works-title {
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 1rem;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .different-works-content {
            max-width: 60rem;
            margin: 0 auto;
            text-align: center;
            margin-bottom: 3rem;
        }

        .different-intro {
            margin-bottom: 2rem;
        }

        .different-problems {
            display: flex;
            align-items: center;
            gap: 2rem;
            margin-bottom: 2rem;
            max-width: 50rem;
            margin-left: auto;
            margin-right: auto;
            justify-content: center;
        }

        .different-problem {
            font-size: 1.25rem;
            color: var(--text);
            font-weight: 600;
            line-height: 1.4;
            text-align: center;
        }

        .problem-separator {
            color: var(--primary);
            font-size: 1.5rem;
            font-weight: bold;
        }

        .different-solution-card {
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.15), rgba(0, 255, 234, 0.1));
            border: 2px solid rgba(124, 58, 237, 0.4);
            border-radius: 1rem;
            padding: 2rem;
            margin: 2rem 0;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(124, 58, 237, 0.15);
        }

        .different-solution-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 234, 0.15), transparent);
            transition: left 0.6s ease;
        }

        .different-solution-card:hover::before {
            left: 100%;
        }

        .different-solution-card:hover {
            border-color: var(--primary);
            box-shadow: 0 8px 25px rgba(0, 255, 234, 0.25);
        }

        .different-solution {
            font-size: 1.2rem;
            color: var(--text);
            line-height: 1.6;
            margin: 0;
        }

        .different-benefits {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            margin: 2rem auto;
            max-width: 50rem;
        }

        .benefit-item {
            display: flex;
            align-items: flex-start;
            gap: 1rem;
        }

        .benefit-icon {
            width: 3rem;
            height: 3rem;
            background: rgba(0, 255, 234, 0.1);
            border-radius: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: var(--primary);
            flex-shrink: 0;
            border: 1px solid rgba(0, 255, 234, 0.3);
        }

        .benefit-content h3 {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.5rem;
        }

        .benefit-content p {
            color: var(--text-muted);
            line-height: 1.6;
            font-size: 1.1rem;
        }

        .process-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
            margin-top: 3rem;
            max-width: 50rem;
            margin-left: auto;
            margin-right: auto;
        }

        .process-step {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: visible;
            z-index: 10;
        }

        .process-step:hover {
            border-color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.2);
        }

        .step-header {
            display: flex;
            justify-content: center;
            margin-bottom: 1.5rem;
        }

        .step-number {
            background: linear-gradient(135deg, rgba(0, 255, 234, 0.2), rgba(255, 0, 255, 0.1));
            color: var(--primary);
            font-weight: bold;
            font-size: 1.5rem;
            padding: 1rem 1.5rem;
            border-radius: 50%;
            border: 2px solid rgba(0, 255, 234, 0.3);
            width: 4rem;
            height: 4rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .step-arrow {
            position: absolute;
            bottom: 0.5rem;
            right: 1rem;
            color: var(--primary);
            font-size: 3rem;
            z-index: 15;
            text-shadow: 0 0 10px var(--primary);
            opacity: 0;
            transform: translateX(-10px);
            transition: all 0.3s ease;
            pointer-events: none;
        }

        .process-step:hover .step-arrow {
            opacity: 1;
            transform: translateX(0);
        }

        .process-step:last-child .step-arrow {
            display: none;
        }

        .step-content {
            text-align: center;
        }

        .process-section {
            border-top: 2px solid var(--border-color);
            padding: 3rem 0 0 0;
            margin-top: 3rem;
            position: relative;
        }

        .process-section::before {
            content: '';
            position: absolute;
            top: -1px;
            left: 50%;
            transform: translateX(-50%);
            width: 100px;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }

        .process-section-title {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text);
            text-align: center;
            margin-bottom: 3rem;
        }

        .process-connection-line {
            position: absolute;
            top: 3rem;
            left: 100%;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            transform: translateX(1rem);
            z-index: 0;
        }

        .step-icon {
            width: 4rem;
            height: 4rem;
            background: rgba(0, 255, 234, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: var(--primary);
            margin: 0 auto 1rem auto;
            border: 1px solid rgba(0, 255, 234, 0.3);
        }

        .process-step::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0.5rem;
            right: 0.5rem;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            border-radius: 1rem 1rem 0 0;
        }

        .process-step:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
            box-shadow: 0 0 30px rgba(0, 255, 234, 0.2);
        }

        .step-content h3 {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.5rem;
        }

        .step-content p {
            color: var(--text-muted);
            line-height: 1.6;
        }

        /* CTA Section */
        .cta {
            padding: 4rem 0;
        }

        .cta-container {
            background: linear-gradient(to right, rgba(0, 0, 0, 0.8), rgba(20, 20, 30, 0.9)), url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="none"/><path d="M0,0 L100,100 M0,100 L100,0" stroke="rgba(124, 58, 237, 0.1)" stroke-width="1"/></svg>');
            border-radius: 1rem;
            padding: 3rem 2rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 0 30px rgba(124, 58, 237, 0.2);
            max-width: 75%;
            margin: 0 auto;
        }

        .cta-content {
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }

        .cta-text {
            text-align: left;
        }

        .cta-title {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 2rem;
            color: var(--primary);
        }

        .cta-description {
            color: #e2e8f0;
            margin-bottom: 1rem;
            line-height: 1.6;
            font-size: 1.1rem;
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
            font-size: 1.05rem;
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

        /* Date/time picker styling */
        input[type="datetime-local"] {
            cursor: pointer;
            position: relative;
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

        input[type="datetime-local"] {
            color: #a1a1aa; 
        }

        input[type="datetime-local"]:focus {
            color: white;
        }

        input[type="datetime-local"]:valid {
            color: white;
        }

        /* Animations */
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
        @media (min-width: 640px) {
            .solutions-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .challenges-grid {
                grid-template-columns: repeat(3, 1fr);
            }

            .professionals-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .newsletter-form {
                flex-direction: row;
            }
            
            .newsletter-input {
                flex: 1;
            }

            .hero-buttons {
                flex-direction: row;
                justify-content: flex-start;
            }

            .demo-visual-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .demo-comparison {
                grid-template-columns: 1fr 1fr;
            }
        }

        @media (min-width: 768px) {
            .cta-content {
                grid-template-columns: 1fr 1fr;
                align-items: center;
            }
        }

        @media (min-width: 768px) {
            .nav-desktop {
                display: flex;
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
            
            .solutions-grid {
                grid-template-columns: repeat(3, 1fr);
            }
            
            .professionals-grid {
                grid-template-columns: repeat(4, 1fr);
            }

            .process-grid {
                grid-template-columns: repeat(3, 1fr);
            }

            .footer-main {
                flex-direction: row;
                align-items: flex-start;
            }
            
            .footer-bottom {
                justify-content: space-between;
            }

            .demo-visual-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        @media (min-width: 1024px) {
            .professionals-grid {
                grid-template-columns: repeat(4, 1fr);
            }

            .solutions-grid {
                grid-template-columns: repeat(3, 1fr);
            }

            .header-container {
                    padding: 0 3rem;
                }
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

            .step-content h3 {
                font-size: 1.25rem;
            }

            .demo-visual-grid {
                grid-template-columns: 1fr;
            }

            .demo-comparison {
                grid-template-columns: 1fr;
            }
        }

        @media (min-width: 1920px) {
            .container {
                max-width: 1600px;
            }
        }

        @media (max-width: 767px) {
            .process-connection-line {
                display: none;
            }
            
            .different-problems {
                grid-template-columns: 1fr;
                gap: 1rem;
            }
            
            .different-problem {
                text-align: center;
            }
        }

        @media (max-width: 767px) {          
            .different-problems {
                flex-direction: column;
                gap: 1rem;
            }
            
            .problem-separator {
                display: none;
            }
        }

        @media (min-width: 1200px) {
        .nav-desktop {
                gap: 0.75rem; /* More gap between nav items on large screens */
            }
        }
    </style>
</head>
<body>
    <canvas id="matrix"></canvas>
    
    <!-- Demo Popup -->
    <div class="demo-popup" id="demoPopup">
        <div class="demo-content">
            <button class="demo-close" onclick="hideDemo()">&times;</button>
            <h3 class="demo-title">How AI Marketing Works</h3>
            
            <div class="demo-visual-grid">
                <div class="demo-card">
                    <div class="demo-icon">🧠</div>
                    <h3>Pattern Recognition</h3>
                    <p>AI analyzes visitor behavior patterns to predict conversion probability</p>
                </div>
                <div class="demo-card">
                    <div class="demo-icon">🎯</div>
                    <h3>Smart Targeting</h3>
                    <p>Machine learning identifies your highest-value prospects automatically</p>
                </div>
                <div class="demo-card">
                    <div class="demo-icon">⚡</div>
                    <h3>Real-Time Optimization</h3>
                    <p>Campaigns adjust messaging based on live performance data</p>
                </div>
            </div>

            <div class="demo-highlight">
                <h4>Financial AI → Marketing AI</h4>
                <p>The same algorithms that predict market movements can forecast which leads will buy from you. It's pattern recognition applied to human behavior instead of price charts.</p>
            </div>

            <div class="demo-comparison">
                <div class="comparison-item comparison-old">
                    <h5>Traditional Marketing</h5>
                    <p>• Spray and pray approach<br>• Manual A/B testing<br>• Gut feeling decisions<br>• Reactive adjustments</p>
                </div>
                <div class="comparison-item comparison-new">
                    <h5>AI-Powered Marketing</h5>
                    <p>• Precision targeting<br>• Automated optimization<br>• Data-driven insights<br>• Predictive adjustments</p>
                </div>
            </div>

            <div class="demo-highlight">
                <h4>Real Example</h4>
                <p>When someone visits your life insurance page but doesn't convert, traditional marketing sends generic follow-ups. AI marketing analyzes their behavior, compares it to 1000s of similar visitors, and sends personalized content proven to convert that specific visitor type.</p>
            </div>
        </div>
    </div>
    
    <!-- Header -->
    <header>
        <div class="header-container">
            <a href="/" class="logo">
                <span class="logo-icon">🚀</span>
                <span class="logo-text">Web3Fuel.io</span>
            </a>
            
            <nav class="nav-desktop">
                <a href="/trading-suite" class="nav-link">Trading Suite</a>
                <a href="/marketing-solutions" class="nav-link active">Marketing Solutions</a>
                <a href="/blog" class="nav-link">Blog</a>
                <a href="/contact" class="nav-link contact-highlight">Contact</a>
            </nav>
            
            <button class="menu-button" id="menu-button">☰</button>
        </div>
    </header>
    
    <!-- Hero Section -->
    <section class="hero">
        <div class="container">
            <div class="hero-grid">
                <div>
                    <h1>Transform Your Marketing with <span class="hero-accent">AI-Powered</span> Intelligence</h1>
                    <p class="hero-subtitle">Leverage AI models — originally built to forecast financial trends — to power smarter, faster marketing for insurance agents and financial professionals.</p>

                    <div class="hero-buttons">
                        <button class="cta-button" onclick="document.querySelector('.cta').scrollIntoView({behavior: 'smooth'})">
                            Book a Free Strategy Call
                        </button>
                        <button class="cta-button secondary" onclick="showDemo()">
                            AI Enhanced VS Traditional Marketing
                        </button>
                    </div>

                    <div class="hero-checkpoints">
                        <div class="hero-checkpoint">
                            <span class="checkmark">✔️</span>
                            <span>Flexible Plans</span>
                        </div>
                        <div class="hero-checkpoint">
                            <span class="checkmark">✔️</span>
                            <span>Cancel Anytime</span>
                        </div>
                        <div class="hero-checkpoint">
                            <span class="checkmark">✔️</span>
                            <span>Built for Insurance & Finance</span>
                        </div>
                    </div>

                    <p class="hero-subtext">Built by someone who's worked inside the insurance world <br>— and understands how real agents win and lose clients.</p>
                </div>
                
                <div class="hero-visual">
                    <div class="marketing-dashboard">
                        <div class="dashboard-header">
                            <div class="dash-title">Campaign Performance</div>
                            <div class="dash-status">🟢 Active</div>
                        </div>
                        <div class="dashboard-metrics">
                            <div class="metric-item">
                                <div class="metric-header">
                                    <span class="metric-label-text">Lead Generation</span>
                                    <span class="metric-value-text">+247%</span>
                                </div>
                                <div class="metric-bar">
                                    <div class="metric-fill" style="width: 80%"></div>
                                </div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-header">
                                    <span class="metric-label-text">Conversion Rate</span>
                                    <span class="metric-value-text">+189%</span>
                                </div>
                                <div class="metric-bar">
                                    <div class="metric-fill" style="width: 75%"></div>
                                </div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-header">
                                    <span class="metric-label-text">ROI Improvement</span>
                                    <span class="metric-value-text">+312%</span>
                                </div>
                                <div class="metric-bar">
                                    <div class="metric-fill" style="width: 100%"></div>
                                </div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-header">
                                    <span class="metric-label-text">Quote Completion</span>
                                    <span class="metric-value-text">70%</span>
                                </div>
                                <div class="metric-bar">
                                    <div class="metric-fill" style="width: 65%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <!-- Who We Help — and Why Our Approach Works Section -->
    <section class="who-we-help-section">
        <div class="container">
            <div class="who-we-help-header">
                <h2 class="who-we-help-title">Built for Financial Professionals Who Value Trust</h2>
            </div>
            
            <div class="why-ai-content">
                <p class="who-we-help-subtitle">We specialize in client-first marketing systems designed for professionals who operate in regulated, trust-based industries, including:</p>
            </div>
            
            <div class="professionals-grid">
                <div class="professional-card">
                    <div class="professional-icon">🛡️</div>
                    <h3>Insurance Agents</h3>
                </div>
                <div class="professional-card">
                    <div class="professional-icon">⚖️</div>
                    <h3>Risk Consultants</h3>
                </div>
                <div class="professional-card">
                    <div class="professional-icon">🏠</div>
                    <h3>Mortgage & Finance Brokers</h3>
                </div>
                <div class="professional-card">
                    <div class="professional-icon">💰</div>
                    <h3>Financial Planners & Advisors</h3>
                </div>
            </div>
            
            <div class="why-ai-content">
                <p class="why-ai-intro">As someone with years of experience supporting insurance professionals and business owners, we understand the daily challenges you face:</p>
                
                <div class="challenges-grid">
                    <div class="challenge-item">
                        <div class="challenge-icon">😤</div>
                        <div class="challenge-text">Endless follow-ups that <br>go nowhere</div>
                    </div>
                    <div class="challenge-item">
                        <div class="challenge-icon">📉</div>
                        <div class="challenge-text">Unpredictable or low-quality <br>lead sources</div>
                    </div>
                    <div class="challenge-item">
                        <div class="challenge-icon">👻</div>
                        <div class="challenge-text">Prospects ghosting after quote requests</div>
                    </div>
                </div>
                
                <p class="why-ai-solution">That's why we've retooled AI algorithms originally built to forecast financial markets — adapting them to solve the exact sales and marketing struggles financial professionals deal with every day.</p>
            </div>
            
            <div class="closing-statement">
                <p class="closing-text">We don't just know marketing. We've worked inside the industry — and we build systems that respect compliance, elevate trust, and drive results.</p>
            </div>
        </div>
    </section>

    <!-- AI-Powered Services Section -->
    <section class="solutions-section">
        <div class="container">
            <div class="solutions-header">
                <h2 class="solutions-title">AI Marketing Solutions That Drive Results</h2>
            </div>
            
            <div class="solutions-grid">
                <!-- Predictive Lead Scoring -->
                <div class="solution-card">
                    <div class="solution-header">
                        <div class="solution-icon">🎯</div>
                        <h3 class="solution-title">Predictive Lead Scoring</h3>
                    </div>
                    <p class="solution-description">Know which leads are most likely to convert — before you ever call them.</p>
                    <ul class="solution-features">
                        <li>Behavioral analysis patterns</li>
                        <li>Conversion probability scoring</li>
                        <li>Priority lead ranking</li>
                        <li>Real-time lead intelligence</li>
                    </ul>
                </div>
                
                <!-- AI Retargeting Ads -->
                <div class="solution-card">
                    <div class="solution-header">
                        <div class="solution-icon">🎪</div>
                        <h3 class="solution-title">AI Retargeting Ads</h3>
                    </div>
                    <p class="solution-description">Deliver personalized ads based on user behavior (e.g., viewed your "Life Insurance" page).</p>
                    <ul class="solution-features">
                        <li>Dynamic ad personalization</li>
                        <li>Behavioral trigger campaigns</li>
                        <li>Cross-platform retargeting</li>
                        <li>Smart budget optimization</li>
                    </ul>
                </div>
                
                <!-- Smart Chatbot Funnels -->
                <div class="solution-card">
                    <div class="solution-header">
                        <div class="solution-icon">🤖</div>
                        <h3 class="solution-title">Smart Chatbot Funnels</h3>
                    </div>
                    <p class="solution-description">Qualify leads, book appointments, and answer FAQs 24/7 — even while you sleep.</p>
                    <ul class="solution-features">
                        <li>24/7 lead qualification</li>
                        <li>Automated appointment booking</li>
                        <li>FAQ automation</li>
                        <li>Lead nurturing sequences</li>
                    </ul>
                </div>
                
                <!-- Client Welcome Systems -->
                <div class="solution-card">
                    <div class="solution-header">
                        <div class="solution-icon">👋</div>
                        <h3 class="solution-title">Client Welcome Systems</h3>
                    </div>
                    <p class="solution-description">Build instant trust with automated onboarding emails, videos, and scheduling links.</p>
                    <ul class="solution-features">
                        <li>Automated welcome sequences</li>
                        <li>Video onboarding</li>
                        <li>Trust-building content</li>
                        <li>Seamless scheduling</li>
                    </ul>
                </div>
                
                <!-- Compliance-Friendly Content -->
                <div class="solution-card">
                    <div class="solution-header">
                        <div class="solution-icon">📋</div>
                        <h3 class="solution-title">Compliance-Friendly Content</h3>
                    </div>
                    <p class="solution-description">Pre-vetted content that educates and converts — without regulatory headaches.</p>
                    <ul class="solution-features">
                        <li>Pre-approved content library</li>
                        <li>Regulatory compliance checks</li>
                        <li>Educational materials</li>
                        <li>Converting copy templates</li>
                    </ul>
                </div>
                
                <!-- Local Competitor Intelligence -->
                <div class="solution-card">
                    <div class="solution-header">
                        <div class="solution-icon">🔍</div>
                        <h3 class="solution-title">Local Competitor Ad Intelligence</h3>
                    </div>
                    <p class="solution-description">We reverse-engineer what nearby agencies are doing — and help you outperform them.</p>
                    <ul class="solution-features">
                        <li>Competitor ad analysis</li>
                        <li>Market positioning insights</li>
                        <li>Performance benchmarking</li>
                        <li>Strategic advantage planning</li>
                    </ul>
                </div>
            </div>
        </div>
    </section>
    
    <!-- What Makes Us Different + How It Works Combined Section -->
    <section class="different-works-section">
        <div class="container">
            <div class="different-works-header">
                <h2 class="different-works-title">Built by Industry Insiders, Powered by AI</h2>
            </div>
            
            <div class="different-works-content">
                <div class="different-problems">
                    <p class="different-problem">Most marketers don't understand <br> policy compliances & trust.</p>
                    <span class="problem-separator">|</span>
                    <p class="different-problem">Most agents don't have time to <br>test what strategies actually work.</p>
                </div>
                
                <div class="different-solution-card">
                    <p class="different-solution">We've worked in your world — supporting claims, servicing clients, and navigating compliance hurdles. <br>Now we use that insider knowledge to build automated systems that do the heavy lifting for you.</p>
                </div>
            </div>
            
            <div class="different-benefits">
                <div class="benefit-item">
                    <div class="benefit-icon">🛡️</div>
                    <div class="benefit-content">
                        <h3>AI tools tailored for regulated industries</h3>
                        <p>Built specifically for compliance-heavy environments with industry-specific safeguards and features.</p>
                    </div>
                </div>
                
                <div class="benefit-item">
                    <div class="benefit-icon">⚙️</div>
                    <div class="benefit-content">
                        <h3>Strategies designed around real agent workflows</h3>
                        <p>Systems that integrate seamlessly with how you actually work, not how marketers think you work.</p>
                    </div>
                </div>
                
                <div class="benefit-item">
                    <div class="benefit-icon">🚀</div>
                    <div class="benefit-content">
                        <h3>Built-in trust, automation, and performance</h3>
                        <p>Every system prioritizes building client trust while automating repetitive tasks and tracking real results.</p>
                    </div>
                </div>
            </div>
            
            <div class="process-section">
                <h3 class="process-section-title">Our Process</h3>
                
                <div class="process-grid">
                    <div class="process-step">
                        <div class="step-arrow">→</div>
                        <div class="step-header">
                            <div class="step-number">01</div>
                        </div>
                        <div class="step-content">
                            <h3>Discovery Call</h3>
                            <p>We learn your ideal client profile, current lead sources, and business goals.</p>
                        </div>
                    </div>
                    
                    <div class="process-step">
                        <div class="step-arrow">→</div>
                        <div class="step-header">
                            <div class="step-number">02</div>
                        </div>
                        <div class="step-content">
                            <h3>AI Strategy Build</h3>
                            <p>We develop ads, landing pages, and automations tailored to your business.</p>
                        </div>
                    </div>
                    
                    <div class="process-step">
                        <div class="step-header">
                            <div class="step-number">03</div>
                        </div>
                        <div class="step-content">
                            <h3>Launch & Optimize</h3>
                            <p>Campaigns run, leads come in, and we refine performance week after week.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <!-- CTA Section -->
    <section class="cta">
        <div class="container">
            <div class="cta-container">
                <div class="cta-content">
                    <div class="cta-text">
                        <h2 class="cta-title">Ready to attract more qualified leads — without chasing them?</h2>
                        <p class="cta-description">Schedule a free strategy call to discover how AI-powered marketing can transform your insurance business. We'll analyze your current approach and show you exactly how to get better results.</p>
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
                            
                            <div class="form-group">
                                <label for="datetime" class="form-label">Select a Date & Time (EST)</label>
                                <input type="datetime-local" id="datetime" name="datetime" class="form-input" required>
                            </div>

                            <div class="form-group">
                                <label for="message" class="form-label">Message</label>
                                <textarea id="message" name="message" class="form-input form-textarea" placeholder="Please include: Company name, website, and specific marketing goals." required></textarea>
                            </div>
                            
                            <button type="submit" class="form-submit">Submit</button>
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
                    <h3 class="newsletter-title">Marketing Tips & Industry Insights</h3>
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

    <script>
        // Matrix Canvas Background
        const canvas = document.getElementById('matrix');
        const ctx = canvas.getContext('2d');

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const letters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ$%+-=';
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
        
        if (menuButton) {
            menuButton.addEventListener('click', () => {
                console.log('Mobile menu clicked');
            });
        }
        
        // Demo popup functionality
        function showDemo() {
            document.getElementById('demoPopup').classList.add('show');
            document.body.style.overflow = 'hidden';
        }
        
        function hideDemo() {
            document.getElementById('demoPopup').classList.remove('show');
            document.body.style.overflow = 'auto';
        }
        
        // Close demo when clicking outside
        document.getElementById('demoPopup').addEventListener('click', function(e) {
            if (e.target === this) {
                hideDemo();
            }
        });
        
        // Close demo with Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                hideDemo();
            }
        });
        
        // Contact form submission
        function sendEmail(event) {
            event.preventDefault();
            
            // Initialize EmailJS with your public key
            emailjs.init("xSYgQUruN6qY2C0o2");
            
            // Convert datetime to EST and format it nicely
            const datetimeInput = document.getElementById('datetime').value;
            const selectedDate = new Date(datetimeInput);
            const estDateTime = selectedDate.toLocaleString("en-US", {
                timeZone: "America/New_York",
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            }) + " EST";
            
            const params = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                preferred_datetime: estDateTime,
                message: document.getElementById('message').value
            };
            
            // Send email
            emailjs.send("service_gf8ewl9", "template_nad2dyc", params)
                .then(() => {
                    alert("Thanks for booking your strategy call! We will email you a Google meeting link invite within 24 hours.");
                    document.getElementById('contactForm').reset();
                })
                .catch((error) => {
                    console.error('Error:', error);
                    alert("Sorry, there was an error submitting your request. Please try again or reach out directly via LinkedIn.");
                });
        }

        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });

        // Add subtle animations to cards on load
        document.addEventListener('DOMContentLoaded', function() {
            const cards = document.querySelectorAll('.solution-card, .professional-card, .process-step');
            cards.forEach((card, index) => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    card.style.transition = 'all 0.6s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, index * 100);
            });

            // Set minimum date to today for datetime picker
            const datetimeInput = document.getElementById('datetime');
            if (datetimeInput) {
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset()); // Convert to local timezone
                datetimeInput.min = now.toISOString().slice(0, 16);
            }
        });

        // Interactive hover effects for metric cards
        document.querySelectorAll('.metric').forEach(metric => {
            metric.addEventListener('mouseenter', function() {
                this.style.transform = 'scale(1.05)';
                this.style.borderColor = 'var(--primary)';
            });
            
            metric.addEventListener('mouseleave', function() {
                this.style.transform = 'scale(1)';
                this.style.borderColor = 'var(--border-color)';
            });
        });

        // Animate progress bars on scroll
        const observerOptions = {
            threshold: 0.5,
            rootMargin: '0px 0px -100px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const progressBars = entry.target.querySelectorAll('.metric-fill');
                    progressBars.forEach(bar => {
                        const width = bar.style.width;
                        bar.style.width = '0%';
                        setTimeout(() => {
                            bar.style.width = width;
                        }, 100);
                    });
                }
            });
        }, observerOptions);

        // Observe the marketing dashboard
        const dashboardSection = document.querySelector('.marketing-dashboard');
        if (dashboardSection) {
            observer.observe(dashboardSection);
        }
    </script>
</body>
</html>
'''

@marketing_solutions_bp.route('/')
def marketing_solutions():
    return render_template_string(template)

@marketing_solutions_bp.route('/case-studies')
def case_studies():
    """Detailed case studies page"""
    return render_template_string("<h1>Case Studies Coming Soon</h1>")

@marketing_solutions_bp.route('/get-quote')
def get_quote():
    """Custom quote request page for marketing services"""
    return render_template_string("<h1>Quote Request Coming Soon</h1>")