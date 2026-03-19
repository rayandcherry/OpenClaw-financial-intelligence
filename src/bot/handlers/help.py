from telegram import Update
from telegram.ext import ContextTypes


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*OpenClaw Commands*\n\n"
        "*Scanning*\n"
        "/scan — Scan your watchlist now\n"
        "/scan TICKER — Scan a single ticker\n\n"
        "*Watchlist*\n"
        "/watchlist — Show your watchlist\n"
        "/watch AAPL NVDA — Add tickers\n"
        "/unwatch AAPL — Remove a ticker\n"
        "/presets — Browse preset watchlists\n\n"
        "*Schedule*\n"
        "/schedule — Show scan schedule\n"
        "/schedule 8:00 20:00 — Set scan times (UTC)\n"
        "/pause — Pause scheduled scans\n"
        "/resume — Resume scheduled scans\n\n"
        "*Settings*\n"
        "/settings — Show preferences\n"
        "/lang EN|ZH — Set language\n"
        "/mode US|CRYPTO|ALL — Set scan mode\n"
        "/strategies — Toggle strategies\n\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
