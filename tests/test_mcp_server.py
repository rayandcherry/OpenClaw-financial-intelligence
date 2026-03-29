import pytest
from unittest.mock import patch, MagicMock


def test_handle_news():
    with patch("src.mcp_server.get_market_news", return_value="- Title: Snippet"):
        from src.mcp_server import handle_news
        result = handle_news(ticker="AAPL", max_results=3)
    assert "news" in result
    assert "error" not in result


def test_handle_news_failure():
    with patch("src.mcp_server.get_market_news", side_effect=Exception("network error")):
        from src.mcp_server import handle_news
        result = handle_news(ticker="AAPL")
    assert "error" in result


def test_handle_scan():
    signal = {
        "ticker": "AAPL", "strategy": "trinity", "confidence": 80,
        "price": 150.0, "plan": {"stop_loss": 140, "take_profit": 170},
        "stats": {"total": {"wr": 60, "count": 30}}, "side": "LONG",
        "date": "2026-03-29", "metrics": {}
    }
    with patch("src.mcp_server.scan_market", return_value=[signal]):
        from src.mcp_server import handle_scan
        result = handle_scan(tickers=["AAPL", "NVDA"], mode="ALL", strategies=None)
    assert len(result["signals"]) == 1
    assert result["signals"][0]["ticker"] == "AAPL"


def test_handle_scan_with_mode_filter():
    with patch("src.mcp_server.scan_market", return_value=[]) as mock_scan:
        from src.mcp_server import handle_scan
        result = handle_scan(tickers=["AAPL", "BTC-USD"], mode="US", strategies=None)
    # scan_market should only receive US tickers
    called_tickers = mock_scan.call_args[0][0]
    assert "AAPL" in called_tickers
    assert "BTC-USD" not in called_tickers


def test_handle_scan_empty():
    with patch("src.mcp_server.scan_market", return_value=[]):
        from src.mcp_server import handle_scan
        result = handle_scan()
    assert result["signals"] == []
    assert result["count"] == 0


def test_handle_scan_ticker():
    signal = {"ticker": "NVDA", "strategy": "trinity", "confidence": 85}
    with patch("src.mcp_server.process_ticker", return_value=signal):
        with patch("src.mcp_server.get_market_news", return_value="Good news"):
            with patch("src.mcp_server._cache") as mock_cache:
                mock_cache.get.return_value = {"wr": 60, "trades": 30}
                from src.mcp_server import handle_scan_ticker
                result = handle_scan_ticker(ticker="NVDA")
    assert result["signal"]["ticker"] == "NVDA"
    assert "news" in result
    assert result["backtest"] is not None


def test_handle_scan_ticker_no_signal():
    with patch("src.mcp_server.process_ticker", return_value=None):
        with patch("src.mcp_server.get_market_news", return_value="Some news"):
            with patch("src.mcp_server._cache") as mock_cache:
                mock_cache.get.return_value = None
                with patch("src.mcp_server.Backtester") as MockBT:
                    instance = MagicMock()
                    instance.get_summary_metrics.return_value = {"wr": 50}
                    MockBT.return_value = instance
                    from src.mcp_server import handle_scan_ticker
                    result = handle_scan_ticker(ticker="MSFT")
    assert result["signal"] is None


def test_handle_backtest():
    with patch("src.mcp_server.Backtester") as MockBT:
        instance = MagicMock()
        instance.get_summary_metrics.return_value = {
            "roi": 15.2, "wr": 62.0, "trades": 47, "pnl": 15200.0
        }
        MockBT.return_value = instance
        from src.mcp_server import handle_backtest
        result = handle_backtest(ticker="AAPL", period="3y", strategy=None)
    assert result["roi"] == 15.2
    assert result["win_rate"] == 62.0


def test_handle_backtest_failure():
    with patch("src.mcp_server.Backtester", side_effect=Exception("no data")):
        from src.mcp_server import handle_backtest
        result = handle_backtest(ticker="FAKE", period="3y")
    assert "error" in result


import numpy as np
import pandas as pd
import tempfile
import os


def test_handle_indicators():
    df = pd.DataFrame({
        "Open": np.random.uniform(100, 200, 250),
        "High": np.random.uniform(100, 200, 250),
        "Low": np.random.uniform(100, 200, 250),
        "Close": np.random.uniform(100, 200, 250),
        "Volume": np.random.randint(1000000, 5000000, 250),
    })
    result_df = df.copy()
    result_df["SMA_200"] = 150.0
    result_df["EMA_50"] = 155.0
    result_df["RSI_14"] = 52.0
    result_df["ATR_14"] = 3.5
    result_df["MACD"] = 0.5
    result_df["MACD_Signal"] = 0.3
    result_df["MACD_Hist"] = 0.2
    result_df["Regime"] = "Bull"
    result_df["RVOL"] = 1.1
    result_df["BBL_20_2.0"] = 140.0

    with patch("src.mcp_server.fetch_data", return_value=df):
        with patch("src.mcp_server.calculate_indicators", return_value=result_df):
            from src.mcp_server import handle_indicators
            result = handle_indicators(ticker="AAPL")
    assert "price" in result
    assert "rsi_14" in result
    assert "regime" in result
    assert "error" not in result


def test_handle_indicators_no_data():
    with patch("src.mcp_server.fetch_data", return_value=None):
        from src.mcp_server import handle_indicators
        result = handle_indicators(ticker="FAKE")
    assert "error" in result


def test_handle_position_size():
    from src.mcp_server import handle_position_size
    result = handle_position_size(
        ticker="AAPL", entry_price=150.0, stop_loss=140.0,
        account_balance=100000, win_rate=60.0, reward_ratio=2.0
    )
    assert "qty" in result
    assert "max_loss" in result
    assert result["qty"] > 0


@pytest.fixture
def mcp_tracker(tmp_path):
    from src.tracker.service import TrackerService
    svc = TrackerService(initial_balance=100000)
    svc.positions_file = str(tmp_path / "positions.json")
    return svc


def test_handle_position_add(mcp_tracker):
    mock_df = pd.DataFrame({"Close": [150.0], "High": [155.0], "Low": [145.0], "ATR_14": [3.5]})
    with patch("src.mcp_server._tracker", mcp_tracker):
        with patch("src.tracker.service.fetch_data", return_value=mock_df):
            with patch("src.tracker.service.calculate_indicators", return_value=mock_df):
                from src.mcp_server import handle_position_add
                result = handle_position_add(ticker="AAPL", entry_price=150.0, qty=10, side="LONG", tp1=None)
    assert result["status"] == "added"
    assert result["ticker"] == "AAPL"


def test_handle_position_add_duplicate(mcp_tracker):
    mock_df = pd.DataFrame({"Close": [150.0], "High": [155.0], "Low": [145.0], "ATR_14": [3.5]})
    with patch("src.tracker.service.fetch_data", return_value=mock_df):
        with patch("src.tracker.service.calculate_indicators", return_value=mock_df):
            mcp_tracker.add_position("AAPL", 150.0, 10)
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_add
        result = handle_position_add(ticker="AAPL", entry_price=160.0, qty=5, side="LONG", tp1=None)
    assert "error" in result


def test_handle_position_list_empty(mcp_tracker):
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_list
        result = handle_position_list()
    assert result["positions"] == []
    assert result["count"] == 0


def test_handle_position_list_with_positions(mcp_tracker):
    mock_df = pd.DataFrame({"Close": [150.0], "High": [155.0], "Low": [145.0], "ATR_14": [3.5]})
    with patch("src.tracker.service.fetch_data", return_value=mock_df):
        with patch("src.tracker.service.calculate_indicators", return_value=mock_df):
            mcp_tracker.add_position("AAPL", 150.0, 10)
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_list
        result = handle_position_list()
    assert result["count"] == 1
    assert result["positions"][0]["ticker"] == "AAPL"


def test_handle_position_remove(mcp_tracker):
    mock_df = pd.DataFrame({"Close": [140.0], "High": [145.0], "Low": [135.0], "ATR_14": [3.0]})
    with patch("src.tracker.service.fetch_data", return_value=mock_df):
        with patch("src.tracker.service.calculate_indicators", return_value=mock_df):
            mcp_tracker.add_position("NVDA", 140.0, 5)
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_remove
        result = handle_position_remove(ticker="NVDA")
    assert result["status"] == "removed"


def test_handle_position_remove_nonexistent(mcp_tracker):
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_remove
        result = handle_position_remove(ticker="FAKE")
    assert "error" in result
