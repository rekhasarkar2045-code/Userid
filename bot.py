import asyncio
import logging
import sqlite3
import requests
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
BOT_TOKEN = "8604572355:AAHplc24nwqf8frKRV6-TJyZJcxGpy1Zbyg"   # 👈 Replace with your BotFather token
API_URL   = "https://tg-number-api-wbka.vercel.app/"
PORT      = 8080  # Render open port

# ─────────────────────────────────────────────
#  Logging
# ────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Database
# ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            username  TEXT,
            full_name TEXT,
            chat_id   INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_user(user_id: int, username: str, full_name: str, chat_id: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, username, full_name, chat_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username  = excluded.username,
            full_name = excluded.full_name,
            chat_id   = excluded.chat_id
    """, (user_id, username.lower() if username else None, full_name, chat_id))
    conn.commit()
    conn.close()


def get_userid_by_username(username: str):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT user_id, full_name FROM users WHERE username = ?", (username.lower(),))
    row = c.fetchone()
    conn.close()
    return row


# ─────────────────────────────────────────────
#  Passive Tracker
# ─────────────────────────────────────────
async def track_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return
    save_user(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        chat_id=chat.id,
    )


# ─────────────────────────────────────────────
#  /start & /help
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╔══════════════════════════╗\n"
        "║      🤖  *BOT MENU*        ║\n"
        "╚══════════════════════════╝\n\n"
        "📌 *Commands:*\n\n"
        "🔍 `/userid @username`\n"
        "   ↳ Get Telegram User ID\n\n"
        "📞 `/ser [user\\_id]`\n"
        "   ↳ Lookup phone number by ID\n\n"
        "ℹ️ `/help` — Show this menu\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# ─────────────────────────────
#  /userid @username
# ─────────────────────────────────────────────
async def userid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* `/userid @username`",
            parse_mode="Markdown"
        )
        return

    raw = context.args[0].lstrip("@").strip()
    if not raw:
        await update.message.reply_text("❌ Invalid username.", parse_mode="Markdown")
        return

    row = get_userid_by_username(raw)

    if row:
        uid, full_name = row
        text = (
            "╔══════════════════════╗\n"
            "║   🔍  *USER ID FOUND*   ║\n"
            "╚════════════════╝\n\n"
            f"👤 *Name:* {full_name}\n"
            f"🔖 *Username:* @{raw}\n"
            f"🆔 *User ID:* `{uid}`\n\n"
            f"💡 _Use_ `/ser {uid}` _to lookup number\\._"
        )
    else:
        text = (
            "⚠️ *User not found in database.*\n\n"
            "The user must send *at least one message* "
            "before I can track their ID.\n\n"
            "Ask them to say something, then try again."
        )

    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
#  /ser [userid]
# ─────────────────────────────────────────────
async def ser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ *Usage:* `/ser [user\\_id]`\nExample: `/ser 7420311171`",
            parse_mode="Markdown"
        )
        return

    user_id = context.args[0].strip()
    if not user_id.isdigit():
        await update.message.reply_text(
            "❌ *Invalid ID.* User ID must be a number.",
            parse_mode="Markdown"
        )
        return

    wait_msg = await update.message.reply_text("⏳ *Fetching data...*", parse_mode="Markdown")

    try:
        response = requests.get(API_URL, params={"userid": user_id}, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and data.get("result"):
            result = data["result"]
            full_number = f"{result['country_code']}{result['number']}"
            text = (
                "╔══════════════════════════╗\n"
                "║   📞  *NUMBER FOUND*        ║\n"
                "╚══════════════════════════╝\n\n"
                f"🆔 *User ID:*      `{user_id}`\n"
                f"🌍 *Country:*      {result['country']}\n"
                f"🔢 *Code:*         `{result['country_code']}`\n"
                f"📱 *Number:*       `{result['number']}`\n"
                f"📞 *Full Number:*  `{full_number}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 _API valid until: {data.get('api_valid_until', 'N/A')}_"
            )
        else:
            text = (
                "╔══════════════════════╗\n"
                "║   ❌  *NOT FOUND*      ║\n"
                "╚══════════════════════╝\n\n"
                f"No phone number linked to ID `{user_id}`.\n\n"
                "_This user may have hidden their number or it's not in the database\\._"
            )

    except requests.exceptions.Timeout:
        text = "⏱️ *Request timed out.* Please try again."
    except requests.exceptions.HTTPError as e:
        text = f"🌐 *HTTP Error:* `{e}`"
    except Exception as e:
        logger.exception("API call failed")
        text = f"⚠️ *Unexpected error:* `{str(e)}`"

    await wait_msg.delete()
    await update.message.reply_text(text, parse_mode="Markdown")


# ────────────────────────────────────────
#  Dummy HTTP server — keeps Render happy
# ─────────────────────────────────────────────
async def health(request):
    return web.Response(text="OK")


async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ Web server running on port {PORT}")


# ─────────────────────────────────────────────
#  Main — Python 3.14 compatible
# ─────────────────────────────────────────────
async def main():
    init_db()

    await start_web()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, track_users), group=0)
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("userid", userid_cmd))
    app.add_handler(CommandHandler("ser",    ser_cmd))

    logger.info("✅ Bot started successfully.")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
