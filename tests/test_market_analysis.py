from unittest.mock import patch

import pandas as pd
import pytest

from src.core.market_analysis import (
    GaugeReading,
    fetch_market_snapshot,
    format_market_block,
    sentiment_verdict,
)


def _mock_df(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes})


def test_sentiment_risk_on():
    # SPY +0.5%, QQQ +0.8%, VIX 13 (low) → 風險偏好
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 585.0, 0.5, 1.0),
        GaugeReading("QQQ", "QQQ", "納指100", 510.0, 0.8, 1.5),
        GaugeReading("^VIX", "VIX", "恐慌指數", 13.0, -2.0, -5.0),
    ]
    assert "風險偏好" in sentiment_verdict(readings)


def test_sentiment_risk_off():
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 580.0, -1.5, -2.5),
        GaugeReading("QQQ", "QQQ", "納指100", 500.0, -2.0, -3.0),
        GaugeReading("^VIX", "VIX", "恐慌指數", 25.0, 8.0, 15.0),
    ]
    assert "避險" in sentiment_verdict(readings)


def test_sentiment_neutral_mixed():
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 585.0, 0.3, 1.0),
        GaugeReading("QQQ", "QQQ", "納指100", 510.0, -0.4, -0.5),
        GaugeReading("^VIX", "VIX", "恐慌指數", 17.0, 0.0, 1.0),
    ]
    assert "中性" in sentiment_verdict(readings)


def test_format_block_renders_all_lines():
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 585.20, 0.41, 1.20),
        GaugeReading("^VIX", "VIX", "恐慌指數", 13.50, -1.20, -5.30),
        GaugeReading("^TNX", "10Y", "10年期殖利率", 4.42, 0.05, 0.50),
        GaugeReading("DX-Y.NYB", "DXY", "美元指數", 104.20, 0.10, 0.30),
    ]
    block = format_market_block(readings, include_commentary=False)
    assert "📈 *大盤*" in block
    assert "SPY" in block
    assert "$585.20" in block
    assert "13.50" in block  # VIX no $ sign
    assert "4.42%" in block  # 10Y already in percentage form
    assert "情緒" in block


def test_format_block_empty():
    block = format_market_block([], include_commentary=False)
    assert "暫無數據" in block


def test_format_block_with_commentary_string():
    """Pre-built commentary string is injected verbatim under 今日要點."""
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 585.20, 0.41, 1.20),
    ]
    block = format_market_block(
        readings, commentary="CPI 2.3%略低於預期，市場提前反映降息。"
    )
    assert "📝 *今日要點*" in block
    assert "CPI 2.3%略低於預期" in block


def test_format_block_skips_commentary_when_empty_string():
    """Empty commentary string suppresses the 今日要點 section."""
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 585.20, 0.41, 1.20),
    ]
    block = format_market_block(readings, commentary="")
    assert "今日要點" not in block


def test_fetch_commentary_returns_empty_on_llm_failure():
    """LLM exceptions should NOT propagate — report must still render."""
    from src.core.market_analysis import fetch_market_commentary
    readings = [
        GaugeReading("SPY", "SPY", "標普500", 585.20, 0.41, 1.20),
    ]
    # Patch GeminiClient import inside fetch_market_commentary to raise.
    with patch("src.core.llm_client.GeminiClient",
                side_effect=RuntimeError("no API key")):
        result = fetch_market_commentary(readings)
    assert result == ""


def test_fetch_commentary_returns_empty_for_empty_readings():
    from src.core.market_analysis import fetch_market_commentary
    assert fetch_market_commentary([]) == ""


def test_fetch_market_snapshot_skips_failed_fetches():
    """When a gauge fetch returns None or empty data, it's silently skipped."""

    def fake_fetch(symbol, period="2y"):
        if symbol == "SPY":
            return _mock_df([580, 581, 582, 583, 584, 585])
        return None  # All others fail

    with patch("src.core.market_analysis.fetch_data", side_effect=fake_fetch):
        readings = fetch_market_snapshot()

    assert len(readings) == 1
    assert readings[0].display == "SPY"
    # +1d: (585-584)/584 ≈ 0.171%
    assert readings[0].chg_pct == pytest.approx(0.171, abs=0.01)
    # +5d: (585-580)/580 ≈ 0.862%
    assert readings[0].chg_5d_pct == pytest.approx(0.862, abs=0.01)


def test_fetch_market_snapshot_handles_short_history():
    """Less than 6 bars → can't compute 5d % → skip gauge."""
    def fake_fetch(symbol, period="2y"):
        return _mock_df([100, 101, 102])  # only 3 bars

    with patch("src.core.market_analysis.fetch_data", side_effect=fake_fetch):
        readings = fetch_market_snapshot()
    assert readings == []
