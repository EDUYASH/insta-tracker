import logging
import os
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from extractor import extract_username_from_url
from scraper import scrape_socialblade
from sheets import (
    get_sheet,
    get_or_create_date_column,
    find_or_create_profile_row,
    update_follower_count,
    load_profiles_from_sheet,
    save_profile_to_sheet,
    remove_profile_from_sheet,
)

# ─── CONFIG ──────────────────────────────────────────────────
# All config via environment variables (for Railway cloud deployment)
BOT_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "8936564014:AAHJ4dKgXxXRjyfo4GdmPGr2lRw0jv6R0Hc")
SHEET_TAB  = os.environ.get("SHEET_TAB", "Sheet1")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─── Helpers ─────────────────────────────────────────────────

def days_remaining(added_date_str, track_days=4):
    try:
        added   = datetime.strptime(str(added_date_str), "%Y-%m-%d").date()
        expires = added + timedelta(days=int(track_days))
        return max(0, (expires - date.today()).days)
    except:
        return 0

def days_elapsed(added_date_str, track_days=4):
    try:
        added   = datetime.strptime(str(added_date_str), "%Y-%m-%d").date()
        elapsed = (date.today() - added).days
        return min(elapsed, int(track_days))
    except:
        return 0

def add_to_tracker_sheet(username, followers):
    """Write today's follower count into the main Sheet1 tracking tab."""
    try:
        date_col_str = date.today().strftime("%d/%m/%y")
        ws           = get_sheet(tab_name=SHEET_TAB)
        date_col     = get_or_create_date_column(ws, date_col_str)
        profile_link = f"https://www.instagram.com/{username}/"
        row_idx      = find_or_create_profile_row(ws, username, profile_link)
        if followers:
            update_follower_count(ws, row_idx, date_col, followers)
        return True
    except Exception as e:
        log.error(f"Sheet update error: {e}")
        return False

# ─── Bot Handlers ─────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Instagram Follower Tracker Bot\n\n"
        "Send me any Instagram profile URL and I'll track it for 4 days!\n\n"
        "Commands:\n"
        "/list - See all tracked profiles\n"
        "/remove username - Stop tracking\n"
        "/help - How to use\n\n"
        "Example - just paste:\n"
        "https://www.instagram.com/learningwave.in/"
    )
    await update.message.reply_text(msg)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "How to use:\n\n"
        "1. Open Instagram on your phone\n"
        "2. Go to any profile\n"
        "3. Tap Share > Copy Profile Link\n"
        "4. Come here and paste the URL\n"
        "5. Done! Tracked for 4 days\n\n"
        "Also works with:\n"
        "- Direct username: zanvixofficial\n"
        "- With @: @zanvixofficial\n\n"
        "Post/Reel URLs don't work - use profile URL instead."
    )
    await update.message.reply_text(msg)


async def list_profiles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        profiles = load_profiles_from_sheet()
    except Exception as e:
        await update.message.reply_text(f"Error loading profiles: {e}")
        return

    if not profiles:
        await update.message.reply_text(
            "No profiles tracked yet!\nSend an Instagram profile URL to start."
        )
        return

    lines = ["Currently Tracking:\n"]
    for p in profiles:
        username   = p.get("username", "")
        added      = p.get("added_date", "")
        track_days = int(p.get("track_days", 4))
        rem        = days_remaining(added, track_days)
        elapsed    = days_elapsed(added, track_days)

        filled  = "o" * elapsed
        empty   = "-" * (track_days - elapsed)
        bar     = f"[{filled}{empty}]"
        status  = f"{rem} day{'s' if rem != 1 else ''} left" if rem > 0 else "EXPIRED"
        lines.append(f"@{username}\n  {bar} Day {elapsed}/{track_days} - {status}")

    lines.append("\nSend /remove username to stop tracking")
    await update.message.reply_text("\n".join(lines))


async def remove_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: /remove username\nExample: /remove learningwave.in"
        )
        return

    username = args[0].lstrip("@").lower()
    try:
        removed = remove_profile_from_sheet(username)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    if removed:
        await update.message.reply_text(f"Removed @{username} from tracking.")
    else:
        await update.message.reply_text(f"@{username} not found in tracking list.")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    msg  = await update.message.reply_text("Processing...")

    username = None

    if "instagram.com" in text:
        username = extract_username_from_url(text)
        if not username:
            await msg.edit_text(
                "Could not extract username from this URL.\n\n"
                "Please use the PROFILE URL:\n"
                "instagram.com/USERNAME/\n\n"
                "Or just send the username directly:\n"
                "zanvixofficial"
            )
            return
    else:
        # Direct username input
        candidate = text.lstrip("@").lower().strip()
        if not candidate or " " in candidate or len(candidate) > 30:
            await msg.edit_text(
                "Please send a valid Instagram profile URL or username."
            )
            return
        username = candidate

    # Check if already tracking
    try:
        profiles = load_profiles_from_sheet()
        if any(p.get("username", "").lower() == username for p in profiles):
            await msg.edit_text(f"@{username} is already being tracked!")
            return
    except Exception as e:
        log.error(f"Error checking profiles: {e}")

    # Fetch follower count from Social Blade
    await msg.edit_text(f"Fetching @{username} from Social Blade...")
    data      = scrape_socialblade(username)
    followers = data["followers"] if data else None
    following = data["following"] if data else None

    # Save to BotConfig tab
    try:
        today = date.today().strftime("%Y-%m-%d")
        save_profile_to_sheet(username, today, 4)
    except Exception as e:
        log.error(f"Error saving to config sheet: {e}")
        await msg.edit_text(f"Error saving profile: {e}")
        return

    # Update main tracker sheet
    sheet_ok = add_to_tracker_sheet(username, followers)

    followers_text = f"{followers:,}" if followers else "N/A"
    following_text = str(following) if following else "N/A"
    sheet_text     = "Google Sheet updated!" if sheet_ok else "Sheet update failed"

    response = (
        f"@{username} added!\n\n"
        f"Followers : {followers_text}\n"
        f"Following : {following_text}\n"
        f"Tracking  : 4 days\n"
        f"Sheet     : {sheet_text}\n\n"
        f"Daily at 9 AM it will auto-update!"
    )

    keyboard = [[InlineKeyboardButton(f"Remove @{username}", callback_data=f"remove:{username}")]]
    await msg.edit_text(response, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("remove:"):
        username = query.data.split(":", 1)[1]
        try:
            remove_profile_from_sheet(username)
            await query.edit_message_text(f"Removed @{username} from tracking.")
        except Exception as e:
            await query.edit_message_text(f"Error removing: {e}")


# ─── Main ────────────────────────────────────────────────────
def main():
    print("Starting Insta Tracker Bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("list",   list_profiles))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("Bot is running! Send messages on Telegram.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
