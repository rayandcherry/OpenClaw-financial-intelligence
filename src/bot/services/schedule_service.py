from __future__ import annotations

import asyncio
import logging
from datetime import time as dt_time, datetime, timezone
from src.bot.services.report_formatter import ReportFormatter

logger = logging.getLogger(__name__)


def _is_blocked_error(exc: Exception) -> bool:
    """Check if an exception indicates the user blocked the bot (Telegram 403)."""
    try:
        from telegram.error import Forbidden
        if isinstance(exc, Forbidden):
            return True
    except ImportError:
        pass
    # Fallback: check string representation for "403" or "Forbidden"
    return "403" in str(exc) or "Forbidden" in str(exc)


class ScheduleService:
    def __init__(self, user_service, scan_service, report_formatter: ReportFormatter = None):
        self.user_service = user_service
        self.scan_service = scan_service
        self.report_formatter = report_formatter or ReportFormatter()

    def collect_users_for_time(self, scan_time: dt_time) -> list:
        return self.user_service.get_users_for_time(scan_time)

    def build_user_tickers_map(self, users: list) -> dict[int, list[str]]:
        result = {}
        for user in users:
            tickers = self.user_service.get_watchlist(user.id)
            if tickers:
                result[user.id] = tickers
        return result

    async def execute_batch(
        self,
        user_tickers: dict[int, list[str]],
        user_telegram_map: dict[int, int],
        deliver_fn,
        user_strategies: dict[int, list] | None = None,
    ):
        if not user_tickers:
            return

        started_at = datetime.now(timezone.utc)
        results = await self.scan_service.batch_scan(user_tickers, user_strategies=user_strategies)

        for user_id, signals in results.items():
            telegram_id = user_telegram_map.get(user_id)
            if telegram_id is None:
                continue

            total_scanned = len(user_tickers.get(user_id, []))
            messages = self.report_formatter.format_report_messages(signals, total_scanned)

            delivery_ok = True
            user_blocked = False
            for msg in messages:
                if user_blocked:
                    break
                delivered = False
                for attempt in range(3):
                    try:
                        await deliver_fn(telegram_id, msg)
                        delivered = True
                        break
                    except Exception as e:
                        # Detect user blocking the bot (Telegram 403)
                        if _is_blocked_error(e):
                            logger.info(f"User {user_id} blocked the bot, deactivating")
                            self.user_service.deactivate(user_id)
                            user_blocked = True
                            break
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt * 5)  # 5s, 10s
                        else:
                            logger.error(f"Delivery failed for user {user_id} after 3 attempts: {e}")
                if not delivered:
                    delivery_ok = False

            try:
                self.user_service.log_scan(
                    user_id=user_id,
                    triggered_by="scheduled",
                    tickers_count=total_scanned,
                    signals_found=len(signals),
                    status="done" if delivery_ok else "failed",
                    report_text="\n".join(messages),
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.error(f"Failed to log scan for user {user_id}: {e}")

    async def trigger_scheduled_scan(self, scan_time: dt_time, deliver_fn):
        users = self.collect_users_for_time(scan_time)
        if not users:
            return

        user_tickers = self.build_user_tickers_map(users)
        user_telegram_map = {u.id: u.telegram_id for u in users}
        user_strategies = {u.id: u.strategies for u in users}

        logger.info(f"Scheduled scan at {scan_time}: {len(users)} users, "
                     f"{len(self.scan_service.dedupe_tickers(user_tickers))} unique tickers")

        await self.execute_batch(user_tickers, user_telegram_map, deliver_fn, user_strategies)
