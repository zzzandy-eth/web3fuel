"""
Reply Assistant Discord Bot + Monitor
Runs continuously to monitor accounts and send Discord notifications
"""

import discord
from discord import app_commands
from discord.ui import Button, View, TextInput, Modal
import asyncio
import os
import sys
import mysql.connector
from datetime import datetime, timedelta
import json
import anthropic
from dotenv import load_dotenv
import logging
import signal

# Add parent directory to path to import feed_monitor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from backend.services.feed_monitor import FeedMonitor, PLATFORM_HANDLERS

# Monitoring state file (shared with web app)
MONITORING_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'logs', 'monitoring_state.json')

def is_monitoring_paused(user_discord_id):
    """Check if monitoring is paused for a user"""
    try:
        if os.path.exists(MONITORING_STATE_FILE):
            with open(MONITORING_STATE_FILE, 'r') as f:
                state = json.load(f)
                return state.get(str(user_discord_id), {}).get('paused', False)
    except Exception as e:
        logging.warning(f"Could not check monitoring state: {e}")
    return False

# Load environment variables
load_dotenv()

# Setup comprehensive logging with UTF-8 encoding
os.makedirs('logs', exist_ok=True)

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
X_BEARER_TOKEN = os.getenv('X_BEARER_TOKEN')
CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', 720))  # Default: 12 hours
MIN_QUALITY_SCORE = int(os.getenv('MIN_QUALITY_SCORE', 5))

# Claude API Usage Limits
DAILY_AI_LIMIT = int(os.getenv('DAILY_AI_LIMIT', 1000))  # Max generations per day
AI_COST_LIMIT = float(os.getenv('AI_COST_LIMIT', 5.0))  # Max cost per day in USD

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# Initialize database connection pool
try:
    from mysql.connector import pooling
    db_pool = pooling.MySQLConnectionPool(
        pool_name="monitor_pool",
        pool_size=5,
        pool_reset_session=True,
        **DB_CONFIG
    )
    logger.info("✓ Database connection pool initialized")
except Exception as e:
    logger.error(f"Failed to create database connection pool: {e}")
    db_pool = None

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Initialize services
feed_monitor = FeedMonitor()
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)


# Claude API Usage Tracker
class UsageTracker:
    """Track daily Claude API usage and enforce limits"""

    def __init__(self):
        self.usage_file = 'logs/usage.json'
        self.date = datetime.now().date().isoformat()
        self.generations = 0
        self.cost = 0.0
        self.load_usage()

    def load_usage(self):
        """Load usage from file"""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)

                    # Reset if new day
                    if data.get('date') != self.date:
                        logger.info("New day detected - resetting usage counters")
                        self.reset_usage()
                    else:
                        self.generations = data.get('generations', 0)
                        self.cost = data.get('cost', 0.0)
                        logger.info(f"Loaded usage: {self.generations} generations, ${self.cost:.2f}")
        except Exception as e:
            logger.error(f"Error loading usage data: {e}")
            self.reset_usage()

    def reset_usage(self):
        """Reset daily counters"""
        self.date = datetime.now().date().isoformat()
        self.generations = 0
        self.cost = 0.0
        self.save_usage()

    def check_new_day(self):
        """Check if new day and reset if needed"""
        current_date = datetime.now().date().isoformat()
        if current_date != self.date:
            logger.info(f"New day detected: {current_date}")
            self.reset_usage()
            return True
        return False

    def can_generate(self):
        """Check if we can generate more replies"""
        self.check_new_day()

        if self.generations >= DAILY_AI_LIMIT:
            logger.warning(f"Daily generation limit reached: {DAILY_AI_LIMIT}")
            return False

        if self.cost >= AI_COST_LIMIT:
            logger.warning(f"Daily cost limit reached: ${AI_COST_LIMIT}")
            return False

        return True

    def calculate_cost(self, input_tokens, output_tokens):
        """Calculate cost for Claude API call"""
        # Claude 3.5 Sonnet pricing (as of 2024)
        INPUT_COST_PER_1M = 3.00  # $3 per million input tokens
        OUTPUT_COST_PER_1M = 15.00  # $15 per million output tokens

        input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        total_cost = input_cost + output_cost

        return total_cost

    def record_usage(self, input_tokens, output_tokens):
        """Record generation and cost"""
        cost = self.calculate_cost(input_tokens, output_tokens)

        self.generations += 1
        self.cost += cost

        logger.info(f"Usage recorded: Generation {self.generations}/{DAILY_AI_LIMIT}, "
                   f"Cost ${self.cost:.4f}/${AI_COST_LIMIT} (+${cost:.4f})")

        self.save_usage()

    def save_usage(self):
        """Save usage to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump({
                    'date': self.date,
                    'generations': self.generations,
                    'cost': round(self.cost, 4)
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")

    def get_remaining(self):
        """Get remaining generations and budget"""
        return {
            'generations_remaining': DAILY_AI_LIMIT - self.generations,
            'cost_remaining': round(AI_COST_LIMIT - self.cost, 2),
            'generations_used': self.generations,
            'cost_used': round(self.cost, 2)
        }


# Initialize usage tracker
usage_tracker = UsageTracker()


def get_db_connection():
    """Get database connection from pool"""
    try:
        if db_pool:
            return db_pool.get_connection()
        else:
            # Fallback to direct connection if pool failed
            return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        logger.error(f"Database connection error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected database connection error: {e}", exc_info=True)
        return None


def get_db_cursor(conn):
    """Get database cursor with dict results"""
    return conn.cursor(dictionary=True)


def get_all_active_users():
    """Get all users with active monitoring"""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT DISTINCT u.*
            FROM users u
            INNER JOIN monitored_accounts ma ON u.discord_id = ma.user_discord_id
            WHERE u.is_active = TRUE
            AND ma.is_active = TRUE
        """)

        users = cursor.fetchall()
        return users

    except Exception as e:
        logger.error(f"Error fetching users: {e}", exc_info=True)
        return []
    finally:
        cursor.close()
        conn.close()


def get_filter_settings(user_discord_id):
    """Get user's filter settings"""
    conn = get_db_connection()
    if not conn:
        return {}

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT * FROM filter_settings
            WHERE user_discord_id = %s
        """, (user_discord_id,))

        settings = cursor.fetchone()

        if settings:
            # Parse JSON fields
            if settings['keywords_include']:
                settings['keywords_include'] = json.loads(settings['keywords_include'])
            if settings['keywords_exclude']:
                settings['keywords_exclude'] = json.loads(settings['keywords_exclude'])

        return settings or {}

    except Exception as e:
        logger.error(f"Error fetching filter settings: {e}", exc_info=True)
        return {}
    finally:
        cursor.close()
        conn.close()


def get_monitored_accounts(user_discord_id):
    """Get user's monitored accounts"""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT * FROM monitored_accounts
            WHERE user_discord_id = %s
            AND is_active = TRUE
        """, (user_discord_id,))

        accounts = cursor.fetchall()
        return accounts

    except Exception as e:
        logger.error(f"Error fetching accounts: {e}", exc_info=True)
        return []
    finally:
        cursor.close()
        conn.close()


def update_last_checked(account_id, last_post_id=None):
    """Update account's last checked timestamp and post ID"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = get_db_cursor(conn)

    try:
        if last_post_id:
            cursor.execute("""
                UPDATE monitored_accounts
                SET last_checked_at = CURRENT_TIMESTAMP,
                    last_post_id = %s
                WHERE id = %s
            """, (last_post_id, account_id))
        else:
            cursor.execute("""
                UPDATE monitored_accounts
                SET last_checked_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (account_id,))

        conn.commit()

    except Exception as e:
        logger.error(f"Error updating last checked: {e}", exc_info=True)
    finally:
        cursor.close()
        conn.close()


def check_daily_notification_limit(user_discord_id, max_notifications):
    """Check if user has reached daily notification limit"""
    conn = get_db_connection()
    if not conn:
        return False

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM pending_replies
            WHERE user_discord_id = %s
            AND DATE(created_at) = CURDATE()
        """, (user_discord_id,))

        result = cursor.fetchone()
        count = result['count'] if result else 0

        return count < max_notifications

    except Exception as e:
        logger.error(f"Error checking notification limit: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def is_duplicate_post(user_discord_id, post_id):
    """Check if post has already been processed for this user"""
    conn = get_db_connection()
    if not conn:
        return False

    cursor = get_db_cursor(conn)

    try:
        # Check if post_id exists in pending_replies or reply_history
        cursor.execute("""
            SELECT COUNT(*) as count FROM (
                SELECT 1 FROM pending_replies
                WHERE user_discord_id = %s AND post_id = %s
                UNION
                SELECT 1 FROM reply_history
                WHERE user_discord_id = %s AND original_post_url LIKE %s
            ) as duplicates
        """, (user_discord_id, post_id, user_discord_id, f'%{post_id}%'))

        result = cursor.fetchone()
        count = result['count'] if result else 0

        if count > 0:
            logger.info(f"    Skipping duplicate post {post_id}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking duplicate post: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def generate_reply_with_quality(post_content, platform='x'):
    """Generate AI reply with quality score using Claude"""

    try:
        prompt = f"""You are a blockchain/web3 enthusiast networking in the crypto space. Generate a thoughtful, engaging reply to this {platform} post:

"{post_content}"

CONTEXT: You're building relationships in the blockchain/web3 industry. Your replies should position you as knowledgeable about cross-chain infrastructure, DeFi, and blockchain technology - someone worth connecting with.

Requirements:
- Maximum 280 characters for X/Twitter (shorter is better)
- Sound like a real human, not an AI or marketing account
- NO emojis whatsoever
- Add genuine value, insight, or a thoughtful question
- Avoid generic responses like "Great post!", "This is the way", or "Thanks for sharing"
- Be authentic and specific to what was said
- Build rapport that opens doors for future collaboration

Also provide:
1. Quality score (1-10) based on how human it sounds and networking potential
2. Brief reasoning for the score

Format your response as JSON:
{{
    "reply": "your reply text here",
    "quality_score": 8,
    "reasoning": "why this reply is valuable"
}}"""

        message = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
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

        # Record usage
        usage = message.usage
        usage_tracker.record_usage(usage.input_tokens, usage.output_tokens)

        # Add usage info to reply data
        reply_data['usage'] = {
            'input_tokens': usage.input_tokens,
            'output_tokens': usage.output_tokens,
            'cost': usage_tracker.calculate_cost(usage.input_tokens, usage.output_tokens)
        }

        return reply_data

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}", exc_info=True)
        return {
            'reply': 'Interesting perspective! I would love to hear more about this.',
            'quality_score': 5,
            'reasoning': 'Fallback reply due to API error',
            'usage': {'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0}
        }
    except Exception as e:
        logger.error(f"AI generation error: {e}", exc_info=True)
        return {
            'reply': 'Interesting perspective! I would love to hear more about this.',
            'quality_score': 5,
            'reasoning': 'Fallback reply due to generation error',
            'usage': {'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0}
        }


def save_pending_reply(user_discord_id, post, reply_data):
    """Save pending reply to database"""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            INSERT INTO pending_replies
            (user_discord_id, platform, post_url, post_id, post_content,
             post_author, post_author_handle, likes_count, replies_count,
             engagement_score, suggested_reply, quality_score, reasoning)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                suggested_reply = VALUES(suggested_reply),
                quality_score = VALUES(quality_score),
                reasoning = VALUES(reasoning)
        """, (
            user_discord_id,
            post.get('platform', 'x'),
            post['post_url'],
            post['post_id'],
            post['content'],
            post['author'],
            post['author_handle'],
            post['likes_count'],
            post['replies_count'],
            post['engagement_score'],
            reply_data['reply'],
            reply_data['quality_score'],
            reply_data['reasoning']
        ))

        conn.commit()
        pending_id = cursor.lastrowid

        logger.info(f"Saved pending reply ID {pending_id} for user {user_discord_id}")
        return pending_id

    except mysql.connector.Error as e:
        logger.error(f"Database error saving pending reply: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error saving pending reply: {e}", exc_info=True)
        return None
    finally:
        cursor.close()
        conn.close()


def update_pending_reply(pending_id, discord_message_id, discord_channel_id):
    """Update pending reply with Discord message info"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            UPDATE pending_replies
            SET discord_message_id = %s,
                discord_channel_id = %s
            WHERE id = %s
        """, (discord_message_id, discord_channel_id, pending_id))

        conn.commit()
        logger.info(f"Updated pending reply {pending_id} with Discord message ID {discord_message_id}")

    except Exception as e:
        logger.error(f"Error updating pending reply: {e}", exc_info=True)
    finally:
        cursor.close()
        conn.close()


class EditReplyModal(discord.ui.Modal, title="Edit Reply"):
    """Modal for editing reply text"""

    def __init__(self, pending_id, current_text, platform):
        super().__init__()
        self.pending_id = pending_id
        self.platform = platform

        self.reply_text = TextInput(
            label="Reply Text",
            style=discord.TextStyle.paragraph,
            placeholder="Edit your reply here...",
            default=current_text,
            required=True,
            max_length=280 if platform == 'x' else 3000
        )

        self.add_item(self.reply_text)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""

        new_text = self.reply_text.value

        # Validate character count
        if self.platform == 'x' and len(new_text) > 280:
            await interaction.response.send_message(
                f"⚠️ Reply too long for X/Twitter! ({len(new_text)}/280 characters)",
                ephemeral=True
            )
            return

        # Update database
        conn = get_db_connection()
        if conn:
            cursor = get_db_cursor(conn)

            cursor.execute("""
                UPDATE pending_replies
                SET edited_reply = %s,
                    edit_count = edit_count + 1,
                    status = 'edited'
                WHERE id = %s
            """, (new_text, self.pending_id))

            conn.commit()
            cursor.close()
            conn.close()

        # Update original message
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="💬 Your Reply (EDITED)", value=new_text, inline=False)
        embed.color = discord.Color.orange()

        await interaction.response.edit_message(embed=embed)
        await interaction.followup.send("✅ Reply updated!", ephemeral=True)


class ReplyApprovalView(discord.ui.View):
    """Interactive buttons for reply approval"""

    def __init__(self, pending_id, platform):
        super().__init__(timeout=None)
        self.pending_id = pending_id
        self.platform = platform

    @discord.ui.button(label="✅ Post", style=discord.ButtonStyle.success)
    async def post_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Post reply without liking"""
        await self.post_reply(interaction, like=False)

    @discord.ui.button(label="❤️ Post + Like", style=discord.ButtonStyle.primary)
    async def post_like_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Post reply and like original post"""
        await self.post_reply(interaction, like=True)

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.secondary)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open edit modal"""

        # Get current reply text
        conn = get_db_connection()
        if not conn:
            await interaction.response.send_message("Database error", ephemeral=True)
            return

        cursor = get_db_cursor(conn)
        cursor.execute("""
            SELECT suggested_reply, edited_reply
            FROM pending_replies
            WHERE id = %s
        """, (self.pending_id,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result:
            await interaction.response.send_message("Reply not found", ephemeral=True)
            return

        current_text = result['edited_reply'] if result['edited_reply'] else result['suggested_reply']

        # Show modal
        modal = EditReplyModal(self.pending_id, current_text, self.platform)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.danger)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip this reply"""

        # Update status
        conn = get_db_connection()
        if conn:
            cursor = get_db_cursor(conn)

            cursor.execute("""
                UPDATE pending_replies
                SET status = 'skipped',
                    responded_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (self.pending_id,))

            conn.commit()
            cursor.close()
            conn.close()

        # Update message
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.light_gray()
        embed.set_footer(text="⏭️ Skipped")

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("Skipped this reply", ephemeral=True)

    async def post_reply(self, interaction: discord.Interaction, like: bool):
        """Post the reply to social media"""

        await interaction.response.defer(ephemeral=True)

        # Get pending reply
        conn = get_db_connection()
        if not conn:
            await interaction.followup.send("Database error", ephemeral=True)
            return

        cursor = get_db_cursor(conn)

        cursor.execute("""
            SELECT * FROM pending_replies
            WHERE id = %s
        """, (self.pending_id,))

        pending = cursor.fetchone()

        if not pending:
            await interaction.followup.send("Reply not found", ephemeral=True)
            cursor.close()
            conn.close()
            return

        # Use edited reply if available
        reply_text = pending['edited_reply'] if pending['edited_reply'] else pending['suggested_reply']

        # TODO: Implement actual posting to X/LinkedIn
        # For now, just mark as posted and save to history

        try:
            # Mark as posted
            cursor.execute("""
                UPDATE pending_replies
                SET status = 'posted',
                    posted_at = CURRENT_TIMESTAMP,
                    also_liked = %s
                WHERE id = %s
            """, (like, self.pending_id))

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

            # Update message
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.set_footer(text=f"✅ Posted{' + Liked' if like else ''} at {datetime.now().strftime('%Y-%m-%d %H:%M')}")

            # Disable all buttons
            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send(f"✅ Reply posted successfully{' and liked' if like else ''}!", ephemeral=True)

        except Exception as e:
            logger.error(f"Post error: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error posting reply: {e}", ephemeral=True)

        finally:
            cursor.close()
            conn.close()


async def send_discord_notification(user_discord_id, post, reply_data, pending_id, retry_count=0):
    """Send Discord notification with interactive buttons and rate limit handling"""

    MAX_RETRIES = 3

    try:
        # Get notification channel
        channel = bot.get_channel(DISCORD_CHANNEL_ID)

        if not channel:
            logger.error(f"Discord channel {DISCORD_CHANNEL_ID} not found")
            return

        # Create embed
        embed = discord.Embed(
            title=f"🔔 New Reply Opportunity ({post.get('platform', 'x').upper()})",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Original post
        post_preview = post['content'][:500] + "..." if len(post['content']) > 500 else post['content']
        embed.add_field(
            name=f"📝 Original Post by @{post['author_handle']}",
            value=post_preview,
            inline=False
        )

        # AI generated reply
        embed.add_field(
            name="💬 Suggested Reply",
            value=reply_data['reply'],
            inline=False
        )

        # Engagement metrics
        metrics = f"❤️ {post['likes_count']} | 💬 {post['replies_count']} | Score: {post['engagement_score']}"
        embed.add_field(
            name="📊 Engagement",
            value=metrics,
            inline=True
        )

        # Quality score
        quality_display = "⭐" * reply_data['quality_score']
        embed.add_field(
            name=f"🎯 Quality Score ({reply_data['quality_score']}/10)",
            value=quality_display,
            inline=True
        )

        # Reasoning
        embed.add_field(
            name="💡 AI Reasoning",
            value=reply_data['reasoning'],
            inline=False
        )

        # Post URL
        embed.add_field(
            name="🔗 Link",
            value=post['post_url'],
            inline=False
        )

        # Character count
        char_count = len(reply_data['reply'])
        char_limit = 280 if post.get('platform', 'x') == 'x' else 3000
        embed.set_footer(text=f"Characters: {char_count}/{char_limit}")

        # Create view with buttons
        view = ReplyApprovalView(pending_id, post.get('platform', 'x'))

        # Send message
        message = await channel.send(
            content=f"<@{user_discord_id}>",
            embed=embed,
            view=view
        )

        # Update pending reply with Discord message ID
        update_pending_reply(pending_id, message.id, channel.id)

        logger.info(f"✓ Sent Discord notification to user {user_discord_id} for post {post['post_id']}")

        # Rate limit: Wait 1 second between messages to avoid rate limits
        await asyncio.sleep(1)

    except discord.errors.HTTPException as e:
        if e.status == 429:  # Rate limited
            if retry_count < MAX_RETRIES:
                retry_after = float(e.response.headers.get('Retry-After', 5))
                logger.warning(f"Discord rate limited. Waiting {retry_after} seconds before retry {retry_count + 1}/{MAX_RETRIES}...")
                await asyncio.sleep(retry_after)

                # Retry
                await send_discord_notification(user_discord_id, post, reply_data, pending_id, retry_count + 1)
            else:
                logger.error(f"Discord rate limit exceeded after {MAX_RETRIES} retries")
        else:
            logger.error(f"Discord HTTP error sending notification: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error sending Discord notification: {e}", exc_info=True)


async def process_user_accounts(user):
    """Process all monitored accounts for one user"""

    user_discord_id = user['discord_id']

    # Check if monitoring is paused for this user
    if is_monitoring_paused(user_discord_id):
        logger.info(f"Monitoring paused for user {user_discord_id}, skipping...")
        return

    try:
        # Get filter settings
        filters = get_filter_settings(user_discord_id)

        # Get monitored accounts
        accounts = get_monitored_accounts(user_discord_id)

        logger.info(f"Processing {len(accounts)} accounts for user {user_discord_id}")

        for account in accounts:
            try:
                platform = account['platform']
                account_handle = account['account_handle']

                logger.info(f"  Fetching {platform} feed for @{account_handle}...")

                # Fetch posts
                if platform == 'x':
                    posts = feed_monitor.fetch_x_feed(account_handle)
                elif platform == 'linkedin':
                    posts = feed_monitor.fetch_linkedin_feed(account_handle)
                else:
                    logger.warning(f"  Unknown platform {platform}, skipping")
                    continue

                # Filter new posts
                new_posts = feed_monitor.filter_new_posts(posts, account['last_post_id'])

                logger.info(f"    Found {len(new_posts)} new posts")

                for post in new_posts:
                    # Add platform to post
                    post['platform'] = platform

                    # Check for duplicate
                    if is_duplicate_post(user_discord_id, post['post_id']):
                        continue

                    # Check if should notify
                    if feed_monitor.should_notify(post, filters, user_discord_id):
                        # Check daily notification limit
                        if not check_daily_notification_limit(user_discord_id, filters.get('max_notifications_per_day', 20)):
                            logger.warning(f"    User {user_discord_id} reached daily notification limit")
                            break

                        # Check Claude API usage limits
                        if not usage_tracker.can_generate():
                            logger.error("⚠️ Daily Claude API limit reached - skipping AI generation")
                            remaining = usage_tracker.get_remaining()
                            logger.error(f"   Used: {remaining['generations_used']}/{DAILY_AI_LIMIT} generations, ${remaining['cost_used']}/${AI_COST_LIMIT}")
                            break

                        # Generate AI reply
                        logger.info(f"    Generating reply for post {post['post_id']}...")
                        reply_data = generate_reply_with_quality(post['content'], platform)

                        # Check quality threshold
                        if reply_data['quality_score'] >= filters.get('min_quality_score', MIN_QUALITY_SCORE):
                            # Save to database
                            pending_id = save_pending_reply(user_discord_id, post, reply_data)

                            if pending_id:
                                # Send Discord notification
                                await send_discord_notification(user_discord_id, post, reply_data, pending_id)
                        else:
                            logger.info(f"    Reply quality score too low: {reply_data['quality_score']}")

                # Update last checked
                if posts:
                    update_last_checked(account['id'], posts[0]['post_id'])
                else:
                    update_last_checked(account['id'])

            except Exception as e:
                logger.error(f"Error processing account {account['account_handle']}: {e}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Error processing user {user_discord_id}: {e}", exc_info=True)


async def monitor_loop():
    """Main monitoring loop - runs every CHECK_INTERVAL_MINUTES"""

    # Wait for bot to be ready
    await bot.wait_until_ready()

    logger.info(f"✓ Monitor loop started. Checking every {CHECK_INTERVAL_MINUTES} minutes.")

    while not bot.is_closed():
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"Starting monitoring cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*50}")

            # Get all users with active monitoring
            users = get_all_active_users()

            logger.info(f"Found {len(users)} active users with monitoring enabled")

            for user in users:
                try:
                    await process_user_accounts(user)
                except Exception as e:
                    logger.error(f"Error processing user {user['discord_id']}: {e}", exc_info=True)

                # Rate limit between users
                await asyncio.sleep(2)

            logger.info(f"{'='*50}")
            logger.info(f"Monitoring cycle complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Next check in {CHECK_INTERVAL_MINUTES} minutes")
            logger.info(f"{'='*50}\n")

        except Exception as e:
            logger.error(f"CRITICAL: Error in monitor loop: {e}", exc_info=True)

        # Wait for next cycle
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)


@bot.event
async def on_ready():
    """Bot startup"""
    logger.info(f'✓ Discord bot logged in as {bot.user}')
    logger.info(f'✓ Monitoring channel ID: {DISCORD_CHANNEL_ID}')
    logger.info(f'✓ Check interval: {CHECK_INTERVAL_MINUTES} minutes')
    logger.info(f'✓ Minimum quality score: {MIN_QUALITY_SCORE}')

    # Start monitor loop
    bot.loop.create_task(monitor_loop())


# Graceful shutdown handler
class GracefulShutdown:
    """Handle graceful shutdown signals"""

    def __init__(self):
        self.shutdown_flag = False
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        logger.warning(f"Received shutdown signal ({signum}). Shutting down gracefully...")
        self.shutdown_flag = True
        # Close bot connection
        asyncio.create_task(bot.close())


# Run bot
if __name__ == '__main__':
    if not DISCORD_BOT_TOKEN:
        logger.error("ERROR: DISCORD_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not CLAUDE_API_KEY:
        logger.error("ERROR: CLAUDE_API_KEY not set in .env")
        sys.exit(1)

    # Check X API credentials (warning, not fatal)
    if X_BEARER_TOKEN:
        logger.info("✓ X API credentials found - will use X API as primary source")
    else:
        logger.warning("⚠️ X_BEARER_TOKEN not found in .env")
        logger.warning("⚠️ Will use Nitter only (less reliable)")
        logger.warning("⚠️ Get free X API key: https://developer.twitter.com/en/portal/dashboard")

    # Initialize graceful shutdown
    shutdown_handler = GracefulShutdown()

    logger.info("="*60)
    logger.info("Starting Reply Assistant Discord Bot...")
    logger.info("="*60)

    try:
        bot.run(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"CRITICAL: Bot crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot shutdown complete.")
