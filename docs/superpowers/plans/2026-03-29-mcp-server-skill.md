# OpenClaw MCP Server + Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap OpenClaw's scanner, backtester, and tracker as a local MCP Server (10 tools) with a companion Skill that enforces trading discipline.

**Architecture:** Single `src/mcp_server.py` using MCP Python SDK (stdio transport). Directly calls existing `core/`, `backtest.py`, and `tracker/` modules. Position persistence via JSON. Skill is a standalone `.md` file.

**Tech Stack:** mcp[cli] (Python MCP SDK), existing OpenClaw modules

**Spec:** `docs/superpowers/specs/2026-03-19-mcp-server-skill-design.md`

---

## File Structure

### New Files

```
src/mcp_server.py                  # MCP server entry point with all 10 tool handlers
tests/test_mcp_server.py           # Unit tests for tool handlers
skills/openclaw-trader.md          # Skill file for Claude Code
```

### Modified Files

```
src/tracker/service.py             # Add load_positions(), save_positions(), remove_position()
requirements.txt                   # Add mcp[cli]
```

---

## Task 1: Add Persistence to TrackerService

**Files:**
- Modify: `src/tracker/service.py`
- Create: `tests/test_tracker_persistence.py`

The existing `load_positions` and `save_positions` live in `src/track.py` as standalone functions. We need to move this logic into TrackerService itself so the MCP server can use it without importing the CLI module.

- [ ] **Step 1: Write failing tests**

`tests/test_tracker_persistence.py`:
```python
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import pandas as pd
from src.tracker.service import TrackerService


@pytest.fixture
def tmp_positions_file():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def mock_fetch():
    """Mock fetch_data so add_position doesn't hit yfinance."""
    df = pd.DataFrame({"Close": [150.0], "High": [155.0], "Low": [145.0], "ATR_14": [3.5]})
    with patch("src.tracker.service.fetch_data", return_value=df):
        with patch("src.tracker.service.calculate_indicators", return_value=df):
            yield


@pytest.fixture
def service(tmp_positions_file, mock_fetch):
    svc = TrackerService(initial_balance=100000)
    svc.positions_file = tmp_positions_file
    return svc


def test_save_and_load_positions(service, tmp_positions_file, mock_fetch):
    service.add_position("AAPL", 150.0, 10, side="LONG")
    service.save_positions()

    assert os.path.exists(tmp_positions_file)
    with open(tmp_positions_file) as f:
        data = json.load(f)
    # Uses list format (compatible with existing track.py)
    assert isinstance(data, list)
    assert data[0]["ticker"] == "AAPL"

    svc2 = TrackerService(initial_balance=100000)
    svc2.positions_file = tmp_positions_file
    svc2.load_positions()
    assert "AAPL" in svc2.positions


def test_remove_position(service):
    service.add_position("NVDA", 140.0, 5, side="LONG")
    assert "NVDA" in service.positions
    result = service.remove_position("NVDA")
    assert "NVDA" not in service.positions
    assert result["ticker"] == "NVDA"


def test_remove_nonexistent_position(service):
    result = service.remove_position("FAKE")
    assert result.get("error") is not None


def test_save_empty(service, tmp_positions_file):
    service.save_positions()
    with open(tmp_positions_file) as f:
        data = json.load(f)
    assert data == []


def test_load_missing_file(service):
    service.positions_file = "/tmp/nonexistent_positions_12345.json"
    service.load_positions()
    assert service.positions == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tracker_persistence.py -v
```
Expected: FAIL — `TrackerService` has no `save_positions`, `load_positions`, `remove_position`, or `positions_file`

- [ ] **Step 3: Implement persistence methods**

Add to `src/tracker/service.py`. First read the file, then add these methods and the `positions_file` attribute. The logic is adapted from `src/track.py`'s standalone functions:

```python
import json
import os

# In __init__, add:
self.positions_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "positions.json")

# New methods:
def save_positions(self):
    os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
    # Use list format — compatible with existing src/track.py
    data = []
    for ticker, pm in self.positions.items():
        data.append({
            "ticker": ticker,
            "entry_price": pm.entry_price,
            "qty": pm.qty,
            "side": pm.side,
            "tp1": pm.tp1,
            "sl": pm.current_sl,
            "breakeven": pm.is_breakeven_active,
            "tp1_hit": pm.tp1_hit,
        })
    with open(self.positions_file, "w") as f:
        json.dump(data, f, indent=2)

def load_positions(self):
    if not os.path.exists(self.positions_file):
        return
    try:
        with open(self.positions_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    # Support list format (track.py compat)
    for item in data:
        self.add_position(
            ticker=item["ticker"],
            entry_price=item["entry_price"],
            qty=item["qty"],
            side=item.get("side", "LONG"),
            tp1=item.get("tp1"),
        )
        pm = self.positions.get(item["ticker"])
        if pm:
            if item.get("sl"):
                pm.current_sl = item["sl"]
            if item.get("breakeven"):
                pm.is_breakeven_active = True
            if item.get("tp1_hit"):
                pm.tp1_hit = True

def remove_position(self, ticker: str) -> dict:
    ticker = ticker.upper()
    if ticker not in self.positions:
        return {"error": f"No open position for {ticker}"}
    pm = self.positions[ticker]
    pnl = pm.unrealized_pnl if hasattr(pm, 'unrealized_pnl') else 0.0
    del self.positions[ticker]
    self.save_positions()
    return {"status": "removed", "ticker": ticker, "final_pnl": round(pnl, 2)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tracker_persistence.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tracker/service.py tests/test_tracker_persistence.py
git commit -m "feat(tracker): add load/save/remove position methods to TrackerService"
```

---

## Task 2: Install MCP SDK & Create Server Skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `src/mcp_server.py` (skeleton with 1 tool)
- Create: `tests/test_mcp_server.py` (first test)

- [ ] **Step 1: Add mcp dependency**

Append to `requirements.txt`:
```
mcp[cli]>=1.0
```

- [ ] **Step 2: Install**

```bash
pip install -r requirements.txt
python -c "from mcp.server.fastmcp import FastMCP; print('MCP SDK OK')"
```

- [ ] **Step 3: Write test for first tool (news — simplest)**

`tests/test_mcp_server.py`:
```python
import pytest
from unittest.mock import patch, MagicMock


def test_handle_news():
    with patch("src.core.news.get_market_news", return_value="- Title: Snippet"):
        from src.mcp_server import handle_news
        result = handle_news(ticker="AAPL", max_results=3)
    assert "AAPL" in str(result) or "Title" in str(result)
    assert "error" not in result


def test_handle_news_failure():
    with patch("src.core.news.get_market_news", side_effect=Exception("network error")):
        from src.mcp_server import handle_news
        result = handle_news(ticker="AAPL")
    assert "error" in result
```

- [ ] **Step 4: Run test to verify it fails**

```bash
pytest tests/test_mcp_server.py -v
```
Expected: FAIL — no module `src.mcp_server`

- [ ] **Step 5: Create MCP server skeleton**

`src/mcp_server.py`:
```python
"""OpenClaw MCP Server — Financial intelligence tools for AI agents."""

import sys
import os

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openclaw")


# --- Discovery Tools ---

@mcp.tool()
def news(ticker: str, max_results: int = 5) -> dict:
    """Get recent market news for a ticker."""
    return handle_news(ticker=ticker, max_results=max_results)


def handle_news(ticker: str, max_results: int = 5) -> dict:
    try:
        from core.news import get_market_news
        raw = get_market_news(ticker, max_results=max_results)
        return {"ticker": ticker, "news": raw}
    except Exception as e:
        return {"error": f"News fetch failed for {ticker}: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_mcp_server.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): server skeleton with news tool"
```

---

## Task 3: Discovery Tools (scan, scan_ticker, backtest)

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write tests for scan, scan_ticker, backtest**

Append to `tests/test_mcp_server.py`:
```python
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
    signals = [
        {"ticker": "AAPL", "strategy": "trinity"},
        {"ticker": "BTC-USD", "strategy": "panic"},
    ]
    with patch("src.mcp_server.scan_market", return_value=signals):
        from src.mcp_server import handle_scan
        result = handle_scan(tickers=["AAPL", "BTC-USD"], mode="US", strategies=None)
    # Only AAPL should be scanned (US mode)
    assert result["tickers_scanned"] == ["AAPL"]


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
            from src.mcp_server import handle_scan_ticker
            result = handle_scan_ticker(ticker="NVDA")
    assert result["signal"]["ticker"] == "NVDA"
    assert "news" in result


def test_handle_scan_ticker_no_signal():
    with patch("src.mcp_server.process_ticker", return_value=None):
        with patch("src.mcp_server.get_market_news", return_value="Some news"):
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mcp_server.py -v
```

- [ ] **Step 3: Implement scan, scan_ticker, backtest handlers**

Add to `src/mcp_server.py`:
```python
from core.scanner import scan_market, process_ticker
from core.news import get_market_news
from core.data_fetcher import fetch_data
from core.indicators import calculate_indicators
from core.cache_manager import BacktestCache
from backtest import Backtester
from tracker.service import TrackerService
from tracker.risk import CapitalAllocator
from config import US_STOCKS, CRYPTO_ASSETS

_cache = BacktestCache()


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
    allowed = {s.lower() for s in strategies}
    _map = {"trinity": {"trinity"}, "panic": {"panic"}, "2b": {"2b_reversal", "2b"}}
    expanded = set()
    for s in allowed:
        expanded.update(_map.get(s, {s}))
    return [s for s in signals if s.get("strategy", "").lower() in expanded]


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
        news = get_market_news(ticker, max_results=5)

        # Try cached backtest, fall back to fresh run
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
            "news": news,
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_mcp_server.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): add scan, scan_ticker, backtest tools"
```

---

## Task 4: Analysis Tools (indicators, position_size)

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_mcp_server.py`:
```python
def test_handle_indicators():
    import pandas as pd
    import numpy as np
    df = pd.DataFrame({
        "Open": np.random.uniform(100, 200, 250),
        "High": np.random.uniform(100, 200, 250),
        "Low": np.random.uniform(100, 200, 250),
        "Close": np.random.uniform(100, 200, 250),
        "Volume": np.random.randint(1000000, 5000000, 250),
    })
    with patch("src.mcp_server.fetch_data", return_value=df):
        with patch("src.mcp_server.calculate_indicators", return_value=df.assign(
            SMA_200=150, EMA_50=155, RSI_14=52, ATR_14=3.5,
            MACD=0.5, MACD_Signal=0.3, MACD_Hist=0.2,
            Regime="Bull", RVOL=1.1, **{"BBL_20_2.0": 140}
        )):
            from src.mcp_server import handle_indicators
            result = handle_indicators(ticker="AAPL")
    assert "price" in result
    assert "rsi_14" in result
    assert "regime" in result


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
```

- [ ] **Step 2: Run to verify fail, then implement**

Add to `src/mcp_server.py`:
```python
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
        # CapitalAllocator may return 0 (int) when Kelly edge is negative
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
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mcp_server.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): add indicators and position_size tools"
```

---

## Task 5: Execution Tools (position_add, position_list, position_update, position_remove)

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_mcp_server.py`:
```python
import tempfile
import os


@pytest.fixture
def mcp_tracker(tmp_path):
    """Set up a TrackerService with temp file for position tests."""
    from src.tracker.service import TrackerService
    svc = TrackerService(initial_balance=100000)
    svc.positions_file = str(tmp_path / "positions.json")
    return svc


def test_handle_position_add(mcp_tracker):
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_add
        result = handle_position_add(ticker="AAPL", entry_price=150.0, qty=10, side="LONG", tp1=None)
    assert result["status"] == "added"
    assert result["ticker"] == "AAPL"
    assert "AAPL" in mcp_tracker.positions


def test_handle_position_add_duplicate(mcp_tracker):
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
    mcp_tracker.add_position("AAPL", 150.0, 10)
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_list
        result = handle_position_list()
    assert result["count"] == 1
    assert result["positions"][0]["ticker"] == "AAPL"


def test_handle_position_remove(mcp_tracker):
    mcp_tracker.add_position("NVDA", 140.0, 5)
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_remove
        result = handle_position_remove(ticker="NVDA")
    assert result["status"] == "removed"
    assert "NVDA" not in mcp_tracker.positions


def test_handle_position_remove_nonexistent(mcp_tracker):
    with patch("src.mcp_server._tracker", mcp_tracker):
        from src.mcp_server import handle_position_remove
        result = handle_position_remove(ticker="FAKE")
    assert "error" in result
```

- [ ] **Step 2: Run to verify fail, then implement**

Add to `src/mcp_server.py`:
```python
# Module-level tracker instance (loaded once at startup)
_tracker = TrackerService(initial_balance=100000)
_tracker.load_positions()


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
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mcp_server.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): add position management tools (add, list, update, remove)"
```

---

## Task 6: Skill File

**Files:**
- Create: `skills/openclaw-trader.md`

- [ ] **Step 1: Create the skill file**

`skills/openclaw-trader.md`:
```markdown
---
name: openclaw-trader
description: Use when user asks about trading signals, market scanning, position management, or portfolio sizing. Enforces disciplined Golden Workflow — scan → verify → size → confirm → execute.
---

# OpenClaw Trading Intelligence

You are an Elite Financial Intelligence Officer with access to OpenClaw's market scanning and position management tools via MCP.

## Your Capabilities

You have 10 MCP tools from the `openclaw` server:

| Tool | Purpose |
|------|---------|
| `scan` | Scan multiple tickers for signals (Trinity, Panic, 2B strategies) |
| `scan_ticker` | Deep analysis of a single ticker (signal + news + backtest) |
| `backtest` | Historical backtest for a ticker/strategy |
| `news` | Recent market news for a ticker |
| `indicators` | Technical indicator snapshot (RSI, MACD, Bollinger, ATR, Regime) |
| `position_size` | Kelly Criterion position sizing with VaR limits |
| `position_add` | Record a new position |
| `position_list` | List all open positions |
| `position_update` | Update positions with latest market data |
| `position_remove` | Close a position |

## Strategy Knowledge

**Trinity (Trend Pullback):** Price above SMA200, pulling back near EMA50, RSI 40-60. Conservative trend-following with 1:2 risk/reward.

**Panic (Mean Reversion):** Price below Bollinger lower band, RSI under 30, volume spike. Capitulation bottom play with 1:3 risk/reward.

**2B Reversal (Swing Failure):** False breakout of prior high/low, confirmed by RSI divergence or MACD histogram shrinkage. Counter-trend with tight stops.

## Golden Workflow (MANDATORY)

When a user asks about trading opportunities, signals, or wants to act on a ticker, you MUST follow this workflow in order. **Never skip steps.**

### Step 1: SCAN
Call `scan` or `scan_ticker` to find signals.
- If no signals found → tell user "No opportunities found right now" → STOP

### Step 2: VERIFY
Call `backtest` for each signal found.
- If win rate ≤ 50% → warn: "Backtest doesn't support this signal (WR: X%). Not recommended." → STOP
- Show: win rate, trade count, regime breakdown (Bull/Bear/Sideways)

### Step 3: SIZE
Call `position_size` with the signal's stop-loss level and user's account balance.
- If user hasn't told you their balance, ASK before proceeding
- Show: suggested quantity, maximum loss, Kelly percentage

### Step 4: CONFIRM (HARD GATE)
Present the complete picture:
- Signal: strategy, confidence, entry price
- Risk: stop-loss, take-profit, risk/reward ratio
- Backtest: win rate, sample size
- Sizing: quantity, max loss

Then ask: **"Do you want to record this position?"**
- Wait for explicit "yes" → proceed to Step 5
- Anything else → STOP
- **NEVER auto-execute. NEVER assume confirmation.**

### Step 5: EXECUTE
Call `position_add` with the confirmed parameters.
- Confirm: "Position recorded for [TICKER] at $[PRICE], [QTY] shares, SL at $[SL]"

### Step 6: MONITOR
Remind user: "Use position_update to check your positions and trigger stop-loss/take-profit levels."

## Rules

- **Never skip backtest verification (Step 2)** — even if user says "just buy it"
- **Never execute without confirmation (Step 4)** — this is non-negotiable
- **Always show stop-loss and take-profit levels** when presenting signals
- **Always include regime context** (Bull/Bear/Sideways) from backtest
- **Always end trading discussions with:** "⚠️ Not financial advice. Do your own research."
- **Follow user's language** — respond in the same language the user writes in

## Position Management

When user asks about existing positions:
- Call `position_list` to show current state
- Call `position_update` to refresh with latest prices
- Explain any alerts (breakeven triggered, trailing stop moved, TP1 hit)
- For closing: call `position_remove` after user confirms

## When NOT to Use This Skill

- General coding questions
- Non-financial topics
- Questions about the OpenClaw codebase itself (use normal code exploration)
```

- [ ] **Step 2: Commit**

```bash
mkdir -p skills
git add skills/openclaw-trader.md
git commit -m "feat(skill): add openclaw-trader skill with Golden Workflow discipline"
```

---

## Task 7: Integration Test & Registration

**Files:**
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write integration test**

Append to `tests/test_mcp_server.py`:
```python
def test_full_workflow_integration(mcp_tracker):
    """Integration: scan → backtest → size → add → list → remove."""
    signal = {
        "ticker": "AAPL", "strategy": "trinity", "confidence": 85,
        "price": 150.0, "plan": {"stop_loss": 140, "take_profit": 170},
        "stats": {"total": {"wr": 62, "count": 47}}, "side": "LONG",
        "date": "2026-03-29", "metrics": {}
    }

    with patch("src.mcp_server._tracker", mcp_tracker):
        with patch("src.mcp_server.scan_market", return_value=[signal]):
            from src.mcp_server import handle_scan, handle_backtest, handle_position_size
            from src.mcp_server import handle_position_add, handle_position_list, handle_position_remove

            # Step 1: Scan
            scan_result = handle_scan(tickers=["AAPL"])
            assert scan_result["count"] == 1

        # Step 2: Backtest (mock)
        with patch("src.mcp_server.Backtester") as MockBT:
            instance = MagicMock()
            instance.get_summary_metrics.return_value = {"roi": 15, "wr": 62, "trades": 47, "pnl": 15000}
            MockBT.return_value = instance
            bt_result = handle_backtest(ticker="AAPL", period="3y")
            assert bt_result["win_rate"] == 62

        # Step 3: Size
        size_result = handle_position_size(
            ticker="AAPL", entry_price=150, stop_loss=140,
            account_balance=100000, win_rate=62
        )
        assert size_result["qty"] > 0

        # Step 4: (User confirms — not testable here)

        # Step 5: Add
        add_result = handle_position_add(ticker="AAPL", entry_price=150, qty=size_result["qty"], side="LONG", tp1=170)
        assert add_result["status"] == "added"

        # Step 6: List
        list_result = handle_position_list()
        assert list_result["count"] == 1

        # Cleanup: Remove
        remove_result = handle_position_remove(ticker="AAPL")
        assert remove_result["status"] == "removed"

        final_list = handle_position_list()
        assert final_list["count"] == 0
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/test_mcp_server.py -v
```
Expected: ALL PASS

- [ ] **Step 3: Run existing tests to confirm no regressions**

```bash
pytest tests/ -v --tb=short
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_mcp_server.py
git commit -m "test(mcp): add full Golden Workflow integration test"
```

---

## Summary

| Task | What It Builds | Key Files |
|------|---------------|-----------|
| 1 | TrackerService persistence + remove | tracker/service.py |
| 2 | MCP skeleton + news tool | mcp_server.py |
| 3 | Discovery tools (scan, scan_ticker, backtest) | mcp_server.py |
| 4 | Analysis tools (indicators, position_size) | mcp_server.py |
| 5 | Execution tools (position CRUD) | mcp_server.py |
| 6 | Skill file (Golden Workflow) | skills/openclaw-trader.md |
| 7 | Integration test + registration | tests/test_mcp_server.py |

After all tasks, register with:
```bash
claude mcp add openclaw -- python src/mcp_server.py
```
