from __future__ import annotations

from datetime import time as dt_time
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.bot.db.models import User, UserWatchlist, UserSchedule, ScanLog
from src.config import BOT_CONFIG


class UserService:
    def __init__(self, session: Session):
        self.session = session

    def register(self, telegram_id: int, username: str = None) -> User:
        user = self.session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_active = True
            if username:
                user.username = username
            self.session.commit()
            return user
        user = User(
            telegram_id=telegram_id,
            username=username,
            strategies=BOT_CONFIG["default_strategies"],
        )
        self.session.add(user)
        self.session.commit()
        return user

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.session.query(User).filter_by(telegram_id=telegram_id).first()

    def add_tickers(self, user_id: int, tickers: list[str]) -> list[str]:
        existing = {wl.ticker for wl in self.session.query(UserWatchlist).filter_by(user_id=user_id).all()}
        cap = BOT_CONFIG["watchlist_max"]
        rejected = []
        for t in tickers:
            t_upper = t.upper()
            if t_upper in existing:
                continue
            if len(existing) >= cap:
                rejected.append(t_upper)
                continue
            self.session.add(UserWatchlist(user_id=user_id, ticker=t_upper))
            existing.add(t_upper)
        self.session.commit()
        return rejected

    def remove_ticker(self, user_id: int, ticker: str) -> None:
        self.session.query(UserWatchlist).filter_by(user_id=user_id, ticker=ticker.upper()).delete()
        self.session.commit()

    def clear_watchlist(self, user_id: int) -> int:
        """Remove all tickers from watchlist. Returns count removed."""
        count = self.session.query(UserWatchlist).filter_by(user_id=user_id).delete()
        self.session.commit()
        return count

    def get_watchlist(self, user_id: int) -> list[str]:
        rows = self.session.query(UserWatchlist).filter_by(user_id=user_id).all()
        return [r.ticker for r in rows]

    def set_schedules(self, user_id: int, times: list[dt_time]) -> None:
        self.session.query(UserSchedule).filter_by(user_id=user_id).delete()
        for t in times:
            self.session.add(UserSchedule(user_id=user_id, scan_time=t))
        self.session.commit()

    def get_schedules(self, user_id: int) -> list[UserSchedule]:
        return self.session.query(UserSchedule).filter_by(user_id=user_id).all()

    def update_preferences(self, user_id: int, **kwargs) -> None:
        user = self.session.get(User, user_id)
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        self.session.commit()

    def deactivate(self, user_id: int) -> None:
        user = self.session.get(User, user_id)
        user.is_active = False
        self.session.commit()

    def get_scan_stats(self, user_id: int) -> dict:
        """Return scan statistics for a user."""
        total = self.session.query(func.count(ScanLog.id)).filter_by(user_id=user_id).scalar() or 0
        done = self.session.query(func.count(ScanLog.id)).filter_by(user_id=user_id, status="done").scalar() or 0
        total_signals = self.session.query(func.coalesce(func.sum(ScanLog.signals_found), 0)).filter_by(user_id=user_id, status="done").scalar()
        last_scan = (
            self.session.query(ScanLog)
            .filter_by(user_id=user_id, status="done")
            .order_by(ScanLog.finished_at.desc())
            .first()
        )
        return {
            "total_scans": total,
            "successful_scans": done,
            "total_signals": int(total_signals),
            "last_scan_at": last_scan.finished_at if last_scan else None,
            "last_signals": last_scan.signals_found if last_scan else 0,
        }

    def log_scan(self, user_id: int, triggered_by: str, tickers_count: int,
                 signals_found: int, status: str, report_text: str = None,
                 started_at=None, finished_at=None) -> 'ScanLog':
        from src.bot.db.models import ScanLog
        log = ScanLog(
            user_id=user_id,
            triggered_by=triggered_by,
            tickers_count=tickers_count,
            signals_found=signals_found,
            status=status,
            report_text=report_text,
            started_at=started_at,
            finished_at=finished_at,
        )
        self.session.add(log)
        self.session.commit()
        return log

    def get_users_for_time(self, scan_time: dt_time) -> list[User]:
        schedule_rows = (
            self.session.query(UserSchedule)
            .filter_by(scan_time=scan_time, is_paused=False)
            .all()
        )
        user_ids = [s.user_id for s in schedule_rows]
        if not user_ids:
            return []
        return (
            self.session.query(User)
            .filter(User.id.in_(user_ids), User.is_active == True)
            .all()
        )
