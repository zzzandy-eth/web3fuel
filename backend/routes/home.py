from flask import Blueprint, render_template
from .research import fetch_wordpress_posts, get_cached_data, get_cache_key
from .tools import cross_chain_tools

# Create blueprint
home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def home():
    # Fetch 10 most recent blog posts for homepage carousel
    cache_key = get_cache_key("homepage_posts", per_page=10, page=1)

    def fetch_posts():
        return fetch_wordpress_posts(per_page=10, page=1)

    blog_data = get_cached_data(cache_key, fetch_posts)
    recent_posts = blog_data.get('posts', []) if blog_data.get('success') else []

    # Get 10 most recent tools (first 10 from the list, which is in descending order)
    recent_tools = cross_chain_tools[:10]

    return render_template('index.html', recent_posts=recent_posts, recent_tools=recent_tools)
