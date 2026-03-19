from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service, get_scan_service, get_report_formatter


async def scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    scan_svc = get_scan_service()
    fmt = get_report_formatter()

    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if context.args:
        tickers = [context.args[0].upper()]
    else:
        tickers = user_svc.get_watchlist(user.id)

    if not tickers:
        await update.message.reply_text(
            "No tickers to scan. Use /watch AAPL NVDA or /presets to add some."
        )
        return

    await update.message.reply_text(f"Scanning {len(tickers)} ticker{'s' if len(tickers) != 1 else ''}...")

    signals = await scan_svc.scan_for_user(user_id=user.id, tickers=tickers)

    if signals is None:
        await update.message.reply_text(
            "Your last scan is still running, hang tight. Or you've hit the rate limit (10/hour)."
        )
        return

    messages = fmt.format_report_messages(signals, total_scanned=len(tickers))
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")
