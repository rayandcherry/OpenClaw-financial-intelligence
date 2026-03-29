# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenClaw is a three-pillar financial intelligence system: **Scanner** (discover trading signals), **Backtester** (verify strategies historically), and **Tracker** (manage live positions with risk rules). It scans US stocks and crypto using three strategies (Trinity, Panic, 2B Reversal), enriches candidates with news and LLM analysis via Gemini, and delivers reports via Telegram.

## Commands

```bash
# Setup
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests (integration tests excluded by default via pytest.ini)
pytest
pytest tests/test_tracker_unit.py::TestPositionManager::test_long_lifecycle  # single test
pytest -m integration  # integration tests only (requires real APIs)

# Scanner
python src/main.py                          # full scan, all assets
python src/scan.py --mode US --ticker NVDA   # targeted scan
python src/scan.py --json                    # agent/JSON output mode

# Backtester
python src/simulate.py --ticker AAPL --period 3y
python src/simulate.py --ticker AAPL --optimize --strategy TRINITY

# Position Tracker
python src/track.py add TICKER PRICE QTY --side LONG
python src/track.py monitor
python src/track.py size TICKER PRICE SL --winrate 0.6
python src/track.py remove TICKER

# Optimization (SP500 parameter grid search)
python src/optimize.py

# --- Telegram Bot (multi-tenant product) ---
# Local dev services
docker compose up -d  # starts Postgres + Redis

# Run bot
python src/bot.py  # requires TELEGRAM_BOT_TOKEN, DATABASE_URL, REDIS_URL

# Run bot tests (48+, pythonpath configured in pytest.ini)
pytest tests/bot/ -v
pytest tests/bot/test_handlers.py::test_scan_handler_returns_report -v  # single test
```

## Architecture

### Entry Points
- `src/main.py` / `src/scan.py` — Scanner pipeline (scan → backtest cache → LLM report → Telegram)
- `src/simulate.py` — Backtesting engine with optimization mode
- `src/track.py` — CLI position tracker (add/monitor/size/remove subcommands)
- `src/optimize.py` — Parameter grid search across SP500
- `src/pulse.py` — Single-ticker deep analysis

### Core Modules (`src/core/`)
- `scanner.py` — Concurrent multi-ticker scanning via ThreadPoolExecutor (10 workers)
- `indicators.py` — Technical indicators: SMA, EMA, RSI, Bollinger Bands, MACD, ATR, Volume Profile, Regime detection
- `data_fetcher.py` — yfinance market data
- `news.py` — DuckDuckGo news enrichment
- `llm_client.py` — Gemini API with ordered model fallback (2.5-flash → 2.0-flash → 1.5-pro → 1.5-flash → pro)
- `cache_manager.py` — Backtest stats cache with 7-day TTL, keyed by `{ticker}_{period}`
- `notifier.py` — Telegram delivery, falls back to stdout

### Tracker Modules (`src/tracker/`)
- `service.py` — Main tracking service
- `position.py` — PositionManager: dynamic ATR-based exits (initial SL → breakeven → trailing stop)
- `risk.py` — CapitalAllocator: Kelly Criterion sizing, VaR limits (2% max risk per trade)

### Strategies (configured in `src/config.py`)
- **TRINITY** — Trend pullback: Price > SMA200, near EMA50, RSI 40-60
- **PANIC** — Mean reversion: Below lower Bollinger Band, RSI < 30, elevated volume
- **2B** — Swing failure pattern: false breakout with RSI divergence or MACD histogram shrinkage

### Telegram Bot (`src/bot/` + `src/bot.py`)
- `bot.py` — Entry point: wires bot + scheduler + health check into single process
- `bot/handlers/` — Telegram command handlers (start, scan, watchlist, schedule, settings, help)
- `bot/services/user_service.py` — User CRUD, watchlists, schedules, scan logging (sync SQLAlchemy)
- `bot/services/scan_service.py` — Wraps existing scanner via `run_in_executor`, smart batching across users
- `bot/services/schedule_service.py` — APScheduler batch trigger, delivery retry (3x), blocked user detection
- `bot/services/report_formatter.py` — Signal dicts → Telegram markdown with 4096-char splitting
- `bot/redis_client.py` — Async Redis: backtest cache, scan locks, per-user rate limits
- `bot/db/models.py` — SQLAlchemy: User, UserWatchlist, UserSchedule, ScanLog (JSON for strategies, not ARRAY)
- `bot/health.py` — aiohttp `/health` on port 8080

### LLM Integration
- System prompt lives in `src/prompts/SOUL.md`
- Gemini API key via `GEMINI_API_KEY` env var
- Legacy scanner delivery via `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`
- Bot delivery via `TELEGRAM_BOT_TOKEN` (python-telegram-bot)

## Key Patterns

- **Config injection**: `risk_params` and `strategy_params` are passed into PositionManager/Backtester for testability
- **Persistent state**: Positions stored in `data/positions.json`, saved on each monitor cycle
- **Test markers**: Integration tests use `@pytest.mark.integration` and are excluded by default in `pytest.ini`
- **Gemini SDK**: Uses `google-genai` (not the deprecated `google-generativeai`)
- **Async/sync bridge**: Bot is async (python-telegram-bot), scanner is sync (ThreadPoolExecutor). Bridge via `loop.run_in_executor`
- **Service locator**: `bot/handlers/__init__.py` holds `set_services()`/`get_*_service()` for DI into handlers
- **Smart batching**: Scheduled scans dedupe tickers across users, fetch once, fan out per-user reports
- **`from __future__ import annotations`**: Required in bot modules for Python 3.9 compat (`X | None` syntax)

## Project Decisions

- Default test runs must exclude integration/live tests
- Claude Code is the primary implementation engine; Codex handles review/approval
- Feature repos live in dedicated sibling workspaces under `/Users/bytedance/features/`
