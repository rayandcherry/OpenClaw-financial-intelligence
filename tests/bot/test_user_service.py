import pytest
from datetime import time
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.bot.db.models import Base, User, UserWatchlist, UserSchedule
from src.bot.services.user_service import UserService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def svc(db):
    return UserService(db)


def test_register_new_user(svc, db):
    user = svc.register(telegram_id=111, username="alice")
    assert user.id is not None
    assert user.telegram_id == 111
    assert user.is_active is True


def test_register_existing_reactivates(svc, db):
    user1 = svc.register(telegram_id=222, username="bob")
    user1.is_active = False
    db.commit()
    user2 = svc.register(telegram_id=222, username="bob_updated")
    assert user2.id == user1.id
    assert user2.is_active is True
    assert user2.username == "bob_updated"


def test_get_by_telegram_id(svc, db):
    svc.register(telegram_id=333, username="carol")
    user = svc.get_by_telegram_id(333)
    assert user is not None
    assert user.username == "carol"


def test_get_by_telegram_id_not_found(svc, db):
    assert svc.get_by_telegram_id(999) is None


def test_set_watchlist(svc, db):
    user = svc.register(telegram_id=444, username="dave")
    svc.add_tickers(user.id, ["AAPL", "NVDA", "BTC-USD"])
    tickers = svc.get_watchlist(user.id)
    assert set(tickers) == {"AAPL", "NVDA", "BTC-USD"}


def test_add_tickers_deduplicates(svc, db):
    user = svc.register(telegram_id=555, username="eve")
    svc.add_tickers(user.id, ["AAPL", "NVDA"])
    svc.add_tickers(user.id, ["AAPL", "MSFT"])
    tickers = svc.get_watchlist(user.id)
    assert sorted(tickers) == ["AAPL", "MSFT", "NVDA"]


def test_remove_ticker(svc, db):
    user = svc.register(telegram_id=666, username="frank")
    svc.add_tickers(user.id, ["AAPL", "NVDA"])
    svc.remove_ticker(user.id, "AAPL")
    assert svc.get_watchlist(user.id) == ["NVDA"]


def test_watchlist_cap(svc, db):
    user = svc.register(telegram_id=777, username="grace")
    tickers = [f"T{i}" for i in range(50)]
    svc.add_tickers(user.id, tickers)
    over = svc.add_tickers(user.id, ["EXTRA"])
    assert over == ["EXTRA"]


def test_set_schedule(svc, db):
    user = svc.register(telegram_id=888, username="heidi")
    svc.set_schedules(user.id, [time(8, 0), time(20, 0)])
    scheds = svc.get_schedules(user.id)
    assert len(scheds) == 2


def test_update_preferences(svc, db):
    user = svc.register(telegram_id=999, username="ivan")
    svc.update_preferences(user.id, lang="ZH", scan_mode="CRYPTO")
    user = svc.get_by_telegram_id(999)
    assert user.lang == "ZH"
    assert user.scan_mode == "CRYPTO"


def test_deactivate(svc, db):
    user = svc.register(telegram_id=1010, username="judy")
    svc.deactivate(user.id)
    user = svc.get_by_telegram_id(1010)
    assert user.is_active is False
