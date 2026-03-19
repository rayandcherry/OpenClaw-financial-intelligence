import pytest
from src.bot.services.report_formatter import ReportFormatter


@pytest.fixture
def sample_signal():
    return {
        "ticker": "NVDA",
        "strategy": "trinity",
        "price": 142.30,
        "confidence": 85,
        "metrics": {"rsi": 48.5, "regime": "Bull", "dist_to_ema": "1.2%"},
        "stats": {"total": {"wr": 62.0, "count": 47}},
        "plan": {"stop_loss": 134.10, "take_profit": 158.70, "risk_reward": "1:2 (ATR Based)"},
        "side": "LONG",
        "date": "2026-03-19",
    }


@pytest.fixture
def formatter():
    return ReportFormatter()


def test_format_signal_card(formatter, sample_signal):
    card = formatter.format_signal_card(sample_signal)
    assert "NVDA" in card
    assert "Trinity" in card or "trinity" in card.lower()
    assert "85" in card
    assert "134.10" in card or "134.1" in card
    assert "62" in card


def test_format_report_with_signals(formatter, sample_signal):
    report = formatter.format_report([sample_signal], total_scanned=25)
    assert "1 signal" in report.lower() or "1 Signal" in report
    assert "25" in report
    assert "NVDA" in report


def test_format_report_no_signals(formatter):
    report = formatter.format_report([], total_scanned=25)
    assert "0 signal" in report.lower() or "quiet" in report.lower() or "All quiet" in report


def test_format_report_splits_long_messages(formatter, sample_signal):
    signals = [dict(sample_signal, ticker=f"T{i:03d}") for i in range(20)]
    messages = formatter.format_report_messages(signals, total_scanned=100)
    assert isinstance(messages, list)
    assert all(len(m) <= 4096 for m in messages)
    assert len(messages) >= 1


def test_strategy_emoji(formatter):
    assert formatter._strategy_emoji("trinity") == "🟢"
    assert formatter._strategy_emoji("panic") == "🔴"
    assert formatter._strategy_emoji("2B_Reversal") == "🟡"
