from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service
from src.config import PRESET_WATCHLISTS


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    tg_user = update.effective_user

    user = user_svc.register(telegram_id=tg_user.id, username=tg_user.username)

    preset_names = list(PRESET_WATCHLISTS.keys())
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"preset:{name}")]
        for name in preset_names
    ]
    keyboard.append([InlineKeyboardButton("Custom (add later)", callback_data="preset:skip")])

    text = (
        "Welcome to *OpenClaw* 🦞\n\n"
        "I scan markets for trading signals using three strategies "
        "(Trinity, Panic, 2B) and deliver intelligence reports right here.\n\n"
        "*Quick setup — pick a watchlist:*\n"
        "Or just type /scan AAPL to try it now."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
