import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bot.db.models import Base
from bot.db.session import DATABASE_URL
from bot.redis_client import RedisClient
from bot.services.user_service import UserService
from bot.services.scan_service import ScanService
from bot.services.schedule_service import ScheduleService
from bot.services.report_formatter import ReportFormatter
from bot.handlers import set_services
from bot.handlers.start import start_handler
from bot.handlers.watchlist import watchlist_handler, watch_handler, unwatch_handler, presets_handler, preset_callback
from bot.handlers.scan import scan_handler
from bot.handlers.schedule import schedule_handler, pause_handler, resume_handler
from bot.handlers.settings import settings_handler, lang_handler, mode_handler, strategies_handler
from bot.handlers.help import help_handler
from bot.handlers.status import status_handler
from bot.handlers.last import last_handler
from bot.health import start_health_server

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_sync_engine():
    """Create sync engine for UserService (ORM operations are simple and fast)."""
    url = os.getenv("DATABASE_SYNC_URL")
    if not url:
        # Convert asyncpg URL to psycopg2 for sync access
        url = DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    return create_engine(url)


async def scheduled_scan_tick(bot, schedule_service: ScheduleService):
    """Called every minute by APScheduler. Checks if any users need scanning."""
    now = datetime.now(timezone.utc).time().replace(second=0, microsecond=0)

    async def deliver(telegram_id: int, text: str):
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")

    await schedule_service.trigger_scheduled_scan(now, deliver)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Initialize services
    sync_engine = create_sync_engine()
    Base.metadata.create_all(sync_engine)  # Dev convenience; prod uses Alembic
    db_session = Session(sync_engine)

    redis_client = RedisClient()
    user_service = UserService(db_session)
    scan_service = ScanService(redis_client=redis_client)
    report_formatter = ReportFormatter()
    schedule_service = ScheduleService(user_service, scan_service, report_formatter)

    set_services(user_service, scan_service, report_formatter, redis_client)

    # Build Telegram bot
    app = ApplicationBuilder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("watchlist", watchlist_handler))
    app.add_handler(CommandHandler("watch", watch_handler))
    app.add_handler(CommandHandler("unwatch", unwatch_handler))
    app.add_handler(CommandHandler("presets", presets_handler))
    app.add_handler(CommandHandler("scan", scan_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("last", last_handler))
    app.add_handler(CommandHandler("schedule", schedule_handler))
    app.add_handler(CommandHandler("pause", pause_handler))
    app.add_handler(CommandHandler("resume", resume_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("lang", lang_handler))
    app.add_handler(CommandHandler("mode", mode_handler))
    app.add_handler(CommandHandler("strategies", strategies_handler))
    app.add_handler(CallbackQueryHandler(preset_callback, pattern="^preset:"))

    # Global error handler — ensures users always get feedback
    async def error_handler(update, context):
        logger.exception("Unhandled exception in handler", exc_info=context.error)
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "Something went wrong. Please try again or use /help."
                )
            except Exception:
                pass  # Can't even reply — just log

    app.add_error_handler(error_handler)

    # Schedule: check every minute for users who need scanning
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_scan_tick,
        "interval",
        minutes=1,
        args=[app.bot, schedule_service],
    )

    logger.info("Starting OpenClaw bot...")

    # Start health check + scheduler alongside the bot
    async def post_init(application):
        await start_health_server(port=int(os.getenv("HEALTH_PORT", "8080")))
        scheduler.start()
        logger.info("Scheduler and health check started")

    async def post_shutdown(application):
        scheduler.shutdown()
        scan_service.shutdown()
        await redis_client.close()
        db_session.close()
        logger.info("Shutdown complete")

    app.post_init = post_init
    app.post_shutdown = post_shutdown
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
