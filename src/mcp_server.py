"""OpenClaw MCP Server — Financial intelligence tools for AI agents."""

import sys
import os

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from core.news import get_market_news

mcp = FastMCP("openclaw")


@mcp.tool()
def news(ticker: str, max_results: int = 5) -> dict:
    """Get recent market news for a ticker."""
    return handle_news(ticker=ticker, max_results=max_results)


def handle_news(ticker: str, max_results: int = 5) -> dict:
    try:
        raw = get_market_news(ticker, max_results=max_results)
        return {"ticker": ticker, "news": raw}
    except Exception as e:
        return {"error": f"News fetch failed for {ticker}: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
