# OpenClaw MCP Server + Skill Design

## Overview

Wrap OpenClaw's scanner, backtester, and position tracker as an MCP Server so any AI client (Claude Code, Claude Desktop, Cursor) can use natural language to discover trading signals, verify them, and manage positions. A companion Skill enforces the Golden Workflow discipline — AI cannot skip backtesting or build positions without user confirmation.

**Target user:** Self first, designed for future distribution.

**Transport:** stdio (local). SSE can be added later for remote access.

**Persistence:** `data/positions.json` (existing TrackerService, no database required).

**New dependency:** `mcp[cli]` only.

## Architecture

```
Claude Code / Claude Desktop
       │ stdio (JSON-RPC)
       ▼
src/mcp_server.py
    ├── core/scanner.py         (scan_market, process_ticker)
    ├── core/indicators.py      (calculate_indicators)
    ├── core/data_fetcher.py    (fetch_data)
    ├── core/news.py            (get_market_news)
    ├── backtest.py             (Backtester, Portfolio)
    ├── tracker/service.py      (TrackerService → data/positions.json)
    ├── tracker/risk.py         (CapitalAllocator)
    └── config.py               (strategy params, asset lists)
```

Single process. MCP server directly calls existing modules — no bot layer, no Redis, no Postgres, no Docker required.

## MCP Tools

### Discovery (read-only)

**`scan`**
- Description: Scan tickers for trading signals using Trinity, Panic, and 2B strategies
- Parameters:
  - `tickers` (string[], optional): Tickers to scan. Defaults to US_STOCKS + CRYPTO_ASSETS from config
  - `mode` (string, optional): "US", "CRYPTO", or "ALL" (default "ALL")
  - `strategies` (string[], optional): Filter to specific strategies. Default all three
- Returns: Array of signal objects `{ticker, strategy, confidence, price, plan: {stop_loss, take_profit}, stats, side}`
- Wraps: `scanner.scan_market()` with optional filtering

**`scan_ticker`**
- Description: Deep scan a single ticker — indicators, signal check, news, backtest stats
- Parameters:
  - `ticker` (string, required): e.g. "NVDA", "BTC-USD"
- Returns: `{signal: {...} | null, indicators: {rsi, macd, regime, ...}, news: string, backtest: {wr, count, ...}}`
- Wraps: `process_ticker()` + `get_market_news()` + `BacktestCache` or fresh `Backtester` run

**`backtest`**
- Description: Run historical backtest for a ticker/strategy combination
- Parameters:
  - `ticker` (string, required)
  - `period` (string, optional): Default "3y"
  - `strategy` (string, optional): "TRINITY", "PANIC", "2B", or all
- Returns: `{roi, win_rate, total_trades, per_strategy: {...}, per_regime: {bull, bear, sideways}}`
- Wraps: `Backtester(tickers, period).run()` + `generate_report()`

**`news`**
- Description: Get recent market news for a ticker
- Parameters:
  - `ticker` (string, required)
  - `max_results` (int, optional): Default 5
- Returns: `{articles: [{title, date, source, snippet}]}`
- Wraps: `news.get_market_news()`

### Analysis (read-only)

**`indicators`**
- Description: Get current technical indicators for a ticker
- Parameters:
  - `ticker` (string, required)
  - `period` (string, optional): Default "1y"
- Returns: `{price, sma_200, ema_50, rsi_14, bollinger: {upper, lower}, macd: {value, signal, hist}, atr_14, volume_ratio, regime}`
- Wraps: `data_fetcher.fetch_data()` + `indicators.calculate_indicators()`

**`position_size`**
- Description: Calculate position size using Kelly Criterion with VaR limits
- Parameters:
  - `ticker` (string, required)
  - `entry_price` (float, required)
  - `stop_loss` (float, required)
  - `account_balance` (float, required)
  - `win_rate` (float, optional): Default 50%
  - `reward_ratio` (float, optional): Default 2.0
- Returns: `{qty, max_loss, kelly_pct, constraint}`
- Wraps: `risk.CapitalAllocator.calculate_position_size()`

### Execution (read-write)

**`position_add`**
- Description: Record a new position
- Parameters:
  - `ticker` (string, required)
  - `entry_price` (float, required)
  - `qty` (float, required)
  - `side` (string, optional): "LONG" or "SHORT", default "LONG"
  - `tp1` (float, optional): Take profit target
- Returns: `{status: "added", ticker, entry_price, qty, initial_sl}`
- Wraps: `TrackerService.add_position()`

**`position_list`**
- Description: List all open positions with current P&L
- Parameters: none
- Returns: `{positions: [{ticker, entry_price, qty, side, current_sl, pnl, health}]}`
- Wraps: `TrackerService.positions` dict

**`position_update`**
- Description: Update all positions with latest market data, check for stop-loss/take-profit triggers
- Parameters: none
- Returns: `{updates: [{ticker, price, sl, pnl, action}], alerts: [string]}`
- Wraps: `TrackerService.update_market()`

**`position_remove`**
- Description: Close and remove a position
- Parameters:
  - `ticker` (string, required)
- Returns: `{status: "removed", ticker, final_pnl}`
- Wraps: `TrackerService` position removal

## Skill: openclaw-trader

File: `skills/openclaw-trader.md`

### Role Definition

Elite Financial Intelligence Officer. Understands three strategies:

- **Trinity (Trend Pullback):** Price > SMA200, near EMA50, RSI 40-60. Conservative trend-following.
- **Panic (Mean Reversion):** Below Bollinger lower band, RSI < 30, elevated volume. Capitulation bottoms.
- **2B Reversal:** False breakout of prior high/low, RSI divergence. Swing failure pattern.

Communicates in the user's language. Reports include risk/reward ratios, backtest context, and clear disclaimers.

### Golden Workflow (Strict)

```
User: "看看 NVDA" / "scan for opportunities" / "any signals?"

Step 1: SCAN
  → Call: scan or scan_ticker
  → If no signals: report "no opportunities found" → STOP

Step 2: VERIFY
  → Call: backtest for each signal
  → If WR ≤ 50%: warn user "backtest doesn't support this signal" → STOP
  → Show: win rate, trade count, regime performance

Step 3: SIZE
  → Call: position_size with signal's SL and user's balance
  → Show: suggested qty, max loss, Kelly %

Step 4: CONFIRM (hard gate)
  → Present full picture: signal + backtest + sizing + risk
  → Ask user explicitly: "Do you want to record this position?"
  → If no confirmation → STOP
  → NEVER auto-execute

Step 5: EXECUTE
  → Call: position_add
  → Confirm: "Position recorded. Use position_update to monitor."

Step 6: MONITOR (remind)
  → Tell user to periodically call position_update
  → Explain: breakeven triggers, trailing stops, TP1 ladder exit
```

### Rules

- Never skip Step 2 (backtest verification)
- Never execute Step 5 without explicit user confirmation at Step 4
- Always show stop-loss and take-profit levels
- Always include disclaimer: "Not financial advice. Do your own research."
- When showing signals, include regime context (Bull/Bear/Sideways)
- If user asks to "just buy" without scanning: run the full workflow anyway

### Skill Trigger

Activate when user mentions:
- Scanning, trading signals, market opportunities
- Specific tickers in a trading context
- Position management (add, check, close)
- Portfolio sizing or risk calculation

## File Structure

```
src/mcp_server.py              # MCP server entry point
skills/openclaw-trader.md      # Skill file
```

## Registration

```bash
# Register with Claude Code
claude mcp add openclaw -- python src/mcp_server.py

# The skill is auto-discovered if placed in the project's skills/ directory
# Or manually: copy to ~/.claude/skills/openclaw-trader.md
```

## Error Handling

- yfinance data fetch fails → return `{error: "Market data unavailable for TICKER"}`
- Invalid ticker format → return `{error: "Invalid ticker symbol"}`
- Backtest insufficient data → return `{error: "Not enough historical data", min_required: "1y"}`
- Position already exists → return `{error: "Position already open for TICKER"}`
- All errors are structured JSON, never exceptions to the MCP client

## Testing

- Unit tests for each tool handler (mock core modules)
- Integration test: full scan → backtest → size → add → list → update → remove cycle
- Skill validation: manual test in Claude Code with real conversation
