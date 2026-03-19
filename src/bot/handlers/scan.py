import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service, get_scan_service, get_report_formatter
from src.bot.services.scan_service import ScanService

logger = logging.getLogger(__name__)


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
        # Apply scan mode filter (US/CRYPTO/ALL)
        tickers = ScanService.filter_by_mode(tickers, user.scan_mode)

    if not tickers:
        await update.message.reply_text("No tickers to scan. Use /watch AAPL NVDA or /presets to add some.")
        return

    await update.message.reply_text(f"Scanning {len(tickers)} ticker{'s' if len(tickers) != 1 else ''}...")

    started_at = datetime.now(timezone.utc)

    try:
        signals = await scan_svc.scan_for_user(
            user_id=user.id, tickers=tickers, strategies=user.strategies
        )

        if signals is None:
            user_svc.log_scan(
                user_id=user.id, triggered_by="manual", tickers_count=len(tickers),
                signals_found=0, status="rejected", started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
            await update.message.reply_text(
                "Your last scan is still running, hang tight. Or you've hit the rate limit (10/hour)."
            )
            return

        messages = fmt.format_report_messages(signals, total_scanned=len(tickers))
        for msg in messages:
            await update.message.reply_text(msg, parse_mode="Markdown")

        user_svc.log_scan(
            user_id=user.id, triggered_by="manual", tickers_count=len(tickers),
            signals_found=len(signals), status="done",
            report_text="\n".join(messages), started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.exception(f"Scan failed for user {user.id}: {e}")
        try:
            user_svc.log_scan(
                user_id=user.id, triggered_by="manual", tickers_count=len(tickers),
                signals_found=0, status="failed", started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except Exception:
            pass  # Don't let logging failure mask the original error
        await update.message.reply_text(
            "Something went wrong during the scan. Please try again in a few minutes."
        )
