from flask import Blueprint, render_template

# Create the blueprint for about
about_bp = Blueprint('about', __name__, url_prefix='/about')

@about_bp.route('/')
def about():
    """About page"""
    return render_template('about.html')
