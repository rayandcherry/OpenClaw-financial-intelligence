from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    tickers = user_svc.get_watchlist(user.id)
    scheds = user_svc.get_schedules(user.id)
    stats = user_svc.get_scan_stats(user.id)

    sched_lines = []
    for s in scheds:
        status = "paused" if s.is_paused else "active"
        sched_lines.append(f"{s.scan_time.strftime('%H:%M')} UTC ({status})")

    last = stats["last_scan_at"]
    last_str = last.strftime("%b %d, %H:%M UTC") if last else "never"

    text = (
        f"*Your OpenClaw Status*\n\n"
        f"Watchlist: {len(tickers)} tickers\n"
        f"Schedule: {', '.join(sched_lines) if sched_lines else 'not set'}\n"
        f"Mode: {user.scan_mode} | Lang: {user.lang}\n"
        f"Strategies: {', '.join(user.strategies) if user.strategies else 'All'}\n\n"
        f"*Scan History*\n"
        f"Total scans: {stats['successful_scans']}/{stats['total_scans']}\n"
        f"Signals found: {stats['total_signals']}\n"
        f"Last scan: {last_str} ({stats['last_signals']} signals)"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
