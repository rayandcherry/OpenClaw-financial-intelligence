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
