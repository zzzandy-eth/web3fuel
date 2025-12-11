"""
Reply Assistant Blueprint
AI-powered social media engagement tool with Discord integration
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bleach
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import pooling
import os
import json
import anthropic
import logging

# Setup logging
logger = logging.getLogger(__name__)

reply_assistant_bp = Blueprint('reply_assistant', __name__, url_prefix='/tools/reply-assistant')

# Configuration from environment
TOOL_PASSWORD = os.getenv('TOOL_PASSWORD')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5000/tools/reply-assistant/auth/discord/callback')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# Initialize OAuth
oauth = OAuth()

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Initialize database connection pool
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="reply_assistant_pool",
        pool_size=5,
        pool_reset_session=True,
        **DB_CONFIG
    )
    logger.info("✓ Database connection pool initialized")
except Exception as e:
    logger.error(f"Failed to create database connection pool: {e}")
    db_pool = None

def get_db_connection():
    """Get database connection from pool"""
    try:
        if db_pool:
            return db_pool.get_connection()
        else:
            # Fallback to direct connection if pool failed
            return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection error: {e}", exc_info=True)
        return None

def get_db_cursor(conn):
    """Get database cursor with dict results"""
    return conn.cursor(dictionary=True)

def sanitize_input(text, strip_all=False):
    """Sanitize user input to prevent XSS attacks"""
    if not text:
        return text

    if strip_all:
        # Strip all HTML tags
        return bleach.clean(text, tags=[], strip=True)
    else:
        # Allow only safe tags
        allowed_tags = []
        allowed_attrs = {}
        return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)

def check_rate_limit(user_discord_id):
    """Check if user has remaining requests"""
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error"

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT daily_limit, usage_count, usage_reset_date, is_unlimited
            FROM users
            WHERE discord_id = %s
        """, (user_discord_id,))

        user = cursor.fetchone()

        if not user:
            return False, "User not found"

        # Unlimited users bypass limits
        if user['is_unlimited']:
            return True, None

        # Reset counter if new day
        if user['usage_reset_date'] < datetime.now().date():
            cursor.execute("""
                UPDATE users
                SET usage_count = 0,
                    usage_reset_date = CURDATE()
                WHERE discord_id = %s
            """, (user_discord_id,))
            conn.commit()
            user['usage_count'] = 0

        # Check limit
        if user['usage_count'] >= user['daily_limit']:
            return False, f"Daily limit reached ({user['daily_limit']} requests/day)"

        return True, None

    except Exception as e:
        print(f"Rate limit check error: {e}")
        return False, "Error checking rate limit"
    finally:
        cursor.close()
        conn.close()

def increment_usage(user_discord_id):
    """Increment user's daily usage counter"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            UPDATE users
            SET usage_count = usage_count + 1
            WHERE discord_id = %s
        """, (user_discord_id,))
        conn.commit()
    except Exception as e:
        print(f"Usage increment error: {e}")
    finally:
        cursor.close()
        conn.close()

def get_user_stats(user_discord_id):
    """Get user's reply statistics"""
    conn = get_db_connection()
    if not conn:
        return {'total_replies': 0, 'pending_replies': 0, 'monitored_accounts': 0}

    cursor = get_db_cursor(conn)

    try:
        # Total posted replies
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM reply_history
            WHERE user_discord_id = %s
        """, (user_discord_id,))
        total_replies = cursor.fetchone()['count']

        # Pending replies
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM pending_replies
            WHERE user_discord_id = %s AND status IN ('pending', 'edited')
        """, (user_discord_id,))
        pending_replies = cursor.fetchone()['count']

        # Monitored accounts
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM monitored_accounts
            WHERE user_discord_id = %s AND is_active = TRUE
        """, (user_discord_id,))
        monitored_accounts = cursor.fetchone()['count']

        return {
            'total_replies': total_replies,
            'pending_replies': pending_replies,
            'monitored_accounts': monitored_accounts
        }

    except Exception as e:
        print(f"Stats error: {e}")
        return {'total_replies': 0, 'pending_replies': 0, 'monitored_accounts': 0}
    finally:
        cursor.close()
        conn.close()

# ============================================
# ROUTE: Password Authentication
# ============================================

@reply_assistant_bp.route('/', methods=['GET'])
def index():
    """Password authentication page"""

    # Check if already authenticated
    if 'authenticated' in session and session['authenticated']:
        if 'user_discord_id' in session:
            return redirect(url_for('reply_assistant.dashboard'))
        else:
            return redirect(url_for('reply_assistant.discord_login'))

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reply Assistant - Authentication</title>
        <style>
            :root {
                --primary: #00ffea;
                --secondary: #ff00ff;
                --background: #000000;
                --text: #ffffff;
                --text-muted: #a1a1aa;
                --border-color: #27272a;
            }
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                min-height: 100vh;
                color: #e6edf3;
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
            .close-menu {
                position: absolute;
                top: 1.5rem;
                right: 1.5rem;
                background: transparent;
                border: 2px solid var(--primary);
                color: var(--primary);
                font-size: 1.5rem;
                padding: 0.5rem 0.75rem;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .close-menu:hover {
                background: var(--primary);
                color: var(--background);
            }
            .mobile-nav-link {
                color: var(--text);
                text-decoration: none;
                font-size: 1.5rem;
                font-weight: 600;
                padding: 1rem 2rem;
                border-radius: 8px;
                transition: all 0.3s ease;
            }
            .mobile-nav-link:hover {
                color: var(--primary);
                background: rgba(0, 255, 234, 0.1);
            }
            @media (min-width: 768px) {
                .nav-desktop {
                    display: flex;
                }
                .menu-button {
                    display: none;
                }
            }
            /* Main Content */
            .main-content {
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: calc(100vh - 5rem);
                padding: 20px;
            }
            .auth-container {
                background: #161b22;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                max-width: 400px;
                width: 100%;
                border: 1px solid #30363d;
            }
            h1 {
                color: #e6edf3;
                margin-bottom: 10px;
                font-size: 28px;
                text-align: center;
            }
            .subtitle {
                color: #8b949e;
                margin-bottom: 30px;
                text-align: center;
                font-size: 14px;
            }
            .error {
                background: #3d1f1f;
                border: 1px solid #f85149;
                color: #f85149;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 20px;
                font-size: 14px;
            }
            input[type="password"] {
                width: 100%;
                padding: 14px;
                border: 2px solid #30363d;
                border-radius: 8px;
                font-size: 16px;
                margin-bottom: 20px;
                transition: border-color 0.3s;
                background: #0d1117;
                color: #e6edf3;
            }
            input[type="password"]::placeholder {
                color: #8b949e;
            }
            input[type="password"]:focus {
                outline: none;
                border-color: #58a6ff;
            }
            .auth-container button {
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, opacity 0.2s;
            }
            .auth-container button:hover {
                transform: translateY(-2px);
                opacity: 0.9;
            }
            .auth-container button:active {
                transform: translateY(0);
            }
            .info {
                margin-top: 20px;
                padding: 15px;
                background: #21262d;
                border-radius: 8px;
                font-size: 13px;
                color: #8b949e;
                border: 1px solid #30363d;
            }
            .info strong {
                color: #e6edf3;
            }
        </style>
    </head>
    <body>
        <!-- Header -->
        <header>
            <div class="header-container">
                <a href="/" class="logo">
                    <span class="logo-icon">🚀</span>
                    <span class="logo-text">Web3Fuel.io</span>
                </a>
                <nav class="nav-desktop">
                    <a href="/tools" class="nav-link active">Tools</a>
                    <a href="/research" class="nav-link">Research</a>
                    <a href="/blog" class="nav-link">Blog</a>
                    <a href="/contact" class="nav-link">Contact</a>
                </nav>
                <button class="menu-button" id="menu-button">☰</button>
            </div>
            <!-- Mobile Menu -->
            <div class="mobile-menu" id="mobile-menu">
                <button class="close-menu" id="close-menu">✕</button>
                <nav>
                    <a href="/tools" class="mobile-nav-link active">Tools</a>
                    <a href="/research" class="mobile-nav-link">Research</a>
                    <a href="/blog" class="mobile-nav-link">Blog</a>
                    <a href="/contact" class="mobile-nav-link">Contact</a>
                </nav>
            </div>
        </header>

        <div class="main-content">
            <div class="auth-container">
                <h1>🤖 Reply Assistant</h1>
                <p class="subtitle">AI-powered social media engagement tool</p>

                {% if error %}
                <div class="error">{{ error }}</div>
                {% endif %}

                <form method="POST" action="/tools/reply-assistant/auth/password">
                    <input type="password" name="password" placeholder="Enter password" required autofocus>
                    <button type="submit">Continue</button>
                </form>

                <div class="info">
                    <strong>What is Reply Assistant?</strong><br>
                    Monitor X and LinkedIn accounts, get AI-generated reply suggestions via Discord,
                    and post with one-click approval.
                </div>
            </div>
        </div>

        <script>
            // Mobile Menu Toggle
            const menuButton = document.getElementById('menu-button');
            const mobileMenu = document.getElementById('mobile-menu');
            const closeMenu = document.getElementById('close-menu');

            if (menuButton && mobileMenu) {
                menuButton.addEventListener('click', () => {
                    mobileMenu.classList.add('active');
                    document.body.style.overflow = 'hidden';
                });

                if (closeMenu) {
                    closeMenu.addEventListener('click', () => {
                        mobileMenu.classList.remove('active');
                        document.body.style.overflow = 'auto';
                    });
                }
            }
        </script>
    </body>
    </html>
    """

    error = request.args.get('error')
    return render_template_string(html, error=error)

@reply_assistant_bp.route('/auth/password', methods=['POST'])
def password_auth():
    """Verify password"""
    password = request.form.get('password')

    if password == TOOL_PASSWORD:
        session['authenticated'] = True
        session.permanent = True
        return redirect(url_for('reply_assistant.discord_login'))
    else:
        return redirect(url_for('reply_assistant.index', error='Invalid password'))

# ============================================
# ROUTE: Discord OAuth
# ============================================

@reply_assistant_bp.route('/auth/discord/login')
def discord_login():
    """Redirect to Discord OAuth"""

    if 'authenticated' not in session or not session['authenticated']:
        return redirect(url_for('reply_assistant.index'))

    # Discord OAuth URL
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize?"
        f"client_id={DISCORD_CLIENT_ID}&"
        f"redirect_uri={DISCORD_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=identify"
    )

    return redirect(discord_auth_url)

@reply_assistant_bp.route('/auth/discord/callback')
def discord_callback():
    """Handle Discord OAuth callback"""

    if 'authenticated' not in session or not session['authenticated']:
        return redirect(url_for('reply_assistant.index'))

    code = request.args.get('code')

    if not code:
        return redirect(url_for('reply_assistant.index', error='OAuth failed'))

    try:
        # Exchange code for access token
        import requests

        token_response = requests.post(
            'https://discord.com/api/oauth2/token',
            data={
                'client_id': DISCORD_CLIENT_ID,
                'client_secret': DISCORD_CLIENT_SECRET,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': DISCORD_REDIRECT_URI
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        token_data = token_response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            return redirect(url_for('reply_assistant.index', error='Failed to get access token'))

        # Get user info
        user_response = requests.get(
            'https://discord.com/api/users/@me',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        user_data = user_response.json()

        # Store user in database
        conn = get_db_connection()
        if conn:
            cursor = get_db_cursor(conn)

            cursor.execute("""
                INSERT INTO users (discord_id, discord_username, discord_discriminator, discord_avatar)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    discord_username = VALUES(discord_username),
                    discord_discriminator = VALUES(discord_discriminator),
                    discord_avatar = VALUES(discord_avatar),
                    last_login_at = CURRENT_TIMESTAMP
            """, (
                user_data['id'],
                user_data['username'],
                user_data.get('discriminator', '0'),
                user_data.get('avatar')
            ))

            # Create default filter settings
            cursor.execute("""
                INSERT IGNORE INTO filter_settings (user_discord_id)
                VALUES (%s)
            """, (user_data['id'],))

            conn.commit()
            cursor.close()
            conn.close()

        # Store in session
        session['user_discord_id'] = user_data['id']
        session['user_discord_username'] = user_data['username']
        session['user_discord_avatar'] = user_data.get('avatar')

        return redirect(url_for('reply_assistant.dashboard'))

    except Exception as e:
        print(f"Discord OAuth error: {e}")
        return redirect(url_for('reply_assistant.index', error='Authentication failed'))

@reply_assistant_bp.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('reply_assistant.index'))

# ============================================
# ROUTE: Dashboard
# ============================================

@reply_assistant_bp.route('/dashboard')
def dashboard():
    """Main dashboard"""

    if 'user_discord_id' not in session:
        return redirect(url_for('reply_assistant.index'))

    user_discord_id = session['user_discord_id']

    # Get user info
    conn = get_db_connection()
    if not conn:
        return "Database error", 500

    cursor = get_db_cursor(conn)

    cursor.execute("""
        SELECT * FROM users WHERE discord_id = %s
    """, (user_discord_id,))

    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not user['is_active']:
        return "Access denied", 403

    # Get stats
    stats = get_user_stats(user_discord_id)

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reply Assistant - Dashboard</title>
        <style>
            :root {
                --primary: #00ffea;
                --secondary: #ff00ff;
                --background: #000000;
                --text: #ffffff;
                --text-muted: #a1a1aa;
                --border-color: #27272a;
            }
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                color: #e6edf3;
            }
            /* Site Header Styles */
            .site-header {
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
            .close-menu {
                position: absolute;
                top: 1.5rem;
                right: 1.5rem;
                background: transparent;
                border: 2px solid var(--primary);
                color: var(--primary);
                font-size: 1.5rem;
                padding: 0.5rem 0.75rem;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .close-menu:hover {
                background: var(--primary);
                color: var(--background);
            }
            .mobile-nav-link {
                color: var(--text);
                text-decoration: none;
                font-size: 1.5rem;
                font-weight: 600;
                padding: 1rem 2rem;
                border-radius: 8px;
                transition: all 0.3s ease;
            }
            .mobile-nav-link:hover {
                color: var(--primary);
                background: rgba(0, 255, 234, 0.1);
            }
            @media (min-width: 768px) {
                .nav-desktop {
                    display: flex;
                }
                .menu-button {
                    display: none;
                }
            }
            /* Main Content */
            .main-content {
                padding: 20px;
            }
            .dashboard-header {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }
            .dashboard-header h1 {
                font-size: 32px;
                margin-bottom: 10px;
            }
            .dashboard-header p {
                opacity: 0.9;
                font-size: 16px;
            }
            .user-info {
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.2);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .user-info .username {
                font-weight: 600;
            }
            .user-info a {
                color: white;
                text-decoration: none;
                padding: 8px 16px;
                background: rgba(255,255,255,0.2);
                border-radius: 6px;
                transition: background 0.3s;
            }
            .user-info a:hover {
                background: rgba(255,255,255,0.3);
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: #161b22;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                text-align: center;
                border: 1px solid #30363d;
            }
            .stat-value {
                font-size: 36px;
                font-weight: 700;
                color: #58a6ff;
                margin-bottom: 8px;
            }
            .stat-label {
                color: #8b949e;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .nav-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
            }
            .nav-card {
                background: #161b22;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                text-decoration: none;
                color: #e6edf3;
                transition: transform 0.3s, box-shadow 0.3s, border-color 0.3s;
                border: 1px solid #30363d;
            }
            .nav-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 8px 30px rgba(0,0,0,0.4);
                border-color: #58a6ff;
            }
            .nav-card h3 {
                color: #58a6ff;
                margin-bottom: 12px;
                font-size: 20px;
            }
            .nav-card p {
                color: #8b949e;
                line-height: 1.6;
                font-size: 14px;
            }
            .tools-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .tool-card {
                background: #161b22;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                border: 1px solid #30363d;
            }
            .tool-card h3 {
                color: #58a6ff;
                margin-bottom: 8px;
                font-size: 18px;
            }
            .tool-card p {
                color: #8b949e;
                font-size: 13px;
                margin-bottom: 15px;
            }
            .tool-card textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #30363d;
                border-radius: 8px;
                font-size: 14px;
                font-family: inherit;
                margin-bottom: 10px;
                resize: vertical;
                background: #0d1117;
                color: #e6edf3;
            }
            .tool-card textarea::placeholder {
                color: #8b949e;
            }
            .tool-card textarea:focus {
                outline: none;
                border-color: #58a6ff;
            }
            .tool-card button, #testBtn {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, opacity 0.2s;
            }
            .tool-card button:hover, #testBtn:hover {
                transform: translateY(-2px);
                opacity: 0.9;
            }
            #testResult {
                margin-top: 15px;
                padding: 15px;
                background: #1c2128;
                border-left: 4px solid #58a6ff;
                border-radius: 6px;
            }
            #testResult.error {
                background: #3d1f1f;
                border-left-color: #f85149;
            }
            #testResult .result-label {
                font-size: 12px;
                color: #8b949e;
                text-transform: uppercase;
                margin-bottom: 5px;
            }
            #testResult .result-value {
                color: #e6edf3;
                margin-bottom: 10px;
                line-height: 1.5;
            }
            .usage-stat {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #30363d;
            }
            .usage-stat:last-child {
                border-bottom: none;
            }
            .usage-label {
                color: #8b949e;
                font-size: 14px;
            }
            .usage-value {
                color: #e6edf3;
                font-weight: 600;
                font-size: 14px;
            }
            /* Toast Notifications */
            .toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .toast {
                padding: 14px 20px;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                box-shadow: 0 4px 20px rgba(0,0,0,0.4);
                display: flex;
                align-items: center;
                gap: 10px;
                animation: slideIn 0.3s ease;
                max-width: 350px;
            }
            .toast.success {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
            }
            .toast.error {
                background: linear-gradient(135deg, #da3633 0%, #f85149 100%);
            }
            .toast.info {
                background: linear-gradient(135deg, #1f6feb 0%, #58a6ff 100%);
            }
            .toast.warning {
                background: linear-gradient(135deg, #9e6a03 0%, #d29922 100%);
            }
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            .toast.hiding {
                animation: slideOut 0.3s ease forwards;
            }
            /* Loading States */
            .btn-loading {
                position: relative;
                pointer-events: none;
                opacity: 0.8;
            }
            .btn-loading::after {
                content: '';
                position: absolute;
                width: 16px;
                height: 16px;
                top: 50%;
                left: 50%;
                margin-left: -8px;
                margin-top: -8px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            .btn-loading span {
                visibility: hidden;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            /* Monitoring Status Card */
            .monitoring-status {
                background: #161b22;
                padding: 20px;
                border-radius: 12px;
                border: 1px solid #30363d;
                margin-bottom: 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .status-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .status-indicator {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #238636;
                animation: pulse 2s infinite;
            }
            .status-indicator.paused {
                background: #d29922;
                animation: none;
            }
            .status-indicator.offline {
                background: #da3633;
                animation: none;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .status-text {
                font-size: 14px;
                color: #8b949e;
            }
            .status-text strong {
                color: #e6edf3;
            }
            .monitoring-controls {
                display: flex;
                gap: 10px;
            }
            .btn-secondary {
                background: #21262d;
                border: 1px solid #30363d;
                color: #e6edf3;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                cursor: pointer;
                transition: background 0.2s, border-color 0.2s;
            }
            .btn-secondary:hover {
                background: #30363d;
                border-color: #8b949e;
            }
            .btn-resume {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                border-color: #238636;
                color: white;
            }
            .btn-resume:hover {
                background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%);
                border-color: #2ea043;
            }
        </style>
    </head>
    <body>
        <!-- Site Header -->
        <header class="site-header">
            <div class="header-container">
                <a href="/" class="logo">
                    <span class="logo-icon">🚀</span>
                    <span class="logo-text">Web3Fuel.io</span>
                </a>
                <nav class="nav-desktop">
                    <a href="/tools" class="nav-link active">Tools</a>
                    <a href="/research" class="nav-link">Research</a>
                    <a href="/blog" class="nav-link">Blog</a>
                    <a href="/contact" class="nav-link">Contact</a>
                </nav>
                <button class="menu-button" id="menu-button">☰</button>
            </div>
            <!-- Mobile Menu -->
            <div class="mobile-menu" id="mobile-menu">
                <button class="close-menu" id="close-menu">✕</button>
                <nav>
                    <a href="/tools" class="mobile-nav-link active">Tools</a>
                    <a href="/research" class="mobile-nav-link">Research</a>
                    <a href="/blog" class="mobile-nav-link">Blog</a>
                    <a href="/contact" class="mobile-nav-link">Contact</a>
                </nav>
            </div>
        </header>

        <!-- Toast Container -->
        <div class="toast-container" id="toastContainer"></div>

        <div class="main-content">
            <div class="dashboard-header">
                <h1>🤖 Reply Assistant Dashboard</h1>
                <p>Monitor social media and engage with AI-powered replies</p>

                <div class="user-info">
                    <div class="username">👤 {{ user.discord_username }}</div>
                    <a href="/tools/reply-assistant/logout">Logout</a>
                </div>
            </div>

            <!-- Monitoring Status -->
            <div class="monitoring-status">
                <div class="status-info">
                    <div class="status-indicator" id="statusIndicator"></div>
                    <div class="status-text">
                        <strong id="statusLabel">Checking...</strong>
                        <span id="statusDetail"></span>
                    </div>
                </div>
                <div class="monitoring-controls">
                    <button class="btn-secondary" onclick="refreshStatus()" id="refreshBtn">
                        <span>Refresh Status</span>
                    </button>
                    <button class="btn-secondary" onclick="toggleMonitoring()" id="toggleBtn" style="display:none;">
                        <span>Pause Monitoring</span>
                    </button>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Monitored Accounts</div>
                    <div class="stat-value">{{ stats.monitored_accounts }}</div>
                </div>

                <div class="stat-card">
                    <div class="stat-label">Pending Replies</div>
                    <div class="stat-value">{{ stats.pending_replies }}</div>
                </div>

                <div class="stat-card">
                    <div class="stat-label">Total Replies</div>
                    <div class="stat-value">{{ stats.total_replies }}</div>
                </div>
            </div>

            <div class="tools-grid">
                <div class="tool-card">
                    <h3>🧪 Test AI Generation</h3>
                    <p>Test the reply generation without waiting for monitoring</p>
                    <form id="testForm" onsubmit="return testGeneration(event)">
                        <textarea id="testPostContent" placeholder="Paste a social media post here to test AI reply generation..." rows="4" required></textarea>
                        <button type="submit" id="testBtn">Generate Reply</button>
                    </form>
                    <div id="testResult" style="display:none;"></div>
                </div>

                <div class="tool-card">
                    <h3>📊 API Usage Today</h3>
                    <p>Track your Claude API usage and costs</p>
                    <div id="costTracker">
                        <div class="usage-stat">
                            <span class="usage-label">Generations:</span>
                            <span class="usage-value" id="generationCount">Loading...</span>
                        </div>
                        <div class="usage-stat">
                            <span class="usage-label">Cost Today:</span>
                            <span class="usage-value" id="costToday">Loading...</span>
                        </div>
                        <div class="usage-stat">
                            <span class="usage-label">Daily Limit:</span>
                            <span class="usage-value" id="dailyLimit">Loading...</span>
                        </div>
                    </div>
                    <button onclick="refreshUsage()" style="margin-top: 15px; font-size: 13px; padding: 8px 16px;">Refresh</button>
                </div>
            </div>

            <div class="nav-grid">
                <a href="/tools/reply-assistant/accounts" class="nav-card">
                    <h3>📱 Manage Accounts</h3>
                    <p>Add, remove, or pause monitored accounts from X, LinkedIn, and other platforms.</p>
                </a>

                <a href="/tools/reply-assistant/settings" class="nav-card">
                    <h3>⚙️ Filter Settings</h3>
                    <p>Configure keywords, engagement thresholds, and quality filters for notifications.</p>
                </a>

                <a href="/tools/reply-assistant/history" class="nav-card">
                    <h3>📊 Reply History</h3>
                    <p>View your posted replies, engagement metrics, and performance analytics.</p>
                </a>
            </div>
        </div>

        <script>
            // ============== Mobile Menu Toggle ==============
            const menuButton = document.getElementById('menu-button');
            const mobileMenu = document.getElementById('mobile-menu');
            const closeMenu = document.getElementById('close-menu');

            if (menuButton && mobileMenu) {
                menuButton.addEventListener('click', () => {
                    mobileMenu.classList.add('active');
                    document.body.style.overflow = 'hidden';
                });

                if (closeMenu) {
                    closeMenu.addEventListener('click', () => {
                        mobileMenu.classList.remove('active');
                        document.body.style.overflow = 'auto';
                    });
                }
            }

            // ============== Toast Notification System ==============
            function showToast(message, type = 'info', duration = 4000) {
                const container = document.getElementById('toastContainer');
                const toast = document.createElement('div');
                toast.className = `toast ${type}`;

                const icons = {
                    success: '✓',
                    error: '✕',
                    info: 'ℹ',
                    warning: '⚠'
                };

                toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
                container.appendChild(toast);

                // Auto-remove after duration
                setTimeout(() => {
                    toast.classList.add('hiding');
                    setTimeout(() => toast.remove(), 300);
                }, duration);
            }

            // ============== Loading State Helpers ==============
            function setButtonLoading(btn, loading) {
                if (loading) {
                    btn.classList.add('btn-loading');
                    btn.dataset.originalText = btn.innerHTML;
                    btn.innerHTML = '<span>' + btn.textContent + '</span>';
                    btn.disabled = true;
                } else {
                    btn.classList.remove('btn-loading');
                    btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
                    btn.disabled = false;
                }
            }

            // ============== Monitoring Status ==============
            async function refreshStatus() {
                const btn = document.getElementById('refreshBtn');
                setButtonLoading(btn, true);

                try {
                    const response = await fetch('/tools/reply-assistant/api/health');
                    const data = await response.json();

                    const indicator = document.getElementById('statusIndicator');
                    const label = document.getElementById('statusLabel');
                    const detail = document.getElementById('statusDetail');

                    if (data.status === 'healthy') {
                        indicator.className = 'status-indicator';
                        label.textContent = 'Monitoring Active';
                        detail.textContent = data.minutes_since_last_check
                            ? ` • Last check ${Math.round(data.minutes_since_last_check)} min ago`
                            : '';
                    } else if (data.status === 'warning') {
                        indicator.className = 'status-indicator paused';
                        label.textContent = 'Monitoring Delayed';
                        detail.textContent = ` • Last check ${Math.round(data.minutes_since_last_check)} min ago`;
                        showToast('Monitoring seems delayed. Check if the bot is running.', 'warning');
                    } else {
                        indicator.className = 'status-indicator offline';
                        label.textContent = 'Monitoring Offline';
                        detail.textContent = data.minutes_since_last_check
                            ? ` • Last check ${Math.round(data.minutes_since_last_check)} min ago`
                            : ' • No recent activity';
                    }

                } catch (error) {
                    document.getElementById('statusIndicator').className = 'status-indicator offline';
                    document.getElementById('statusLabel').textContent = 'Status Unknown';
                    document.getElementById('statusDetail').textContent = ' • Could not connect';
                } finally {
                    setButtonLoading(btn, false);
                }
            }

            // ============== Test AI Generation ==============
            async function testGeneration(event) {
                event.preventDefault();

                const btn = document.getElementById('testBtn');
                const result = document.getElementById('testResult');
                const postContent = document.getElementById('testPostContent').value;

                setButtonLoading(btn, true);
                result.style.display = 'none';

                try {
                    const response = await fetch('/tools/reply-assistant/api/test-generation', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ post_content: postContent })
                    });

                    const data = await response.json();

                    if (response.ok) {
                        result.className = '';
                        result.innerHTML = `
                            <div class="result-label">Quality Score</div>
                            <div class="result-value"><strong>${data.quality_score}/10</strong> - ${data.reasoning}</div>
                            <div class="result-label">Suggested Reply</div>
                            <div class="result-value">${data.suggested_reply}</div>
                            <div class="result-label">Cost</div>
                            <div class="result-value">${data.cost} (${data.tokens.input} in + ${data.tokens.output} out)</div>
                        `;
                        showToast('Reply generated successfully!', 'success');
                    } else {
                        result.className = 'error';
                        result.innerHTML = `<strong>Error:</strong> ${data.error || 'Failed to generate reply'}`;
                        showToast(data.error || 'Failed to generate reply', 'error');
                    }

                    result.style.display = 'block';

                    // Refresh usage stats
                    refreshUsage();

                } catch (error) {
                    result.className = 'error';
                    result.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    result.style.display = 'block';
                    showToast('Network error. Please try again.', 'error');
                } finally {
                    setButtonLoading(btn, false);
                }
            }

            // ============== Refresh Usage Statistics ==============
            async function refreshUsage() {
                try {
                    const response = await fetch('/tools/reply-assistant/api/usage-stats');
                    const data = await response.json();

                    if (response.ok) {
                        document.getElementById('generationCount').textContent = `${data.generations}/${data.daily_limit}`;
                        document.getElementById('costToday').textContent = data.cost;
                        document.getElementById('dailyLimit').textContent = `$${data.cost_limit}`;
                    } else {
                        document.getElementById('generationCount').textContent = 'Error';
                        document.getElementById('costToday').textContent = 'Error';
                        document.getElementById('dailyLimit').textContent = 'Error';
                    }
                } catch (error) {
                    console.error('Failed to fetch usage stats:', error);
                }
            }

            // ============== Toggle Monitoring (Pause/Resume) ==============
            let monitoringPaused = false;

            async function toggleMonitoring() {
                const btn = document.getElementById('toggleBtn');
                setButtonLoading(btn, true);

                try {
                    const response = await fetch('/tools/reply-assistant/api/toggle-monitoring', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });

                    const data = await response.json();

                    if (response.ok) {
                        monitoringPaused = data.paused;
                        updateToggleButton();
                        updateStatusIndicator();

                        if (data.paused) {
                            showToast('Monitoring paused. You will not receive new reply suggestions.', 'warning');
                        } else {
                            showToast('Monitoring resumed. You will receive new reply suggestions.', 'success');
                        }
                    } else {
                        showToast(data.error || 'Failed to toggle monitoring', 'error');
                    }
                } catch (error) {
                    showToast('Network error. Please try again.', 'error');
                } finally {
                    setButtonLoading(btn, false);
                }
            }

            function updateToggleButton() {
                const btn = document.getElementById('toggleBtn');
                if (monitoringPaused) {
                    btn.innerHTML = '<span>Resume Monitoring</span>';
                    btn.classList.add('btn-resume');
                } else {
                    btn.innerHTML = '<span>Pause Monitoring</span>';
                    btn.classList.remove('btn-resume');
                }
            }

            function updateStatusIndicator() {
                const indicator = document.getElementById('statusIndicator');
                const label = document.getElementById('statusLabel');
                const detail = document.getElementById('statusDetail');

                if (monitoringPaused) {
                    indicator.className = 'status-indicator paused';
                    label.textContent = 'Monitoring Paused';
                    detail.textContent = ' • Click Resume to restart';
                }
            }

            async function loadMonitoringStatus() {
                try {
                    const response = await fetch('/tools/reply-assistant/api/monitoring-status');
                    const data = await response.json();

                    if (response.ok) {
                        monitoringPaused = data.paused;
                        updateToggleButton();

                        // Show toggle button now that we have the status
                        document.getElementById('toggleBtn').style.display = 'inline-block';

                        if (monitoringPaused) {
                            updateStatusIndicator();
                        }
                    }
                } catch (error) {
                    console.error('Failed to load monitoring status:', error);
                }
            }

            // ============== Initialize on Page Load ==============
            window.addEventListener('DOMContentLoaded', () => {
                refreshUsage();
                refreshStatus();
                loadMonitoringStatus();

                // Auto-refresh status every 5 minutes
                setInterval(refreshStatus, 300000);
            });
        </script>
    </body>
    </html>
    """

    return render_template_string(html, user=user, stats=stats)

# ============================================
# ROUTE: Manage Accounts
# ============================================

@reply_assistant_bp.route('/accounts', methods=['GET', 'POST'])
def accounts():
    """Manage monitored accounts"""

    if 'user_discord_id' not in session:
        return redirect(url_for('reply_assistant.index'))

    user_discord_id = session['user_discord_id']

    conn = get_db_connection()
    if not conn:
        return "Database error", 500

    cursor = get_db_cursor(conn)

    # Handle POST (add account)
    if request.method == 'POST':
        platform = sanitize_input(request.form.get('platform'), strip_all=True)
        account_url = sanitize_input(request.form.get('account_url'), strip_all=True)

        if platform and account_url:
            # Parse account handle from URL
            account_handle = None

            if platform == 'x':
                # Extract from twitter.com/username or x.com/username
                if 'twitter.com/' in account_url or 'x.com/' in account_url:
                    account_handle = account_url.split('/')[-1].split('?')[0].replace('@', '')
            elif platform == 'linkedin':
                # Extract from linkedin.com/in/username
                if 'linkedin.com/in/' in account_url:
                    account_handle = account_url.split('/in/')[-1].split('?')[0].rstrip('/')

            if account_handle:
                try:
                    cursor.execute("""
                        INSERT INTO monitored_accounts
                        (user_discord_id, platform, account_url, account_handle)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            is_active = TRUE,
                            account_url = VALUES(account_url)
                    """, (user_discord_id, platform, account_url, account_handle))

                    conn.commit()
                except Exception as e:
                    print(f"Add account error: {e}")

    # Get all accounts
    cursor.execute("""
        SELECT * FROM monitored_accounts
        WHERE user_discord_id = %s
        ORDER BY added_at DESC
    """, (user_discord_id,))

    accounts_list = cursor.fetchall()

    cursor.close()
    conn.close()

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Manage Accounts - Reply Assistant</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                padding: 20px;
                color: #e6edf3;
            }
            .header {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }
            .header h1 {
                font-size: 28px;
                margin-bottom: 10px;
            }
            .header a {
                color: white;
                text-decoration: none;
                opacity: 0.9;
                font-size: 14px;
            }
            .header a:hover {
                opacity: 1;
            }
            .add-form {
                background: #161b22;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                margin-bottom: 30px;
                border: 1px solid #30363d;
            }
            .add-form h2 {
                margin-bottom: 20px;
                color: #e6edf3;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #8b949e;
                font-weight: 600;
            }
            .form-group select,
            .form-group input {
                width: 100%;
                padding: 12px;
                border: 2px solid #30363d;
                border-radius: 8px;
                font-size: 15px;
                background: #0d1117;
                color: #e6edf3;
            }
            .form-group select option {
                background: #161b22;
                color: #e6edf3;
            }
            .form-group input::placeholder {
                color: #8b949e;
            }
            .form-group select:focus,
            .form-group input:focus {
                outline: none;
                border-color: #58a6ff;
            }
            button {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, opacity 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                opacity: 0.9;
            }
            .accounts-list {
                background: #161b22;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                border: 1px solid #30363d;
            }
            .accounts-list h2 {
                margin-bottom: 20px;
                color: #e6edf3;
            }
            .account-item {
                padding: 20px;
                border: 2px solid #30363d;
                border-radius: 8px;
                margin-bottom: 15px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #0d1117;
            }
            .account-item.inactive {
                opacity: 0.5;
            }
            .account-info {
                flex: 1;
            }
            .account-info .platform {
                display: inline-block;
                padding: 4px 12px;
                background: #238636;
                color: white;
                border-radius: 4px;
                font-size: 12px;
                margin-bottom: 8px;
                text-transform: uppercase;
            }
            .account-info .handle {
                font-size: 18px;
                font-weight: 600;
                color: #e6edf3;
                margin-bottom: 5px;
            }
            .account-info .url {
                font-size: 13px;
                color: #8b949e;
            }
            .account-actions {
                display: flex;
                gap: 10px;
            }
            .account-actions button {
                padding: 8px 16px;
                font-size: 13px;
            }
            .btn-danger {
                background: linear-gradient(135deg, #da3633 0%, #f85149 100%);
            }
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: #8b949e;
            }
            .empty-state .icon {
                font-size: 64px;
                margin-bottom: 20px;
            }
            .empty-state h3 {
                color: #e6edf3;
                margin-bottom: 10px;
            }
            .empty-state p {
                margin-bottom: 20px;
                line-height: 1.6;
            }
            .empty-state .hint {
                font-size: 13px;
                padding: 15px;
                background: #21262d;
                border-radius: 8px;
                border: 1px solid #30363d;
                text-align: left;
                max-width: 400px;
                margin: 0 auto;
            }
            /* Toast Notifications */
            .toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
            }
            .toast {
                padding: 14px 20px;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                margin-bottom: 10px;
                animation: slideIn 0.3s ease;
            }
            .toast.success { background: linear-gradient(135deg, #238636 0%, #2ea043 100%); }
            .toast.error { background: linear-gradient(135deg, #da3633 0%, #f85149 100%); }
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            /* Loading state */
            .btn-loading {
                opacity: 0.7;
                pointer-events: none;
            }
        </style>
    </head>
    <body>
        <div class="toast-container" id="toastContainer"></div>

        <div class="header">
            <h1>📱 Manage Accounts</h1>
            <a href="/tools/reply-assistant/dashboard">← Back to Dashboard</a>
        </div>

        <div class="add-form">
            <h2>Add New Account</h2>
            <form method="POST">
                <div class="form-group">
                    <label>Platform</label>
                    <select name="platform" required>
                        <option value="">Select platform...</option>
                        <option value="x">X (Twitter)</option>
                        <option value="linkedin">LinkedIn</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Account URL</label>
                    <input type="url" name="account_url" placeholder="https://twitter.com/username or https://linkedin.com/in/username" required>
                </div>

                <button type="submit">Add Account</button>
            </form>
        </div>

        <div class="accounts-list">
            <h2>Monitored Accounts ({{ accounts|length }})</h2>

            {% if accounts %}
                {% for account in accounts %}
                <div class="account-item {% if not account.is_active %}inactive{% endif %}">
                    <div class="account-info">
                        <span class="platform">{{ account.platform }}</span>
                        <div class="handle">@{{ account.account_handle }}</div>
                        <div class="url">{{ account.account_url }}</div>
                    </div>

                    <div class="account-actions">
                        <form method="POST" action="/tools/reply-assistant/accounts/toggle/{{ account.id }}" style="display:inline;">
                            {% if account.is_active %}
                            <button type="submit">Pause</button>
                            {% else %}
                            <button type="submit">Resume</button>
                            {% endif %}
                        </form>

                        <form method="POST" action="/tools/reply-assistant/accounts/delete/{{ account.id }}" style="display:inline;">
                            <button type="submit" class="btn-danger" onclick="return confirm('Delete this account?')">Delete</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <h3>No Accounts Yet</h3>
                    <p>Start monitoring X accounts to get AI-powered reply suggestions.</p>
                    <div class="hint">
                        <strong>How it works:</strong><br>
                        1. Add an X account URL above<br>
                        2. The bot monitors for new posts<br>
                        3. Get AI reply suggestions via Discord<br>
                        4. Approve and post with one click
                    </div>
                </div>
            {% endif %}
        </div>

        <script>
            // Show toast on successful add (check URL params)
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('added')) {
                showToast('Account added successfully!', 'success');
            }
            if (urlParams.get('deleted')) {
                showToast('Account removed', 'success');
            }

            function showToast(message, type) {
                const container = document.getElementById('toastContainer');
                const toast = document.createElement('div');
                toast.className = 'toast ' + type;
                toast.textContent = message;
                container.appendChild(toast);
                setTimeout(() => toast.remove(), 4000);
            }
        </script>
    </body>
    </html>
    """

    return render_template_string(html, accounts=accounts_list)

@reply_assistant_bp.route('/accounts/toggle/<int:account_id>', methods=['POST'])
def toggle_account(account_id):
    """Toggle account active status"""

    if 'user_discord_id' not in session:
        return redirect(url_for('reply_assistant.index'))

    user_discord_id = session['user_discord_id']

    conn = get_db_connection()
    if conn:
        cursor = get_db_cursor(conn)

        cursor.execute("""
            UPDATE monitored_accounts
            SET is_active = NOT is_active
            WHERE id = %s AND user_discord_id = %s
        """, (account_id, user_discord_id))

        conn.commit()
        cursor.close()
        conn.close()

    return redirect(url_for('reply_assistant.accounts'))

@reply_assistant_bp.route('/accounts/delete/<int:account_id>', methods=['POST'])
def delete_account(account_id):
    """Delete account"""

    if 'user_discord_id' not in session:
        return redirect(url_for('reply_assistant.index'))

    user_discord_id = session['user_discord_id']

    conn = get_db_connection()
    if conn:
        cursor = get_db_cursor(conn)

        cursor.execute("""
            DELETE FROM monitored_accounts
            WHERE id = %s AND user_discord_id = %s
        """, (account_id, user_discord_id))

        conn.commit()
        cursor.close()
        conn.close()

    return redirect(url_for('reply_assistant.accounts'))

# ============================================
# ROUTE: Settings
# ============================================

@reply_assistant_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Filter settings"""

    if 'user_discord_id' not in session:
        return redirect(url_for('reply_assistant.index'))

    user_discord_id = session['user_discord_id']

    conn = get_db_connection()
    if not conn:
        return "Database error", 500

    cursor = get_db_cursor(conn)

    # Handle POST
    if request.method == 'POST':
        keywords_include = sanitize_input(request.form.get('keywords_include', ''), strip_all=True)
        keywords_exclude = sanitize_input(request.form.get('keywords_exclude', ''), strip_all=True)
        min_likes = int(request.form.get('min_likes', 10))
        min_quality_score = int(request.form.get('min_quality_score', 5))
        max_notifications_per_day = int(request.form.get('max_notifications_per_day', 20))

        # Convert keywords to JSON arrays
        keywords_include_list = [sanitize_input(k.strip(), strip_all=True) for k in keywords_include.split(',') if k.strip()]
        keywords_exclude_list = [sanitize_input(k.strip(), strip_all=True) for k in keywords_exclude.split(',') if k.strip()]

        cursor.execute("""
            UPDATE filter_settings
            SET keywords_include = %s,
                keywords_exclude = %s,
                min_likes = %s,
                min_quality_score = %s,
                max_notifications_per_day = %s
            WHERE user_discord_id = %s
        """, (
            json.dumps(keywords_include_list),
            json.dumps(keywords_exclude_list),
            min_likes,
            min_quality_score,
            max_notifications_per_day,
            user_discord_id
        ))

        conn.commit()

    # Get current settings
    cursor.execute("""
        SELECT * FROM filter_settings
        WHERE user_discord_id = %s
    """, (user_discord_id,))

    filter_settings = cursor.fetchone()

    cursor.close()
    conn.close()

    # Convert JSON to strings
    keywords_include_str = ''
    keywords_exclude_str = ''

    if filter_settings:
        if filter_settings['keywords_include']:
            keywords_include_str = ', '.join(json.loads(filter_settings['keywords_include']))
        if filter_settings['keywords_exclude']:
            keywords_exclude_str = ', '.join(json.loads(filter_settings['keywords_exclude']))

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Filter Settings - Reply Assistant</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                padding: 20px;
                color: #e6edf3;
            }
            .header {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }
            .header h1 {
                font-size: 28px;
                margin-bottom: 10px;
            }
            .header a {
                color: white;
                text-decoration: none;
                opacity: 0.9;
                font-size: 14px;
            }
            .header a:hover {
                opacity: 1;
            }
            .settings-form {
                background: #161b22;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                max-width: 800px;
                border: 1px solid #30363d;
            }
            .form-section {
                margin-bottom: 40px;
            }
            .form-section:last-child {
                margin-bottom: 0;
            }
            .form-section h2 {
                color: #e6edf3;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #30363d;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #8b949e;
                font-weight: 600;
            }
            .form-group input,
            .form-group textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #30363d;
                border-radius: 8px;
                font-size: 15px;
                background: #0d1117;
                color: #e6edf3;
            }
            .form-group input::placeholder,
            .form-group textarea::placeholder {
                color: #8b949e;
            }
            .form-group input:focus,
            .form-group textarea:focus {
                outline: none;
                border-color: #58a6ff;
            }
            .form-group textarea {
                min-height: 100px;
                font-family: inherit;
            }
            .form-group .hint {
                margin-top: 5px;
                font-size: 13px;
                color: #8b949e;
            }
            button {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                border: none;
                padding: 14px 32px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, opacity 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                opacity: 0.9;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚙️ Filter Settings</h1>
            <a href="/tools/reply-assistant/dashboard">← Back to Dashboard</a>
        </div>

        <form method="POST" class="settings-form">
            <div class="form-section">
                <h2>Keyword Filters</h2>

                <div class="form-group">
                    <label>Include Keywords (comma-separated)</label>
                    <textarea name="keywords_include" placeholder="web3, blockchain, crypto">{{ keywords_include }}</textarea>
                    <div class="hint">Only notify for posts containing these keywords (leave empty for all posts)</div>
                </div>

                <div class="form-group">
                    <label>Exclude Keywords (comma-separated)</label>
                    <textarea name="keywords_exclude" placeholder="spam, scam">{{ keywords_exclude }}</textarea>
                    <div class="hint">Never notify for posts containing these keywords</div>
                </div>
            </div>

            <div class="form-section">
                <h2>Engagement Filters</h2>

                <div class="form-group">
                    <label>Minimum Likes</label>
                    <input type="number" name="min_likes" value="{{ settings.min_likes }}" min="0">
                    <div class="hint">Only notify for posts with at least this many likes</div>
                </div>
            </div>

            <div class="form-section">
                <h2>Quality Filters</h2>

                <div class="form-group">
                    <label>Minimum Quality Score (1-10)</label>
                    <input type="number" name="min_quality_score" value="{{ settings.min_quality_score }}" min="1" max="10">
                    <div class="hint">AI quality score threshold for generated replies</div>
                </div>

                <div class="form-group">
                    <label>Max Notifications Per Day</label>
                    <input type="number" name="max_notifications_per_day" value="{{ settings.max_notifications_per_day }}" min="1">
                    <div class="hint">Maximum Discord notifications you'll receive daily</div>
                </div>
            </div>

            <button type="submit">Save Settings</button>
        </form>
    </body>
    </html>
    """

    return render_template_string(
        html,
        settings=filter_settings or {},
        keywords_include=keywords_include_str,
        keywords_exclude=keywords_exclude_str
    )

# ============================================
# ROUTE: Reply History
# ============================================

@reply_assistant_bp.route('/history')
def history():
    """Reply history"""

    if 'user_discord_id' not in session:
        return redirect(url_for('reply_assistant.index'))

    user_discord_id = session['user_discord_id']

    conn = get_db_connection()
    if not conn:
        return "Database error", 500

    cursor = get_db_cursor(conn)

    cursor.execute("""
        SELECT * FROM reply_history
        WHERE user_discord_id = %s
        ORDER BY posted_at DESC
        LIMIT 100
    """, (user_discord_id,))

    history_list = cursor.fetchall()

    cursor.close()
    conn.close()

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reply History - Reply Assistant</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0d1117;
                padding: 20px;
                color: #e6edf3;
            }
            .header {
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }
            .header h1 {
                font-size: 28px;
                margin-bottom: 10px;
            }
            .header a {
                color: white;
                text-decoration: none;
                opacity: 0.9;
                font-size: 14px;
            }
            .header a:hover {
                opacity: 1;
            }
            .history-list {
                background: #161b22;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                border: 1px solid #30363d;
            }
            .history-item {
                padding: 20px;
                border: 2px solid #30363d;
                border-radius: 8px;
                margin-bottom: 15px;
                background: #0d1117;
            }
            .history-item .platform {
                display: inline-block;
                padding: 4px 12px;
                background: #238636;
                color: white;
                border-radius: 4px;
                font-size: 12px;
                margin-bottom: 10px;
                text-transform: uppercase;
            }
            .history-item .content {
                color: #e6edf3;
                line-height: 1.6;
                margin-bottom: 15px;
            }
            .history-item .meta {
                display: flex;
                justify-content: space-between;
                color: #8b949e;
                font-size: 13px;
            }
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: #8b949e;
            }
            .empty-state .icon {
                font-size: 64px;
                margin-bottom: 20px;
            }
            .empty-state h3 {
                color: #e6edf3;
                margin-bottom: 10px;
            }
            .empty-state p {
                margin-bottom: 20px;
                line-height: 1.6;
            }
            .empty-state .steps {
                font-size: 13px;
                padding: 15px;
                background: #21262d;
                border-radius: 8px;
                border: 1px solid #30363d;
                text-align: left;
                max-width: 350px;
                margin: 0 auto;
            }
            .empty-state .steps a {
                color: #58a6ff;
                text-decoration: none;
            }
            .empty-state .steps a:hover {
                text-decoration: underline;
            }
            .stats-summary {
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            .stat-pill {
                background: #21262d;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 13px;
                border: 1px solid #30363d;
            }
            .stat-pill strong {
                color: #58a6ff;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Reply History</h1>
            <a href="/tools/reply-assistant/dashboard">← Back to Dashboard</a>
        </div>

        <div class="history-list">
            {% if history %}
                <div class="stats-summary">
                    <div class="stat-pill"><strong>{{ history|length }}</strong> replies posted</div>
                </div>
                {% for item in history %}
                <div class="history-item">
                    <span class="platform">{{ item.platform }}</span>
                    <div class="content">{{ item.reply_content }}</div>
                    <div class="meta">
                        <span>{{ item.posted_at.strftime('%Y-%m-%d %H:%M') }}</span>
                        <span>❤️ {{ item.likes_received or 0 }} | 💬 {{ item.replies_received or 0 }}</span>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <div class="icon">📝</div>
                    <h3>No Replies Yet</h3>
                    <p>Your posted replies will appear here with engagement metrics.</p>
                    <div class="steps">
                        <strong>Get started:</strong><br>
                        1. <a href="/tools/reply-assistant/accounts">Add accounts to monitor</a><br>
                        2. Wait for the bot to find new posts<br>
                        3. Approve replies via Discord<br>
                        4. Track your engagement here
                    </div>
                </div>
            {% endif %}
        </div>
    </body>
    </html>
    """

    return render_template_string(html, history=history_list)

# ============================================
# API: Test AI Generation
# ============================================

@reply_assistant_bp.route('/api/test-generation', methods=['POST'])
@limiter.limit("10 per hour")
def test_generation():
    """Test AI reply generation without waiting for monitoring cycle"""

    if 'user_discord_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_discord_id = session['user_discord_id']

    # Check rate limit
    allowed, error_msg = check_rate_limit(user_discord_id)
    if not allowed:
        return jsonify({'error': error_msg}), 429

    data = request.get_json()
    post_content = sanitize_input(data.get('post_content', ''), strip_all=True)

    if not post_content or len(post_content) < 10:
        return jsonify({'error': 'Post content too short (minimum 10 characters)'}), 400

    try:
        # Generate reply using Claude
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        prompt = f"""You are a social media engagement expert. Generate a thoughtful, engaging reply to this post:

"{post_content}"

Requirements:
- Maximum 280 characters for X/Twitter (shorter is better)
- Professional yet friendly tone
- Add value to the conversation
- Avoid generic responses like "Great post!" or "Thanks for sharing"
- Be authentic and specific

Also provide:
1. Quality score (1-10) based on relevance, value-add, and engagement potential
2. Brief reasoning for the score

Format your response as JSON:
{{
    "reply": "your reply text here",
    "quality_score": 8,
    "reasoning": "why this reply is valuable"
}}"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            reply_data = json.loads(json_match.group())
        else:
            reply_data = {
                'reply': response_text[:280],
                'quality_score': 5,
                'reasoning': 'Generated reply'
            }

        # Calculate cost
        usage = message.usage
        INPUT_COST_PER_1M = 3.00
        OUTPUT_COST_PER_1M = 15.00
        input_cost = (usage.input_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (usage.output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        total_cost = input_cost + output_cost

        # Increment usage counter
        increment_usage(user_discord_id)

        return jsonify({
            'success': True,
            'quality_score': reply_data['quality_score'],
            'reasoning': reply_data['reasoning'],
            'suggested_reply': reply_data['reply'],
            'cost': f"${total_cost:.4f}",
            'tokens': {
                'input': usage.input_tokens,
                'output': usage.output_tokens
            }
        })

    except Exception as e:
        logger.error(f"Test generation failed: {e}", exc_info=True)
        return jsonify({'error': 'Generation failed. Please try again.'}), 500


# ============================================
# API: Generate Reply (used by Discord bot)
# ============================================

@reply_assistant_bp.route('/api/generate-reply', methods=['POST'])
@limiter.limit("100 per hour")
def api_generate_reply():
    """Generate AI reply for a post"""

    data = request.get_json()

    if not data or 'post_content' not in data or 'user_discord_id' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    user_discord_id = data['user_discord_id']
    post_content = sanitize_input(data['post_content'], strip_all=True)
    platform = sanitize_input(data.get('platform', 'x'), strip_all=True)

    # Check rate limit
    allowed, error_msg = check_rate_limit(user_discord_id)
    if not allowed:
        return jsonify({'error': error_msg}), 429

    try:
        # Generate reply using Claude
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        prompt = f"""You are a social media engagement expert. Generate a thoughtful, engaging reply to this {platform} post:

"{post_content}"

Requirements:
- Maximum 280 characters for X/Twitter (shorter is better)
- Professional yet friendly tone
- Add value to the conversation
- Avoid generic responses like "Great post!" or "Thanks for sharing"
- Be authentic and specific

Also provide:
1. Quality score (1-10) based on relevance, value-add, and engagement potential
2. Brief reasoning for the score

Format your response as JSON:
{{
    "reply": "your reply text here",
    "quality_score": 8,
    "reasoning": "why this reply is valuable"
}}"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            reply_data = json.loads(json_match.group())
        else:
            reply_data = {
                'reply': response_text[:280],
                'quality_score': 5,
                'reasoning': 'Generated reply'
            }

        # Increment usage
        increment_usage(user_discord_id)

        return jsonify(reply_data), 200

    except Exception as e:
        print(f"AI generation error: {e}")
        return jsonify({'error': 'Failed to generate reply'}), 500

# ============================================
# API: Health Check
# ============================================

@reply_assistant_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'database': 'error',
                'message': 'Database connection failed'
            }), 500

        cursor = get_db_cursor(conn)

        # Check last monitoring cycle
        cursor.execute("""
            SELECT MAX(last_checked_at) as last_check
            FROM monitored_accounts
        """)

        result = cursor.fetchone()
        last_check = result['last_check'] if result else None

        # Calculate time since last check
        minutes_since = None
        bot_status = "unknown"

        if last_check:
            time_diff = datetime.now() - last_check
            minutes_since = time_diff.total_seconds() / 60

            # Determine bot status based on last check
            if minutes_since < 60:  # Less than 1 hour
                bot_status = "healthy"
            elif minutes_since < 180:  # Less than 3 hours
                bot_status = "warning"
            else:
                bot_status = "offline"

        cursor.close()
        conn.close()

        return jsonify({
            'status': bot_status,
            'database': 'connected',
            'last_check': last_check.isoformat() if last_check else None,
            'minutes_since_last_check': round(minutes_since, 1) if minutes_since else None,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'database': 'error',
            'message': str(e)
        }), 500

# ============================================
# API: Usage Stats
# ============================================

@reply_assistant_bp.route('/api/usage-stats', methods=['GET'])
def usage_stats():
    """Get current API usage statistics"""
    try:
        import os
        import json
        from datetime import datetime

        usage_file = 'logs/usage.json'

        # Default values
        default_stats = {
            'generations': 0,
            'cost': '$0.0000',
            'daily_limit': int(os.getenv('DAILY_AI_LIMIT', 1000)),
            'cost_limit': float(os.getenv('AI_COST_LIMIT', 5.0))
        }

        # Read usage file if exists
        if os.path.exists(usage_file):
            try:
                with open(usage_file, 'r') as f:
                    usage_data = json.load(f)

                # Check if data is from today
                today = datetime.now().date().isoformat()
                if usage_data.get('date') == today:
                    return jsonify({
                        'generations': usage_data.get('generations', 0),
                        'cost': f"${usage_data.get('cost', 0):.4f}",
                        'daily_limit': default_stats['daily_limit'],
                        'cost_limit': default_stats['cost_limit']
                    })
            except Exception as e:
                logger.error(f"Error reading usage file: {e}")

        # Return defaults if no data or old data
        return jsonify(default_stats)

    except Exception as e:
        logger.error(f"Usage stats error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch usage stats'}), 500


# ============================================
# API: Post Reply (used by Discord bot)
# ============================================

# ============================================
# API: Toggle Monitoring (Pause/Resume)
# ============================================

# Store monitoring state per user (file-based for persistence)
MONITORING_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'logs', 'monitoring_state.json')

def load_monitoring_state():
    """Load monitoring state from file"""
    try:
        if os.path.exists(MONITORING_STATE_FILE):
            with open(MONITORING_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load monitoring state: {e}")
    return {}

def save_monitoring_state(state):
    """Save monitoring state to file"""
    try:
        os.makedirs(os.path.dirname(MONITORING_STATE_FILE), exist_ok=True)
        with open(MONITORING_STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"Could not save monitoring state: {e}")

def is_monitoring_paused(user_discord_id):
    """Check if monitoring is paused for a user"""
    state = load_monitoring_state()
    return state.get(str(user_discord_id), {}).get('paused', False)

@reply_assistant_bp.route('/api/toggle-monitoring', methods=['POST'])
def toggle_monitoring():
    """Toggle monitoring pause/resume for current user"""

    if 'user_discord_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_discord_id = str(session['user_discord_id'])

    try:
        state = load_monitoring_state()

        # Get current state for this user
        user_state = state.get(user_discord_id, {'paused': False})

        # Toggle the paused state
        new_paused = not user_state.get('paused', False)

        state[user_discord_id] = {
            'paused': new_paused,
            'updated_at': datetime.now().isoformat()
        }

        save_monitoring_state(state)

        logger.info(f"User {user_discord_id} {'paused' if new_paused else 'resumed'} monitoring")

        return jsonify({
            'success': True,
            'paused': new_paused,
            'message': 'Monitoring paused' if new_paused else 'Monitoring resumed'
        })

    except Exception as e:
        logger.error(f"Toggle monitoring error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to toggle monitoring'}), 500


@reply_assistant_bp.route('/api/monitoring-status', methods=['GET'])
def get_monitoring_status():
    """Get monitoring status for current user"""

    if 'user_discord_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_discord_id = str(session['user_discord_id'])

    try:
        paused = is_monitoring_paused(user_discord_id)

        return jsonify({
            'paused': paused,
            'status': 'paused' if paused else 'active'
        })

    except Exception as e:
        logger.error(f"Get monitoring status error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get status'}), 500


@reply_assistant_bp.route('/api/post-reply', methods=['POST'])
@limiter.limit("100 per hour")
def api_post_reply():
    """Post reply to social media platform"""

    data = request.get_json()

    if not data or 'pending_id' not in data:
        return jsonify({'error': 'Missing pending_id'}), 400

    pending_id = data['pending_id']

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500

    cursor = get_db_cursor(conn)

    # Get pending reply
    cursor.execute("""
        SELECT * FROM pending_replies
        WHERE id = %s
    """, (pending_id,))

    pending = cursor.fetchone()

    if not pending:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Pending reply not found'}), 404

    # Use edited reply if available, otherwise use suggested
    reply_text = pending['edited_reply'] if pending['edited_reply'] else pending['suggested_reply']

    # TODO: Implement actual posting to X/LinkedIn
    # For now, just mark as posted and save to history

    try:
        # Mark as posted
        cursor.execute("""
            UPDATE pending_replies
            SET status = 'posted',
                posted_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (pending_id,))

        # Save to history
        cursor.execute("""
            INSERT INTO reply_history
            (user_discord_id, platform, original_post_url, reply_content)
            VALUES (%s, %s, %s, %s)
        """, (
            pending['user_discord_id'],
            pending['platform'],
            pending['post_url'],
            reply_text
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Reply posted successfully'}), 200

    except Exception as e:
        print(f"Post reply error: {e}")
        cursor.close()
        conn.close()
        return jsonify({'error': 'Failed to post reply'}), 500
