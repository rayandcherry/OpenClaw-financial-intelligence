import pytest
from src.bot.services.report_formatter import ReportFormatter
from src.core.report_builder import classify_signal


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


def test_format_report_with_signals(formatter, sample_signal):
    report = formatter.format_report([sample_signal], total_scanned=25)
    assert "1 signal" in report.lower()
    assert "25" in report
    assert "NVDA" in report
    assert "Trinity" in report


def test_format_report_no_signals(formatter):
    report = formatter.format_report([], total_scanned=25)
    assert "quiet" in report.lower()
    assert "0 signal" in report.lower()


def test_format_report_splits_long_messages(formatter, sample_signal):
    signals = [dict(sample_signal, ticker=f"T{i:03d}") for i in range(40)]
    messages = formatter.format_report_messages(signals, total_scanned=100)
    assert isinstance(messages, list)
    assert all(len(m) <= 4096 for m in messages)
    assert len(messages) >= 1


def test_classify_take_for_high_confidence_trinity(sample_signal):
    verdict, reason = classify_signal(sample_signal)
    assert verdict == "TAKE"
    assert reason is None


def test_classify_skip_for_2b_negative_edge():
    signal = {
        "ticker": "SMCI", "strategy": "2B_Reversal", "confidence": 65,
        "stats": {}, "metrics": {"type": "Bearish 2B"},
    }
    verdict, reason = classify_signal(signal)
    assert verdict == "SKIP"
    assert "negative" in reason.lower()


def test_classify_skip_for_recent_decay():
    signal = {
        "ticker": "KMI", "strategy": "trinity", "confidence": 20,
        "stats": {"recent_decay": True, "warning": "Strategy Failure Warning"},
        "metrics": {},
    }
    verdict, reason = classify_signal(signal)
    assert verdict == "SKIP"
    assert "decay" in reason.lower()


def test_classify_watch_for_moderate_confidence():
    signal = {
        "ticker": "ABC", "strategy": "trinity", "confidence": 55,
        "stats": {}, "metrics": {},
    }
    verdict, _ = classify_signal(signal)
    assert verdict == "WATCH"


def test_report_shows_take_skip_buckets(formatter):
    signals = [
        {"ticker": "DLR", "strategy": "trinity", "confidence": 80, "price": 193.31,
         "stats": {}, "metrics": {"regime": "Bull"},
         "plan": {"stop_loss": 170.32, "take_profit": 239.29, "risk_reward": "1:2 (SMA200 floor)"},
         "side": "LONG"},
        {"ticker": "SMCI", "strategy": "2B_Reversal", "confidence": 65, "price": 32.0,
         "stats": {}, "metrics": {"type": "Bearish 2B", "regime": "Bear"},
         "plan": {"stop_loss": 36.55, "take_profit": 18.34, "risk_reward": "1:3 (Fixed)"},
         "side": "SHORT"},
    ]
    report = formatter.format_report(signals, total_scanned=75)
    assert "Take" in report
    assert "Skip" in report
    assert "DLR" in report
    assert "SMCI" in report
    assert "Strategy edge" in report


def test_report_shows_layer_attribution(formatter):
    signals = [
        {"ticker": "DLR", "strategy": "trinity", "confidence": 80, "price": 193.31,
         "stats": {}, "metrics": {"regime": "Bull"},
         "plan": {"stop_loss": 170.32, "take_profit": 239.29, "risk_reward": "1:2"},
         "side": "LONG"},
    ]
    report = formatter.format_report(signals, total_scanned=75)
    assert "Infrastructure" in report  # DLR is in AI Infrastructure preset
