from flask import Blueprint, render_template, jsonify, request, Response, abort
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
                            print(f"[OK] Found source_url: {featured_image}")
                        
                        # Extract all available sizes for responsive images
                        if 'media_details' in media and 'sizes' in media['media_details']:
                            sizes = media['media_details']['sizes']
                            print(f"Available sizes: {list(sizes.keys())}")
                            
                            # Store all available sizes
                            for size_name, size_data in sizes.items():
                                if 'source_url' in size_data:
                                    featured_image_sizes[size_name] = size_data['source_url']
                                    print(f"[OK] Found size {size_name}: {size_data['source_url']}")
                            
                            # If no source_url was found, try to get the best available size
                            if not featured_image:
                                # Prefer larger sizes for better quality, but not the massive full size
                                for size_name in ['large', 'medium_large', 'medium', 'full', 'thumbnail']:
                                    if size_name in sizes and 'source_url' in sizes[size_name]:
                                        featured_image = sizes[size_name]['source_url']
                                        print(f"[OK] Found image via sizes[{size_name}]: {featured_image}")
                                        break
                        
                        # Fallback to guid if available
                        if not featured_image and 'guid' in media and 'rendered' in media['guid']:
                            featured_image = media['guid']['rendered']
                            featured_image_sizes['guid'] = media['guid']['rendered']
                            print(f"[OK] Found image via guid: {featured_image}")
                            
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
                        print(f"[OK] Found via direct API source_url: {featured_image}")
                    
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
                                    print(f"[OK] Found via direct API sizes[{size_name}]: {featured_image}")
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
            print(f"[OK] FINAL FEATURED IMAGE: {featured_image}")
        else:
            print("[ERR] NO FEATURED IMAGE FOUND")
        
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
        
        print(f"[OK] Processed post successfully")
        return result
    
    except Exception as e:
        print(f"[ERR] Error processing post: {e}")
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
    return render_template('blog.html')