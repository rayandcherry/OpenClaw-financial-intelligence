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

_tracker = TrackerService(initial_balance=100000)
_tracker.load_positions()


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


@mcp.tool()
def indicators(ticker: str, period: str = "1y") -> dict:
    """Get current technical indicators for a ticker."""
    return handle_indicators(ticker=ticker, period=period)


def handle_indicators(ticker, period="1y"):
    try:
        df = fetch_data(ticker, period)
        if df is None or df.empty:
            return {"error": f"No market data available for {ticker}"}
        df = calculate_indicators(df)
        latest = df.iloc[-1]
        return {
            "ticker": ticker,
            "price": round(float(latest["Close"]), 2),
            "sma_200": round(float(latest.get("SMA_200", 0)), 2),
            "ema_50": round(float(latest.get("EMA_50", 0)), 2),
            "rsi_14": round(float(latest.get("RSI_14", 0)), 2),
            "bollinger_lower": round(float(latest.get("BBL_20_2.0", 0)), 2),
            "macd": round(float(latest.get("MACD", 0)), 4),
            "macd_signal": round(float(latest.get("MACD_Signal", 0)), 4),
            "macd_hist": round(float(latest.get("MACD_Hist", 0)), 4),
            "atr_14": round(float(latest.get("ATR_14", 0)), 2),
            "volume_ratio": round(float(latest.get("RVOL", 0)), 2),
            "regime": str(latest.get("Regime", "Unknown")),
        }
    except Exception as e:
        return {"error": f"Indicators failed for {ticker}: {str(e)}"}


@mcp.tool()
def position_size(
    ticker: str, entry_price: float, stop_loss: float,
    account_balance: float, win_rate: float = 50.0, reward_ratio: float = 2.0
) -> dict:
    """Calculate position size using Kelly Criterion with VaR limits."""
    return handle_position_size(
        ticker=ticker, entry_price=entry_price, stop_loss=stop_loss,
        account_balance=account_balance, win_rate=win_rate, reward_ratio=reward_ratio
    )


def handle_position_size(ticker, entry_price, stop_loss, account_balance, win_rate=50.0, reward_ratio=2.0):
    try:
        allocator = CapitalAllocator(account_balance)
        result = allocator.calculate_position_size(
            ticker=ticker, entry_price=entry_price, stop_loss=stop_loss,
            win_rate_pct=win_rate, reward_ratio=reward_ratio
        )
        if not isinstance(result, dict):
            return {"error": "Negative edge — Kelly suggests not trading this setup", "qty": 0}
        return {
            "ticker": ticker,
            "qty": result["qty"],
            "max_loss": result["max_loss"],
            "kelly_pct": result["kelly_suggestion_pct"],
            "constraint": result["constraint"],
        }
    except Exception as e:
        return {"error": f"Position sizing failed: {str(e)}"}


@mcp.tool()
def position_add(ticker: str, entry_price: float, qty: float, side: str = "LONG", tp1: float = None) -> dict:
    """Record a new position."""
    return handle_position_add(ticker=ticker, entry_price=entry_price, qty=qty, side=side, tp1=tp1)


def handle_position_add(ticker, entry_price, qty, side="LONG", tp1=None):
    try:
        ticker = ticker.upper()
        if ticker in _tracker.positions:
            return {"error": f"Position already open for {ticker}"}
        _tracker.add_position(ticker, entry_price, qty, side=side, tp1=tp1)
        _tracker.save_positions()
        pm = _tracker.positions[ticker]
        return {
            "status": "added",
            "ticker": ticker,
            "entry_price": entry_price,
            "qty": qty,
            "side": side,
            "initial_sl": round(pm.current_sl, 2),
        }
    except Exception as e:
        return {"error": f"Failed to add position: {str(e)}"}


@mcp.tool()
def position_list() -> dict:
    """List all open positions with current P&L."""
    return handle_position_list()


def handle_position_list():
    positions = []
    for ticker, pm in _tracker.positions.items():
        positions.append({
            "ticker": ticker,
            "entry_price": pm.entry_price,
            "qty": pm.qty,
            "side": pm.side,
            "current_sl": round(pm.current_sl, 2),
            "pnl": round(pm.unrealized_pnl, 2) if hasattr(pm, 'unrealized_pnl') else 0.0,
            "health": "ACTIVE",
        })
    return {"positions": positions, "count": len(positions)}


@mcp.tool()
def position_update() -> dict:
    """Update all positions with latest market data, check for triggers."""
    return handle_position_update()


def handle_position_update():
    try:
        status_report, alerts = _tracker.update_market()
        _tracker.save_positions()
        updates = []
        for ticker, pm in _tracker.positions.items():
            updates.append({
                "ticker": ticker,
                "price": round(pm.current_price, 2) if hasattr(pm, 'current_price') else 0,
                "sl": round(pm.current_sl, 2),
                "pnl": round(pm.unrealized_pnl, 2) if hasattr(pm, 'unrealized_pnl') else 0,
            })
        return {"updates": updates, "alerts": alerts, "status_report": status_report}
    except Exception as e:
        return {"error": f"Position update failed: {str(e)}"}


@mcp.tool()
def position_remove(ticker: str) -> dict:
    """Close and remove a position."""
    return handle_position_remove(ticker=ticker)


def handle_position_remove(ticker):
    try:
        result = _tracker.remove_position(ticker)
        return result
    except Exception as e:
        return {"error": f"Failed to remove position: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
