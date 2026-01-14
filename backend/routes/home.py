from flask import Blueprint, render_template
from .blog import fetch_wordpress_posts, get_cached_data, get_cache_key
from .tools import cross_chain_tools

# Create blueprint
home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def home():
    # Fetch 3 most recent blog posts for homepage
    cache_key = get_cache_key("homepage_posts", per_page=3, page=1)

    def fetch_posts():
        return fetch_wordpress_posts(per_page=3, page=1)

    blog_data = get_cached_data(cache_key, fetch_posts)
    recent_posts = blog_data.get('posts', []) if blog_data.get('success') else []

    # Get 3 most recent tools (first 3 from the list, which is in descending order)
    recent_tools = cross_chain_tools[:3]

    return render_template('index.html', recent_posts=recent_posts, recent_tools=recent_tools)
