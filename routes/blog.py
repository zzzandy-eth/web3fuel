from flask import Blueprint, render_template_string, jsonify, request, Response, abort
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time
import json
import html
import re
from urllib.parse import quote_plus
from functools import wraps
import hashlib

# Try to import Redis for caching
try:
    import redis
    REDIS_AVAILABLE = True
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
except ImportError:
    REDIS_AVAILABLE = False
    print("Redis not available - using in-memory cache")

# Create a Blueprint for blog page
blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

# WordPress API configuration
WORDPRESS_API_BASE = "https://web3fuel.io/blockchain/blog/wp-json/wp/v2"
WORDPRESS_SITE_URL = "https://web3fuel.io/blockchain/blog"
CACHE_TIMEOUT = 300  # 5 minutes

# In-memory cache fallback
memory_cache = {}

def get_cache_key(prefix, **kwargs):
    """Generate cache key from parameters"""
    key_parts = [prefix]
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")
    return ":".join(key_parts)

def get_cached_data(cache_key, fetch_function, cache_time=CACHE_TIMEOUT):
    """
    Get cached data with fallback to memory cache
    """
    try:
        if REDIS_AVAILABLE:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        else:
            # Use memory cache
            if cache_key in memory_cache:
                cached_data, timestamp = memory_cache[cache_key]
                if time.time() - timestamp < cache_time:
                    return cached_data
        
        # Fetch fresh data
        data = fetch_function()
        
        # Store in cache
        if REDIS_AVAILABLE:
            redis_client.setex(cache_key, cache_time, json.dumps(data))
        else:
            memory_cache[cache_key] = (data, time.time())
        
        return data
    
    except Exception as e:
        print(f"Cache error: {e}")
        return fetch_function()

def rate_limit(max_requests=60, window=60):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            client_ip = request.remote_addr
            key = f"rate_limit:{client_ip}:{f.__name__}"
            
            try:
                if REDIS_AVAILABLE:
                    current = redis_client.get(key)
                    if current is None:
                        redis_client.setex(key, window, 1)
                    else:
                        current = int(current)
                        if current >= max_requests:
                            abort(429)  # Too Many Requests
                        redis_client.incr(key)
                
                return f(*args, **kwargs)
            except Exception as e:
                print(f"Rate limiting error: {e}")
                return f(*args, **kwargs)
        
        return wrapper
    return decorator

def fetch_wordpress_posts(per_page=6, page=1, search=None, category=None):
    """
    Fetch blog posts from WordPress REST API with enhanced error handling
    """
    try:
        # Prepare parameters
        params = {
            'per_page': min(per_page, 20),  # Limit to prevent abuse
            'page': page,
            '_embed': 'wp:featuredmedia,author,wp:term',
            'status': 'publish',
            'orderby': 'date',
            'order': 'desc'
        }
        
        if search:
            params['search'] = search[:100]  # Limit search query length
        
        if category:
            # Fetch category ID first
            cat_response = requests.get(
                f"{WORDPRESS_API_BASE}/categories",
                params={'slug': category},
                timeout=10
            )
            if cat_response.status_code == 200:
                categories = cat_response.json()
                if categories:
                    params['categories'] = categories[0]['id']
        
        # Make the request with SSL verification
        response = requests.get(
            f"{WORDPRESS_API_BASE}/posts",
            params=params,
            timeout=15,
            verify=True,
            headers={'User-Agent': 'Web3Fuel-Blog/1.0'}
        )
        
        if response.status_code == 200:
            posts = response.json()
            
            # Process posts
            processed_posts = []
            for post in posts:
                processed_post = process_post_data(post)
                if processed_post:
                    processed_posts.append(processed_post)
            
            return {
                'success': True,
                'posts': processed_posts,
                'total_pages': int(response.headers.get('X-WP-TotalPages', 1)),
                'total_posts': int(response.headers.get('X-WP-Total', len(processed_posts)))
            }
        else:
            print(f"WordPress API error: {response.status_code}")
            return {'success': False, 'error': f"API returned status {response.status_code}"}
            
    except requests.exceptions.Timeout:
        print("WordPress API timeout")
        return {'success': False, 'error': "Request timeout"}
    except Exception as e:
        print(f"Error fetching WordPress posts: {e}")
        return {'success': False, 'error': str(e)}

def process_post_data(post):
    """Process individual post data with enhanced image handling for 1920x1080 images"""
    try:
        print(f"\n=== Processing Post: {post.get('title', {}).get('rendered', 'Unknown')} ===")
        print(f"Featured Media ID: {post.get('featured_media')}")
        
        # Extract featured image with enhanced size handling
        featured_image = None
        featured_image_sizes = {}  # Store multiple sizes for responsive images

        # Method 1: Check _embedded wp:featuredmedia 
        if '_embedded' in post:
            print("Found _embedded data")
            if 'wp:featuredmedia' in post['_embedded']:
                print("Found wp:featuredmedia in _embedded")
                try:
                    media_list = post['_embedded']['wp:featuredmedia']
                    print(f"Media list type: {type(media_list)}, length: {len(media_list) if isinstance(media_list, list) else 'N/A'}")
                    
                    if isinstance(media_list, list) and len(media_list) > 0:
                        media = media_list[0]
                        print(f"Media object keys: {list(media.keys()) if isinstance(media, dict) else 'Not a dict'}")
                        
                        # Check for source_url first (most reliable - this will be your 1920x1080 full size)
                        if 'source_url' in media:
                            featured_image = media['source_url']
                            featured_image_sizes['full'] = media['source_url']
                            print(f"✓ Found source_url: {featured_image}")
                        
                        # Extract all available sizes for responsive images
                        if 'media_details' in media and 'sizes' in media['media_details']:
                            sizes = media['media_details']['sizes']
                            print(f"Available sizes: {list(sizes.keys())}")
                            
                            # Store all available sizes
                            for size_name, size_data in sizes.items():
                                if 'source_url' in size_data:
                                    featured_image_sizes[size_name] = size_data['source_url']
                                    print(f"✓ Found size {size_name}: {size_data['source_url']}")
                            
                            # If no source_url was found, try to get the best available size
                            if not featured_image:
                                # Prefer larger sizes for better quality, but not the massive full size
                                for size_name in ['large', 'medium_large', 'medium', 'full', 'thumbnail']:
                                    if size_name in sizes and 'source_url' in sizes[size_name]:
                                        featured_image = sizes[size_name]['source_url']
                                        print(f"✓ Found image via sizes[{size_name}]: {featured_image}")
                                        break
                        
                        # Fallback to guid if available
                        if not featured_image and 'guid' in media and 'rendered' in media['guid']:
                            featured_image = media['guid']['rendered']
                            featured_image_sizes['guid'] = media['guid']['rendered']
                            print(f"✓ Found image via guid: {featured_image}")
                            
                except Exception as e:
                    print(f"Error processing _embedded media: {e}")
            else:
                print("No wp:featuredmedia found in _embedded")
        else:
            print("No _embedded data found")

        # Method 2: Direct API call if still no image
        if not featured_image and 'featured_media' in post and post['featured_media'] != 0:
            print(f"Attempting direct API call for media ID: {post['featured_media']}")
            try:
                media_response = requests.get(
                    f"{WORDPRESS_API_BASE}/media/{post['featured_media']}",
                    timeout=10,
                    headers={'User-Agent': 'Web3Fuel-Blog/1.0'}
                )
                if media_response.status_code == 200:
                    media_data = media_response.json()
                    print(f"Direct API response keys: {list(media_data.keys())}")
                    
                    if 'source_url' in media_data:
                        featured_image = media_data['source_url']
                        featured_image_sizes['full'] = media_data['source_url']
                        print(f"✓ Found via direct API source_url: {featured_image}")
                    
                    if 'media_details' in media_data and 'sizes' in media_data['media_details']:
                        sizes = media_data['media_details']['sizes']
                        for size_name, size_data in sizes.items():
                            if 'source_url' in size_data:
                                featured_image_sizes[size_name] = size_data['source_url']
                        
                        # If no featured_image yet, select best size
                        if not featured_image:
                            for size_name in ['large', 'medium_large', 'medium', 'full']:
                                if size_name in sizes and 'source_url' in sizes[size_name]:
                                    featured_image = sizes[size_name]['source_url']
                                    print(f"✓ Found via direct API sizes[{size_name}]: {featured_image}")
                                    break
                else:
                    print(f"Direct API call failed: {media_response.status_code}")
            except Exception as e:
                print(f"Error with direct API call: {e}")

        # Final URL cleanup
        if featured_image:
            featured_image = featured_image.strip()
            # Ensure it's a full URL
            if featured_image.startswith('//'):
                featured_image = 'https:' + featured_image
            elif featured_image.startswith('/'):
                featured_image = WORDPRESS_SITE_URL + featured_image
            print(f"✓ FINAL FEATURED IMAGE: {featured_image}")
        else:
            print("✗ NO FEATURED IMAGE FOUND")
        
        # Clean up all image URLs in sizes dict
        for size_name in featured_image_sizes:
            url = featured_image_sizes[size_name].strip()
            if url.startswith('//'):
                featured_image_sizes[size_name] = 'https:' + url
            elif url.startswith('/'):
                featured_image_sizes[size_name] = WORDPRESS_SITE_URL + url
        
        # Extract author info
        author_name = "Web3Fuel Team"
        author_avatar = None
        if '_embedded' in post and 'author' in post['_embedded']:
            try:
                authors = post['_embedded']['author']
                if isinstance(authors, list) and len(authors) > 0:
                    author = authors[0]
                    author_name = author.get('name', author_name)
                    if 'avatar_urls' in author:
                        avatar_urls = author['avatar_urls']
                        for size in ['96', '48', '24']:
                            if size in avatar_urls:
                                author_avatar = avatar_urls[size]
                                break
            except Exception as e:
                print(f"Error extracting author: {e}")
        
        # Extract categories and tags
        categories = []
        tags = []
        if '_embedded' in post and 'wp:term' in post['_embedded']:
            try:
                term_groups = post['_embedded']['wp:term']
                if isinstance(term_groups, list):
                    for term_group in term_groups:
                        if isinstance(term_group, list):
                            for term in term_group:
                                if isinstance(term, dict):
                                    taxonomy = term.get('taxonomy', '')
                                    name = term.get('name', '')
                                    slug = term.get('slug', '')
                                    
                                    if taxonomy == 'category' and name and name != 'Uncategorized':
                                        categories.append({'name': name, 'slug': slug})
                                    elif taxonomy == 'post_tag' and name:
                                        tags.append({'name': name, 'slug': slug})
            except Exception as e:
                print(f"Error extracting categories/tags: {e}")
        
        # Clean up excerpt
        excerpt = ""
        try:
            if 'excerpt' in post and 'rendered' in post['excerpt']:
                excerpt = html.unescape(post['excerpt']['rendered'])
                excerpt = re.sub(r'<[^>]+>', '', excerpt)  # Remove HTML tags
                excerpt = excerpt.strip()
                if len(excerpt) > 200:
                    excerpt = excerpt[:200] + "..."
        except Exception as e:
            print(f"Error processing excerpt: {e}")
        
        # Calculate reading time
        content = ""
        word_count = 0
        try:
            if 'content' in post and 'rendered' in post['content']:
                content = re.sub(r'<[^>]+>', '', post['content']['rendered'])
                word_count = len(content.split()) if content else 0
        except Exception as e:
            print(f"Error processing content: {e}")
            
        reading_time = max(1, round(word_count / 200)) if word_count > 0 else 1
        
        result = {
            'id': post.get('id'),
            'title': html.unescape(post.get('title', {}).get('rendered', 'Untitled')),
            'excerpt': excerpt,
            'content': post.get('content', {}).get('rendered', ''),
            'link': post.get('link', ''),
            'date': post.get('date', ''),
            'modified': post.get('modified', ''),
            'featured_image': featured_image,
            'featured_image_sizes': featured_image_sizes,  # NEW: All available sizes
            'author': author_name,
            'author_avatar': author_avatar,
            'categories': categories,
            'tags': tags,
            'slug': post.get('slug', ''),
            'reading_time': reading_time,
            'word_count': word_count
        }
        
        print(f"✓ Processed post successfully")
        return result
    
    except Exception as e:
        print(f"✗ Error processing post: {e}")
        import traceback
        traceback.print_exc()
        return None

# API Routes
@blog_bp.route('/api/posts')
@rate_limit(max_requests=30, window=60)
def api_posts():
    """API endpoint to fetch blog posts with caching and debugging"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 7, type=int)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    debug = request.args.get('debug', '').lower() == 'true'
    
    print(f"\n=== API POSTS REQUEST ===")
    print(f"Page: {page}, Per Page: {per_page}")
    print(f"Search: '{search}', Category: '{category}'")
    print(f"Debug mode: {debug}")
    
    # Generate cache key
    cache_key = get_cache_key(
        "blog_posts",
        page=page,
        per_page=per_page,
        search=search,
        category=category
    )
    
    def fetch_posts():
        return fetch_wordpress_posts(
            per_page=per_page,
            page=page,
            search=search if search else None,
            category=category if category else None
        )
    
    # Skip cache if debug mode
    if debug:
        result = fetch_posts()
    else:
        result = get_cached_data(cache_key, fetch_posts)
    
    print(f"API Response: {result.get('success')}, Posts: {len(result.get('posts', []))}")
    
    return jsonify(result)

@blog_bp.route('/debug/wordpress')
def debug_wordpress():
    """Debug endpoint to examine raw WordPress data"""
    try:
        # Fetch raw data from WordPress
        response = requests.get(
            f"{WORDPRESS_API_BASE}/posts",
            params={
                'per_page': 1,
                '_embed': 'wp:featuredmedia,author,wp:term',
                'status': 'publish'
            },
            timeout=15,
            headers={'User-Agent': 'Web3Fuel-Blog/1.0'}
        )
        
        if response.status_code == 200:
            posts = response.json()
            
            if posts:
                post = posts[0]
                
                # Extract featured image info
                featured_info = {
                    'featured_media_id': post.get('featured_media'),
                    'has_embedded': '_embedded' in post,
                    'has_featuredmedia': '_embedded' in post and 'wp:featuredmedia' in post['_embedded'],
                }
                
                if '_embedded' in post and 'wp:featuredmedia' in post['_embedded']:
                    media_list = post['_embedded']['wp:featuredmedia']
                    if media_list and len(media_list) > 0:
                        media = media_list[0]
                        featured_info.update({
                            'media_id': media.get('id'),
                            'media_type': media.get('media_type'),
                            'mime_type': media.get('mime_type'),
                            'source_url': media.get('source_url'),
                            'available_sizes': list(media.get('media_details', {}).get('sizes', {}).keys()) if 'media_details' in media else [],
                        })
                        
                        # Get a few sample URLs
                        if 'media_details' in media and 'sizes' in media['media_details']:
                            sizes = media['media_details']['sizes']
                            sample_urls = {}
                            for size_name in ['thumbnail', 'medium', 'large', 'full']:
                                if size_name in sizes and 'source_url' in sizes[size_name]:
                                    sample_urls[size_name] = sizes[size_name]['source_url']
                            featured_info['sample_urls'] = sample_urls
                
                return f"""
                <html>
                <head><title>WordPress Debug</title></head>
                <body style="font-family: monospace; padding: 20px;">
                    <h1>WordPress API Debug</h1>
                    
                    <h2>API Response Status: {response.status_code}</h2>
                    
                    <h2>Post Info:</h2>
                    <p><strong>Title:</strong> {post.get('title', {}).get('rendered', 'N/A')}</p>
                    <p><strong>ID:</strong> {post.get('id')}</p>
                    <p><strong>Link:</strong> <a href="{post.get('link')}" target="_blank">{post.get('link')}</a></p>
                    
                    <h2>Featured Image Analysis:</h2>
                    <pre>{json.dumps(featured_info, indent=2)}</pre>
                    
                    <h2>Test Image Display:</h2>
                    {f'<img src="{featured_info.get("source_url")}" style="max-width: 300px;" alt="Featured Image">' if featured_info.get('source_url') else '<p>No source_url found</p>'}
                    
                    <h2>Raw Post Data (First 2000 chars):</h2>
                    <pre style="background: #f0f0f0; padding: 10px; overflow: auto;">{json.dumps(post, indent=2)[:2000]}...</pre>
                    
                    <h2>Quick Tests:</h2>
                    <p><a href="/blog/api/posts?debug=true" target="_blank">Test API with Debug</a></p>
                    <p><a href="/blog/" target="_blank">View Blog Page</a></p>
                </body>
                </html>
                """
            else:
                return "No posts found in WordPress"
        else:
            return f"WordPress API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Error: {str(e)}"

# Main blog page route
@blog_bp.route('/')
def blog_index():
    """Main blog landing page with all enhancements"""
    
# Updated blog template with enhanced image handling
    template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog - Web3Fuel.io</title>
    <meta name="description" content="Latest insights on blockchain, cryptocurrency, and Web3 technology from Web3Fuel.io">
    <meta name="keywords" content="blockchain, cryptocurrency, web3, bitcoin, ethereum, trading, defi">
    <link rel="alternate" type="application/rss+xml" title="Web3Fuel Blog RSS" href="/blog/feed">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://web3fuel.io/blog/">
    <meta property="og:title" content="Web3Fuel Blog - Blockchain & Crypto Insights">
    <meta property="og:description" content="Latest insights on blockchain, cryptocurrency, and Web3 technology">
    <meta property="og:image" content="https://web3fuel.io/static/og-image.png">

    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="https://web3fuel.io/blog/">
    <meta property="twitter:title" content="Web3Fuel Blog - Blockchain & Crypto Insights">
    <meta property="twitter:description" content="Latest insights on blockchain, cryptocurrency, and Web3 technology">
    <meta property="twitter:image" content="https://web3fuel.io/static/og-image.png">
    
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
            --success: #00ff88;
            --danger: #ff4444;
            --warning: #ffaa00;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--background);
            color: var(--primary);
            font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            line-height: 1.6;
        }

        /* Animated background */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 20%, rgba(0, 255, 234, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(255, 0, 255, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(124, 58, 237, 0.1) 0%, transparent 50%);
            z-index: -1;
            animation: floating 20s ease-in-out infinite;
        }

        @keyframes floating {
            0%, 100% { transform: translate(0, 0) rotate(0deg); }
            33% { transform: translate(30px, -30px) rotate(120deg); }
            66% { transform: translate(-20px, 20px) rotate(240deg); }
        }

        /* Enhanced Header Styles - keeping your existing header styles */
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
            padding: 0.75rem 1.25rem;
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
            0%, 100% { filter: drop-shadow(0 0 10px var(--secondary)); }
            50% { filter: drop-shadow(0 0 20px var(--secondary)); }
        }

        @media (min-width: 768px) {
            .nav-desktop { display: flex; }
            .menu-button { display: none; }
            .header-container { 
                padding: 0 3rem;
                max-width: 1650px;
            }
        }

        /* Page Header */
        .page-header {
            text-align: center;
            padding: 1.5rem 1.5rem;
            position: relative;
            border-bottom: 1px solid var(--border-color);
        }

        .page-title {
            font-size: 2rem;
            margin: 0;
            color: #ffffff;
        }

        .subtitle {
            font-size: 1.2rem;
            color: var(--text-muted);
            margin-top: 0;
            font-weight: 400;
        }

        /* Blog Content */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        .featured-section {
            margin-top:0.5rem;
            margin-bottom: 3rem;
            display: none;
        }

        .section-title {
            font-size: 2rem;
            color: var(--primary);
            margin-bottom: 2rem;
            text-align: center;
        }

        .posts-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .posts-title {
            font-size: 1.6rem;
            color: #ffffff;
            text-shadow: none;
            margin: 0;
            text-align: left;
            flex: 1;
        }

        .posts-count {
            color: #a1a1aa;
            font-size: 1.1rem;
            font-weight: 400;
            white-space: nowrap;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            .posts-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
            }
            
            .posts-title {
                font-size: 1.5rem;
            }
            
            .posts-count {
                align-self: flex-end;
                font-size: 0.8rem;
            }
        }

        .featured-post {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 2rem;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            cursor: pointer;
            display: flex;
            align-items: stretch;
        }

        .featured-post:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
            box-shadow: 0 20px 40px rgba(0, 255, 234, 0.2);
        }

        .featured-image {
            width: 60%;
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            position: relative;
            overflow: hidden;
            border-radius: 12px 0 0 12px;
            flex-shrink: 0;
            aspect-ratio: 16/9;
            min-height: 300px;
        }

        /* Responsive image adjustments */
        @media (min-width: 1200px) {
            .featured-image {
                min-height: 400px;
            }
        }

        @media (min-width: 768px) and (max-width: 1199px) {
            .featured-image {
                min-height: 350px;
            }
        }

        @media (max-width: 768px) {
            .featured-post {
                flex-direction: column;
            }
            
            .featured-image {
                width: 100% !important;
                min-height: 250px !important;
                border-radius: 12px 12px 0 0 !important;
                aspect-ratio: 16/9 !important;
            }
            
            .featured-content {
                justify-content: flex-start !important;
                gap: 0.75rem !important;
            }
        }

        @media (max-width: 480px) {
            .featured-image {
                min-height: 200px !important;
            }
        }

        .post-image {
            width: 100%;
            height: 250px; /* Increased height for grid posts */
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            overflow: hidden;
            border-radius: 12px 12px 0 0;
        }

        /* Add lazy loading styles */
        .image-loading {
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            opacity: 0.3;
            animation: pulse-loading 1.5s ease-in-out infinite;
        }

        @keyframes pulse-loading {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.6; }
        }

        .image-loaded {
            opacity: 1;
            transition: opacity 0.3s ease;
        }

        .image-error {
            background: linear-gradient(45deg, #333, #555);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .image-error::after {
            content: "Image unavailable";
        }

        .featured-content {
            padding: 2rem;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 2rem;
        }

        /* Content ordering and spacing for featured post */
        .featured-content .post-title {
            margin-bottom: 0 !important;
            order: 1;
            font-size: 2rem !important;
        }

        .featured-content .post-excerpt {
            margin-bottom: 0 !important;
            order: 2;
        }

        .featured-content .post-meta {
            margin-bottom: 0 !important;
            order: 3;
        }

        .featured-content .read-more-btn {
            order: 4;
            align-self: flex-start !important;
            padding: 0.5rem 1rem !important;
            font-size: 0.85rem !important;
        }

        .post-meta {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            color: var(--text-muted);
            font-size: 0.9rem;
            flex-wrap: wrap;
        }

        .meta-item {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }

        .post-title {
            font-size: 1.8rem;
            color: var(--text);
            margin-bottom: 1rem;
            line-height: 1.3;
        }

        .post-excerpt {
            color: var(--text-muted);
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }

        .read-more-btn {
            background: var(--primary);
            color: black;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            font-size: 0.9rem;
        }

        .read-more-btn:hover {
            background: #00d6c4;
            transform: translateY(-2px);
        }

        .posts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
            margin-bottom: 3rem;
        }

        .post-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .post-card:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
            box-shadow: 0 15px 30px rgba(0, 255, 234, 0.2);
        }

        .post-content {
            padding: 1.5rem;
        }

        .post-card .post-title {
            font-size: 1.3rem;
            margin-bottom: 0.75rem;
        }

        .post-card .post-excerpt {
            margin-bottom: 1rem;
        }

        .category-tags {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        .category-tag {
            background: rgba(0, 255, 234, 0.2);
            color: var(--primary);
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.8rem;
            border: 1px solid var(--primary);
            text-decoration: none;
            transition: all 0.3s ease;
        }

        .category-tag:hover {
            background: var(--primary);
            color: black;
        }

        /* Footer Styles - keeping your existing footer */
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

        @media (min-width: 768px) {
            .newsletter-form {
                flex-direction: row;
            }
            
            .newsletter-input {
                flex: 1;
            }

            .footer-main {
                flex-direction: row;
                align-items: flex-start;
            }
            
            .footer-bottom {
                justify-content: space-between;
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
        }
        
        /* Loading and Error States */
        .loading {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
        }

        .error-message {
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid #ff4444;
            border-radius: 8px;
            padding: 1rem;
            color: #ff4444;
            text-align: center;
            margin: 2rem 0;
        }

        /* Animation classes */
        .fade-in-up {
            animation: fadeInUp 0.6s ease-out forwards;
            opacity: 0;
            transform: translateY(20px);
        }

        @keyframes fadeInUp {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <header>
        <div class="header-container">
            <a href="/" class="logo">
                <span class="logo-icon">🚀</span>
                <span class="logo-text">Web3Fuel</span>
            </a>
            <nav class="nav-desktop">
                <a href="/trading-suite" class="nav-link">Trading Suite</a>
                <a href="/marketing-solutions" class="nav-link">Marketing Solutions</a>
                <a href="/blog" class="nav-link active">Blog</a>
                <a href="/contact" class="nav-link contact-highlight">Contact</a>
            </nav>
            <button class="menu-button" onclick="toggleMobileMenu()">☰</button>
        </div>
    </header>

    <!-- Page Header -->
    <div class="page-header">
        <h1 class="page-title">Latest Articles</h1>
        <p class="subtitle">Stay up to date with the latest AI trading & marketing insights, tutorials, and trends.</p>
    </div>

    <!-- Main Content -->
    <div class="container">
        <!-- Featured Section -->
        <section class="featured-section" id="featured-section">
            <div id="featured-post"></div>
        </section>

        <!-- Latest Posts Section -->
        <section>
            <div class="posts-header">
                <h2 class="posts-title">More Recent Posts</h2>
                <span class="posts-count" id="posts-count"> < Showing 6 of 6 articles > </span>
            </div>
            <div class="loading" id="loading">
                Loading posts...
            </div>
            <div class="posts-grid" id="posts-grid"></div>
        </section>
    </div>

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
                    <h3 class="newsletter-title">Join to Stay Updated with AI Insights</h3>
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
        // ENHANCED JAVASCRIPT FOR BETTER IMAGE HANDLING

        // Get the best image size based on container dimensions and device pixel ratio
        function getBestImageSize(imageSizes, containerWidth, containerHeight) {
            if (!imageSizes || Object.keys(imageSizes).length === 0) {
                return null;
            }
            
            // Get device pixel ratio for high DPI displays
            const pixelRatio = window.devicePixelRatio || 1;
            const targetWidth = containerWidth * pixelRatio;
            const targetHeight = containerHeight * pixelRatio;
            
            // For featured images (larger containers), prefer larger sizes
            if (containerHeight >= 300) {
                // On larger screens, prefer the full size or large for 1920x1080 images
                const screenWidth = window.innerWidth;
                if (screenWidth >= 1200) {
                    // Large desktop - use full size first
                    for (const size of ['full', 'large', 'medium_large', 'medium']) {
                        if (imageSizes[size]) {
                            return imageSizes[size];
                        }
                    }
                } else {
                    // Medium screens - use large first
                    for (const size of ['large', 'medium_large', 'full', 'medium']) {
                        if (imageSizes[size]) {
                            return imageSizes[size];
                        }
                    }
                }
            } else {
                // For smaller containers, prefer medium sizes
                for (const size of ['medium_large', 'large', 'medium', 'full']) {
                    if (imageSizes[size]) {
                        return imageSizes[size];
                    }
                }
            }
            
            // Fallback to any available size
            const availableSizes = Object.keys(imageSizes);
            if (availableSizes.length > 0) {
                return imageSizes[availableSizes[0]];
            }
            
            return null;
        }

        // Create responsive image with loading states
        function createResponsiveImage(imageData, containerElement, isFeatured = false) {
            const containerWidth = containerElement.offsetWidth || (isFeatured ? 800 : 400);
            const containerHeight = isFeatured ? 400 : 250;
            
            let imageUrl;
            
            if (imageData.featured_image_sizes && Object.keys(imageData.featured_image_sizes).length > 0) {
                // Use the best available size
                imageUrl = getBestImageSize(imageData.featured_image_sizes, containerWidth, containerHeight);
            } else if (imageData.featured_image) {
                // Fallback to the single featured image
                imageUrl = imageData.featured_image;
            }
            
            if (!imageUrl) {
                imageUrl = createPlaceholderImage(imageData.title);
            }
            
            // Add loading class
            containerElement.classList.add('image-loading');
            
            // Create a new image to test loading
            const testImage = new Image();
            
            testImage.onload = function() {
                // Image loaded successfully
                containerElement.style.backgroundImage = `url('${imageUrl}')`;
                containerElement.classList.remove('image-loading');
                containerElement.classList.add('image-loaded');
                
                // Add lazy loading for better performance
                if ('loading' in HTMLImageElement.prototype) {
                    testImage.loading = 'lazy';
                }
            };
            
            testImage.onerror = function() {
                // Image failed to load, try fallback or placeholder
                console.warn('Failed to load image:', imageUrl);
                
                // Try a different size if available
                if (imageData.featured_image_sizes) {
                    const fallbackSizes = ['medium', 'thumbnail', 'full'];
                    let fallbackFound = false;
                    
                    for (const size of fallbackSizes) {
                        if (imageData.featured_image_sizes[size] && imageData.featured_image_sizes[size] !== imageUrl) {
                            console.log('Trying fallback size:', size);
                            imageUrl = imageData.featured_image_sizes[size];
                            testImage.src = imageUrl; // This will trigger onload/onerror again
                            fallbackFound = true;
                            break;
                        }
                    }
                    
                    if (!fallbackFound) {
                        // All sizes failed, use placeholder
                        useErrorState();
                    }
                } else {
                    useErrorState();
                }
            };
            
            function useErrorState() {
                containerElement.classList.remove('image-loading');
                containerElement.classList.add('image-error');
                const placeholderUrl = createPlaceholderImage(imageData.title);
                containerElement.style.backgroundImage = `url('${placeholderUrl}')`;
            }
            
            // Start loading the image
            testImage.src = imageUrl;
            
            return imageUrl;
        }

        // Toggle mobile menu (if you have one)
        function toggleMobileMenu() {
            // Add mobile menu functionality if needed
            console.log('Mobile menu toggle');
        }

        // Create placeholder image
        function createPlaceholderImage(title) {
            const colors = ['00ffea', 'ff00ff', '7c3aed'];
            const color = colors[Math.floor(Math.random() * colors.length)];
            return `data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300"><rect width="400" height="300" fill="%23${color}"/><text x="200" y="150" text-anchor="middle" fill="black" font-size="16" font-weight="bold">Web3Fuel</text></svg>`;
        }

        // Enhanced date formatting
        function formatDate(dateString) {
            const date = new Date(dateString);
            const now = new Date();
            const diffTime = Math.abs(now - date);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays === 1) {
                return "Yesterday";
            } else if (diffDays < 7) {
                return `${diffDays} days ago`;
            } else if (diffDays < 30) {
                const weeks = Math.floor(diffDays / 7);
                return `${weeks} week${weeks > 1 ? 's' : ''} ago`;
            } else {
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });
            }
        }

        // Track blog clicks for analytics
        function trackBlogClick(postTitle, postUrl) {
            console.log('Blog click tracked:', postTitle, postUrl);
        }

        // Enhanced display featured post function
        function displayFeaturedPost(post) {
            const featuredContainer = document.getElementById('featured-post');
            
            featuredContainer.innerHTML = `
                <article class="featured-post fade-in-up" data-post-url="${post.link}">
                    <div class="featured-image" role="img" aria-label="Featured image for ${post.title}"></div>
                    <div class="featured-content">
                        <h3 class="post-title">${post.title}</h3>
                        <p class="post-excerpt">${post.excerpt}</p>
                        <div class="post-meta">
                            <span class="meta-item">📅 ${formatDate(post.date)}</span>
                            <span class="meta-item">✍️ ${post.author}</span>
                            <span class="meta-item">📖 ${post.reading_time} min read</span>
                        </div>
                        <a href="${post.link}" class="read-more-btn read-more-btn-small" target="_blank" rel="noopener" onclick="event.stopPropagation(); trackBlogClick('${post.title}', '${post.link}')">
                            Read Full Article →
                        </a>
                    </div>
                </article>
            `;
            
            // Apply responsive image after DOM is created
            const imageContainer = featuredContainer.querySelector('.featured-image');
            createResponsiveImage(post, imageContainer, true);
            
            // Add click handler to the entire post
            const postElement = featuredContainer.querySelector('.featured-post');
            postElement.addEventListener('click', function() {
                trackBlogClick(post.title, post.link);
                window.open(post.link, '_blank', 'noopener');
            });
            
            document.getElementById('featured-section').style.display = 'block';
        }

        // Enhanced display posts grid function
        function displayPosts(posts, append = false) {
            const postsGrid = document.getElementById('posts-grid');
            
            if (!append) {
                postsGrid.innerHTML = '';
            }
            
            posts.forEach((post, index) => {
                const postCard = document.createElement('article');
                postCard.className = 'post-card fade-in-up';
                postCard.style.animationDelay = `${index * 0.1}s`;
                postCard.setAttribute('data-post-url', post.link);
                postCard.innerHTML = `
                    <div class="post-image" role="img" aria-label="Image for ${post.title}"></div>
                    <div class="post-content">
                        <div class="post-meta">
                            <span class="meta-item">📅 ${formatDate(post.date)}</span>
                            <span class="meta-item">✍️ ${post.author}</span>
                            <span class="meta-item">📖 ${post.reading_time} min read</span>
                        </div>
                        <h4 class="post-title">${post.title}</h4>
                        <p class="post-excerpt">${post.excerpt}</p>
                        <div class="category-tags">
                            ${post.categories.map(cat => `<span class="category-tag">${cat.name}</span>`).join('')}
                        </div>
                        <a href="${post.link}" class="read-more-btn" target="_blank" rel="noopener" onclick="event.stopPropagation(); trackBlogClick('${post.title}', '${post.link}')">
                            Read More →
                        </a>
                    </div>
                `;
                
                // Add click handler to the entire post card
                postCard.addEventListener('click', function() {
                    trackBlogClick(post.title, post.link);
                    window.open(post.link, '_blank', 'noopener');
                });
                
                postsGrid.appendChild(postCard);
                
                // Apply responsive image after DOM is added
                const imageContainer = postCard.querySelector('.post-image');
                createResponsiveImage(post, imageContainer, false);
            });
        }

        // Performance optimization: Preload critical images
        function preloadCriticalImages(posts) {
            const criticalPosts = posts.slice(0, 3); // Preload first 3 images
            
            criticalPosts.forEach(post => {
                if (post.featured_image_sizes && post.featured_image_sizes.medium_large) {
                    const link = document.createElement('link');
                    link.rel = 'preload';
                    link.as = 'image';
                    link.href = post.featured_image_sizes.medium_large;
                    document.head.appendChild(link);
                }
            });
        }

        // Enhanced fallback content
        function showFallbackContent() {
            const featuredContainer = document.getElementById('featured-post');
            const postsGrid = document.getElementById('posts-grid');
            
            featuredContainer.innerHTML = `
                <article class="featured-post">
                    <div class="featured-image"></div>
                    <div class="featured-content">
                        <div class="post-meta">
                            <span class="meta-item">📅 Latest</span>
                            <span class="meta-item">✍️ Web3Fuel Team</span>
                            <span class="meta-item">📖 5 min read</span>
                        </div>
                        <h3 class="post-title">Welcome to Web3Fuel Blog</h3>
                        <p class="post-excerpt">Stay updated with the latest insights on blockchain technology, cryptocurrency markets, and Web3 innovations. Our expert analysis helps you navigate the rapidly evolving digital asset landscape.</p>
                        <div class="category-tags">
                            <span class="category-tag">Blockchain</span>
                            <span class="category-tag">Cryptocurrency</span>
                            <span class="category-tag">Web3</span>
                        </div>
                        <a href="https://web3fuel.io/blockchain/blog/" class="read-more-btn" target="_blank" rel="noopener">Visit Our Blog →</a>
                    </div>
                </article>
            `;
            
            const fallbackPosts = [
                {
                    title: "Cryptocurrency Market Analysis",
                    excerpt: "Deep dive into current market trends, price movements, and what to expect in the coming months.",
                    category: "Analysis",
                    readTime: "8 min read"
                },
                {
                    title: "DeFi Protocol Security", 
                    excerpt: "Understanding the latest security measures and best practices for decentralized finance protocols.",
                    category: "DeFi",
                    readTime: "6 min read"
                },
                {
                    title: "NFT Market Evolution",
                    excerpt: "How the NFT landscape is changing and what new opportunities are emerging for creators and collectors.",
                    category: "NFT", 
                    readTime: "7 min read"
                }
            ];
            
            postsGrid.innerHTML = fallbackPosts.map(post => `
                <article class="post-card">
                    <div class="post-image"></div>
                    <div class="post-content">
                        <div class="post-meta">
                            <span class="meta-item">📅 Recent</span>
                            <span class="meta-item">✍️ Analysis Team</span>
                            <span class="meta-item">📖 ${post.readTime}</span>
                        </div>
                        <h4 class="post-title">${post.title}</h4>
                        <p class="post-excerpt">${post.excerpt}</p>
                        <div class="category-tags">
                            <span class="category-tag">${post.category}</span>
                        </div>
                        <a href="https://web3fuel.io/blockchain/blog/" class="read-more-btn" target="_blank" rel="noopener">Read More →</a>
                    </div>
                </article>
            `).join('');
            
            document.getElementById('featured-section').style.display = 'block';
        }

        // Enhanced post loading with error handling
        async function loadPosts(page = 1, append = false) {
            const loadingElement = document.getElementById('loading');
            
            try {
                loadingElement.style.display = 'block';
                
                const response = await fetch(`/blog/api/posts?page=${page}&per_page=7`);
                const data = await response.json();
                
                loadingElement.style.display = 'none';
                
                if (data.success && data.posts.length > 0) {
                    // Preload critical images for better performance
                    if (page === 1) {
                        preloadCriticalImages(data.posts);
                    }
                    
                    if (page === 1) {
                        // Load featured post
                        displayFeaturedPost(data.posts[0]);
                        // Load remaining posts in grid
                        if (data.posts.length > 1) {
                            displayPosts(data.posts.slice(1), append);
                        }
                    } else {
                        displayPosts(data.posts, append);
                    }
                } else {
                    // Show fallback content
                    showFallbackContent();
                }
            } catch (error) {
                console.error('Error loading posts:', error);
                loadingElement.style.display = 'none';
                showFallbackContent();
            }
        }

        // Initialize when DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            loadPosts(1);
        });
    </script>
</body>
</html>
    '''
    
    return render_template_string(template)