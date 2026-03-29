"""
Integration test for bot services working together.
"""
import pytest


@pytest.mark.integration
def test_user_registration_and_scan_flow():
    """Full flow: register user -> add watchlist -> format report."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.bot.db.models import Base, User
    from src.bot.services.user_service import UserService
    from src.bot.services.report_formatter import ReportFormatter

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user_svc = UserService(db)

        # Register
        user = user_svc.register(telegram_id=12345, username="test_trader")
        assert user.id is not None

        # Add watchlist
        rejected = user_svc.add_tickers(user.id, ["AAPL", "NVDA", "BTC-USD"])
        assert rejected == []
        assert len(user_svc.get_watchlist(user.id)) == 3

        # Format a mock report
        fmt = ReportFormatter()
        signals = [
            {
                "ticker": "AAPL",
                "strategy": "trinity",
                "price": 150.0,
                "confidence": 82,
                "metrics": {},
                "stats": {"total": {"wr": 60.0, "count": 40}},
                "plan": {"stop_loss": 140.0, "take_profit": 170.0},
                "side": "LONG",
                "date": "2026-03-19",
            }
        ]
        messages = fmt.format_report_messages(signals, total_scanned=3)
        assert len(messages) >= 1
        assert "AAPL" in messages[0]
        assert "Trinity" in messages[0] or "trinity" in messages[0].lower()

    engine.dispose()
