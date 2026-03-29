"""OpenClaw MCP Server — Financial intelligence tools for AI agents."""

import sys
import os

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from core.news import get_market_news
from core.scanner import scan_market, process_ticker
from core.data_fetcher import fetch_data
from core.indicators import calculate_indicators
from core.cache_manager import BacktestCache
from backtest import Backtester
from tracker.service import TrackerService
from tracker.risk import CapitalAllocator
from config import US_STOCKS, CRYPTO_ASSETS

_cache = BacktestCache()

mcp = FastMCP("openclaw")


def _filter_tickers_by_mode(tickers, mode):
    if not mode or mode == "ALL":
        return tickers
    if mode == "CRYPTO":
        return [t for t in tickers if t.endswith("-USD")]
    if mode == "US":
        return [t for t in tickers if not t.endswith("-USD")]
    return tickers


def _filter_signals_by_strategy(signals, strategies):
    if not strategies:
        return signals
    _map = {"trinity": {"trinity"}, "panic": {"panic"}, "2b": {"2b_reversal", "2b"}}
    expanded = set()
    for s in strategies:
        expanded.update(_map.get(s.lower(), {s.lower()}))
    return [s for s in signals if s.get("strategy", "").lower() in expanded]


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


@mcp.tool()
def scan(tickers: list[str] = None, mode: str = "ALL", strategies: list[str] = None) -> dict:
    """Scan tickers for trading signals using Trinity, Panic, and 2B strategies."""
    return handle_scan(tickers=tickers, mode=mode, strategies=strategies)


def handle_scan(tickers=None, mode="ALL", strategies=None):
    try:
        if tickers is None:
            tickers = US_STOCKS + CRYPTO_ASSETS
        tickers = _filter_tickers_by_mode(tickers, mode)
        signals = scan_market(tickers)
        signals = _filter_signals_by_strategy(signals, strategies)
        return {"signals": signals, "count": len(signals), "tickers_scanned": tickers}
    except Exception as e:
        return {"error": f"Scan failed: {str(e)}", "signals": [], "count": 0}


@mcp.tool()
def scan_ticker(ticker: str) -> dict:
    """Deep scan a single ticker — signal check, news, and backtest stats."""
    return handle_scan_ticker(ticker=ticker)


def handle_scan_ticker(ticker):
    try:
        signal = process_ticker(ticker)
        news_text = get_market_news(ticker, max_results=5)

        cached = _cache.get(ticker, "3y")
        if cached:
            backtest_stats = cached
        else:
            try:
                bt = Backtester([ticker], "3y")
                bt.load_data()
                bt.run()
                backtest_stats = bt.get_summary_metrics()
                _cache.set(ticker, "3y", backtest_stats)
            except Exception:
                backtest_stats = None

        return {
            "ticker": ticker,
            "signal": signal,
            "news": news_text,
            "backtest": backtest_stats,
        }
    except Exception as e:
        return {"error": f"Scan failed for {ticker}: {str(e)}"}


@mcp.tool()
def backtest(ticker: str, period: str = "3y", strategy: str = None) -> dict:
    """Run historical backtest for a ticker/strategy combination."""
    return handle_backtest(ticker=ticker, period=period, strategy=strategy)


def handle_backtest(ticker, period="3y", strategy=None):
    try:
        strategies = [strategy] if strategy else None
        bt = Backtester([ticker], period)
        bt.load_data()
        bt.run(strategies=strategies)
        metrics = bt.get_summary_metrics()
        return {
            "ticker": ticker,
            "period": period,
            "roi": metrics.get("roi"),
            "win_rate": metrics.get("wr"),
            "total_trades": metrics.get("trades"),
            "pnl": metrics.get("pnl"),
        }
    except Exception as e:
        return {"error": f"Backtest failed for {ticker}: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
