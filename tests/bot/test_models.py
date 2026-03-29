import pytest
from src.bot.db.models import User, UserWatchlist, UserSchedule, ScanLog


def test_create_user(db):
    user = User(telegram_id=123456789, username="trader1", strategies=["TRINITY", "PANIC", "2B"])
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    assert user.telegram_id == 123456789
    assert user.lang == "EN"
    assert user.scan_mode == "ALL"
    assert user.is_active is True


def test_telegram_id_unique(db):
    db.add(User(telegram_id=111, username="a"))
    db.commit()
    db.add(User(telegram_id=111, username="b"))
    with pytest.raises(Exception):
        db.commit()


def test_user_watchlist(db):
    user = User(telegram_id=222, username="trader2")
    db.add(user)
    db.commit()
    wl = UserWatchlist(user_id=user.id, ticker="AAPL")
    db.add(wl)
    db.commit()
    assert wl.ticker == "AAPL"
    assert wl.user_id == user.id


def test_user_schedule(db):
    user = User(telegram_id=333, username="trader3")
    db.add(user)
    db.commit()
    from datetime import time
    sched = UserSchedule(user_id=user.id, scan_time=time(8, 0))
    db.add(sched)
    db.commit()
    assert sched.is_paused is False


def test_scan_log(db):
    user = User(telegram_id=444, username="trader4")
    db.add(user)
    db.commit()
    log = ScanLog(
        user_id=user.id,
        triggered_by="manual",
        tickers_count=25,
        signals_found=3,
        status="done",
        report_text="Test report",
    )
    db.add(log)
    db.commit()
    assert log.signals_found == 3
    assert log.triggered_by == "manual"
