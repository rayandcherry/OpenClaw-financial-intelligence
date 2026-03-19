from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service
from src.bot.db.models import ScanLog


async def last_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    last_scan = (
        user_svc.session.query(ScanLog)
        .filter_by(user_id=user.id, status="done")
        .order_by(ScanLog.finished_at.desc())
        .first()
    )

    if not last_scan or not last_scan.report_text:
        await update.message.reply_text("No previous scan reports found. Use /scan to run one.")
        return

    # Report may be multi-message — split on the separator we know exists
    header = f"*Last scan* ({last_scan.finished_at.strftime('%b %d, %H:%M UTC') if last_scan.finished_at else 'unknown'})\n"
    text = last_scan.report_text

    # Telegram 4096 char limit
    if len(header + text) <= 4096:
        await update.message.reply_text(header + text, parse_mode="Markdown")
    else:
        await update.message.reply_text(header, parse_mode="Markdown")
        # Split report into chunks
        while text:
            chunk = text[:4096]
            text = text[4096:]
            await update.message.reply_text(chunk, parse_mode="Markdown")
