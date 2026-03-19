import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service
from src.config import PRESET_WATCHLISTS

logger = logging.getLogger(__name__)
_validate_pool = ThreadPoolExecutor(max_workers=3)


async def watchlist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    tickers = user_svc.get_watchlist(user.id)
    if not tickers:
        await update.message.reply_text(
            "Your watchlist is empty.\n\nUse /watch AAPL NVDA to add tickers or /presets to browse lists."
        )
        return

    ticker_list = ", ".join(tickers)
    await update.message.reply_text(
        f"*Your Watchlist* ({len(tickers)} tickers)\n\n{ticker_list}\n\n"
        f"/watch to add | /unwatch to remove",
        parse_mode="Markdown",
    )


def _check_ticker(ticker: str) -> bool:
    """Validate ticker exists on yfinance. Runs in thread pool."""
    try:
        from src.core.data_fetcher import fetch_data
        result = fetch_data(ticker, "5d")
        return result is not None and not result.empty
    except Exception:
        return False


async def _validate_ticker(ticker: str) -> bool:
    """Async wrapper for ticker validation."""
    return await asyncio.get_running_loop().run_in_executor(_validate_pool, _check_ticker, ticker)


async def watch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    tickers = context.args
    if not tickers:
        await update.message.reply_text("Usage: /watch AAPL NVDA BTC-USD")
        return

    # Pre-filter: only allow valid ticker format (letters, digits, hyphens, dots, max 12 chars)
    _TICKER_RE = re.compile(r'^[A-Z0-9.\-]{1,12}$')
    upper_tickers = [t.upper() for t in tickers]
    candidates = [t for t in upper_tickers if _TICKER_RE.match(t)]
    rejected_format = [t for t in upper_tickers if not _TICKER_RE.match(t)]

    # Validate remaining against yfinance
    valid, invalid = [], []
    for t in candidates:
        if await _validate_ticker(t):
            valid.append(t)
        else:
            invalid.append(t)
    invalid.extend(rejected_format)

    msg_parts = []
    if valid:
        rejected = user_svc.add_tickers(user.id, valid)
        added = [t for t in valid if t not in rejected]
        if added:
            msg_parts.append(f"Added: {', '.join(added)}")
        if rejected:
            msg_parts.append(f"Watchlist full (50 max), couldn't add: {', '.join(rejected)}")
    if invalid:
        msg_parts.append(f"Not found: {', '.join(invalid)} — check the symbol and try again.")
    if not msg_parts:
        msg_parts.append("Those tickers are already in your watchlist.")

    await update.message.reply_text("\n".join(msg_parts))


async def unwatch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /unwatch AAPL")
        return

    ticker = context.args[0].upper()
    user_svc.remove_ticker(user.id, ticker)
    await update.message.reply_text(f"Removed {ticker} from your watchlist.")


async def presets_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"{name} ({len(tickers)})", callback_data=f"preset:{name}")]
        for name, tickers in PRESET_WATCHLISTS.items()
    ]

    await update.message.reply_text(
        "*Preset Watchlists*\n\nPick one to load:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def preset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("preset:"):
        return

    preset_name = data[len("preset:"):]
    if preset_name == "skip":
        await query.edit_message_text("No worries! Use /watch AAPL NVDA to add tickers anytime.")
        return

    tickers = PRESET_WATCHLISTS.get(preset_name)
    if not tickers:
        await query.edit_message_text("Preset not found.")
        return

    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(query.from_user.id)
    if not user:
        return

    rejected = user_svc.add_tickers(user.id, tickers)
    added_count = len(tickers) - len(rejected)
    await query.edit_message_text(
        f"Loaded *{preset_name}* — {added_count} tickers added to your watchlist.\n\n"
        f"Use /scan to run your first scan!",
        parse_mode="Markdown",
    )
