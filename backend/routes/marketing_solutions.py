from flask import Blueprint, render_template
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

@marketing_solutions_bp.route('/')
def marketing_solutions():
    return render_template('marketing-solutions.html', success_stories=sample_success_stories)

@marketing_solutions_bp.route('/case-studies')
def case_studies():
    """Detailed case studies page"""
    return render_template('case-studies.html', success_stories=sample_success_stories)

@marketing_solutions_bp.route('/get-quote')
def get_quote():
    """Custom quote request page for marketing services"""
    return render_template('get-quote.html')