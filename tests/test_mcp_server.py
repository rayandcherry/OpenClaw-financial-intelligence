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
