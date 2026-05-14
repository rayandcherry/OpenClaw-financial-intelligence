import pytest
from src.bot.services.report_formatter import ReportFormatter
from src.core.report_builder import classify_signal, _fmt_news_lines, _fmt_track_line


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


def test_fmt_news_lines_empty():
    assert _fmt_news_lines(None) == []
    assert _fmt_news_lines("") == []
    assert _fmt_news_lines("No recent news found.") == []
    assert _fmt_news_lines("Could not fetch news: timeout") == []


def test_fmt_news_lines_parses_titles_only():
    raw = "- NVIDIA Q1 beat: data center revenue strong\n- GTC keynote: next-gen roadmap"
    out = _fmt_news_lines(raw)
    assert out == ["  📰 NVIDIA Q1 beat", "  📰 GTC keynote"]


def test_fmt_news_lines_caps_at_max():
    raw = "\n".join(f"- Headline {i}: body" for i in range(5))
    assert len(_fmt_news_lines(raw, max_items=2)) == 2


def test_fmt_track_line_skips_no_trades():
    assert _fmt_track_line(None) == ""
    assert _fmt_track_line({"roi": 0, "wr": 0, "trades": 0, "pnl": 0}) == ""


def test_fmt_track_line_renders_wr_and_trades():
    out = _fmt_track_line({"roi": 312.5, "wr": 71.4, "trades": 18, "pnl": 5000})
    assert "WR 71.4%" in out and "18 trades" in out
    # ROI intentionally dropped — misleading on single-ticker portfolio backtests.
    assert "ROI" not in out


def test_take_signal_includes_news_and_track(formatter):
    signal = {
        "ticker": "NVDA", "strategy": "donchian", "confidence": 90, "price": 235.09,
        "stats": {}, "metrics": {"regime": "Bull"},
        "plan": {"stop_loss": 220.72, "take_profit": 263.83, "risk_reward": "1:2 (ATR Based)"},
        "side": "LONG",
        "sim_stats": {"roi": 312.5, "wr": 71.0, "trades": 18, "pnl": 5000},
        "news": "- NVIDIA Q1 beat: data center revenue strong\n- GTC keynote: roadmap unveiled",
    }
    report = formatter.format_report([signal], total_scanned=1)
    assert "3y track: WR 71.0%" in report
    assert "18 trades" in report
    assert "📰 NVIDIA Q1 beat" in report
    assert "📰 GTC keynote" in report


def test_watch_signal_excludes_news_and_track(formatter):
    """News + track only render under TAKE — WATCH/SKIP stay terse."""
    signal = {
        "ticker": "XYZ", "strategy": "trinity", "confidence": 55, "price": 100.0,
        "stats": {}, "metrics": {"regime": "Sideways"},
        "plan": {"stop_loss": 95, "take_profit": 110, "risk_reward": "1:2"},
        "side": "LONG",
        "sim_stats": {"roi": 100, "wr": 60, "trades": 10, "pnl": 1000},
        "news": "- Big headline: body",
    }
    report = formatter.format_report([signal], total_scanned=1)
    assert "📰" not in report
    assert "3y track" not in report


def test_report_shows_layer_attribution(formatter):
    signals = [
        {"ticker": "DLR", "strategy": "trinity", "confidence": 80, "price": 193.31,
         "stats": {}, "metrics": {"regime": "Bull"},
         "plan": {"stop_loss": 170.32, "take_profit": 239.29, "risk_reward": "1:2"},
         "side": "LONG"},
    ]
    report = formatter.format_report(signals, total_scanned=75)
    assert "Infrastructure" in report  # DLR is in AI Infrastructure preset
