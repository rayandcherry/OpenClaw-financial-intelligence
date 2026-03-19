from datetime import time as dt_time
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service


async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if not context.args:
        scheds = user_svc.get_schedules(user.id)
        if not scheds:
            await update.message.reply_text("No scan schedule set.\n\nUsage: /schedule 8:00 20:00")
            return
        lines = []
        for s in scheds:
            status = "⏸ paused" if s.is_paused else "▶️ active"
            lines.append(f"  {s.scan_time.strftime('%H:%M')} UTC — {status}")
        await update.message.reply_text(
            f"*Your Scan Schedule*\n\n" + "\n".join(lines) + "\n\n/pause | /resume",
            parse_mode="Markdown",
        )
        return

    times = []
    for arg in context.args:
        try:
            parts = arg.split(":")
            times.append(dt_time(int(parts[0]), int(parts[1])))
        except (ValueError, IndexError):
            await update.message.reply_text(f"Invalid time format: {arg}. Use HH:MM (e.g., 8:00)")
            return

    user_svc.set_schedules(user.id, times)
    time_strs = ", ".join(t.strftime("%H:%M") for t in times)
    await update.message.reply_text(f"Schedule set: {time_strs} UTC daily.")


async def pause_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return
    for sched in user_svc.get_schedules(user.id):
        sched.is_paused = True
    user_svc.session.commit()
    await update.message.reply_text("Scheduled scans paused. /resume to restart.")


async def resume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return
    for sched in user_svc.get_schedules(user.id):
        sched.is_paused = False
    user_svc.session.commit()
    await update.message.reply_text("Scheduled scans resumed.")
