# OpenClaw Telegram Bot Product Design

## Overview

Productize OpenClaw as a multi-tenant Telegram bot service for swing traders. Users interact entirely through Telegram — configure watchlists, set scan schedules, receive personalized intelligence reports. The existing scanner, backtester, indicators, and LLM client are reused as-is, wrapped in a service layer that adds multi-tenancy, scheduling, and user management.

**Target user:** Swing traders / part-time investors who check markets a few times a week and want a disciplined workflow.

**V1 success metric:** Users actively receiving and engaging with scan reports.

**Distribution:** Hosted service, free launch (monetize later after validation).

**Regulatory posture:** Bold signals with strong disclaimers in ToS. Not positioned as financial advice.

## Architecture

Single-process application with three layers:

### Telegram Bot Layer
- Built with `python-telegram-bot` (async)
- Command router, conversation handlers (onboarding), rate limiter
- Inline keyboard buttons for onboarding choices, text commands for power users

### Application Layer
- **User Service** — registration, preferences, watchlist management, activation state
- **Scan Service** — wraps existing scanner, backtester, news, and LLM client. Adds smart batching and per-user report fan-out
- **Schedule Service** — APScheduler running in-process. One global cron checks every minute for users whose scan time matches, batches them into a single scan run

### Data Layer
- **Postgres** — users, watchlists, schedules, scan logs
- **Redis** — backtest cache (7-day TTL, replaces file-based cache), scan locks, per-user and global rate limits

## Bot Commands

### Onboarding
- `/start` — welcome message, create account, 3-tap setup (preset watchlist → schedule → language)
- `/help` — command reference

### Watchlist Management
- `/watchlist` — show current watchlist
- `/watch AAPL NVDA BTC` — add tickers (validated against yfinance on add)
- `/unwatch AAPL` — remove ticker
- `/presets` — browse preset lists (SP500 Top 20, FAANG, Crypto Major, etc.)
- Cap: 50 tickers per user

### Scanning
- `/scan` — run scan now on user's watchlist
- `/scan NVDA` — scan single ticker on demand

### Schedule
- `/schedule` — show current scan schedule
- `/schedule 8:00 20:00` — set daily scan times (UTC)
- `/pause` — pause scheduled scans
- `/resume` — resume scheduled scans

### Settings
- `/settings` — show current preferences
- `/lang EN|ZH` — set report language
- `/mode US|CRYPTO|ALL` — set default scan mode
- `/strategies` — toggle which strategies to scan (Trinity/Panic/2B)

## Onboarding Flow

User sends `/start`. Bot responds with welcome message and 3-step inline keyboard setup:

1. **Pick a preset watchlist** — [SP500 Top 20] [FAANG+] [Crypto Major] [Custom]
2. **Set scan schedule** — [Morning 8:00] [Evening 20:00] [Both] [Manual only]
3. **Choose language** — [English] [中文]

Or skip setup entirely with `/scan AAPL` to try immediately.

## Report Format

```
📊 OpenClaw Scan Report — Mar 19, 2026 08:00 UTC

3 signals found from 25 tickers scanned

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 NVDA — Trinity (Trend Pullback)
Confidence: 85/100
Price: $142.30 | SL: $134.10 (ATR×3) | TP: $158.70
Backtest WR: 62% (3yr, 47 trades)
News: Earnings beat estimates, datacenter revenue +40%
━━━━━━━━━━━━━━━━━━━━━━━━━━━

/scan to refresh | /watchlist to edit tickers

⚠️ Not financial advice. Do your own research.
```

If no signals found: "All quiet on your watchlist today. 0 signals from 25 tickers scanned."

Reports exceeding Telegram's 4096 char limit are split into multiple messages: summary header first, then individual signal cards.

## Data Model

### Postgres Tables

**users**
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| telegram_id | BIGINT UNIQUE | Sole identity — no email/password |
| username | TEXT | Telegram username, for display |
| lang | TEXT | Default: EN |
| scan_mode | TEXT | Default: ALL (US/CRYPTO/ALL) |
| strategies | TEXT[] | Default: {TRINITY, PANIC, 2B} |
| is_active | BOOL | False if user blocks bot |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**user_watchlists**
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| user_id | FK → users | |
| ticker | TEXT | Validated on add |
| added_at | TIMESTAMP | |

**user_schedules**
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| user_id | FK → users | |
| scan_time | TIME | UTC |
| is_paused | BOOL | |

**scan_logs**
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| user_id | FK → users | |
| triggered_by | TEXT | schedule / manual / ondemand |
| tickers_count | INT | |
| signals_found | INT | |
| status | TEXT | pending / running / done / failed |
| started_at | TIMESTAMP | |
| finished_at | TIMESTAMP | |
| report_text | TEXT | Full report for "show me last report" |

### Redis Keys

| Key | Value | TTL | Purpose |
|-----|-------|-----|---------|
| `backtest:{ticker}_{period}` | JSON stats | 7 days | Backtest cache (replaces file cache) |
| `scan_lock:{user_id}` | "running" | 5 min | Prevent duplicate concurrent scans |
| `rate:{user_id}:scans` | counter | 1 hour | 10 on-demand scans/hour per user |
| `rate:global:yfinance` | counter | 1 min | Respect upstream rate limits |

## Scan Pipeline

### Smart Batching

The key optimization for multi-tenant scanning. Without batching, 200 users × 25 tickers = 5000 yfinance calls per scan window. With batching:

1. **Collect** — gather watchlists for all users in the same scan time slot
2. **Dedupe** — union all tickers into a unique set (200 users → ~100-200 unique tickers)
3. **Batch fetch** — fetch each ticker once via existing ThreadPoolExecutor scanner
4. **Scan** — run indicators and strategies on shared data, cache in memory for this window (5 min TTL)
5. **Fan out** — for each user, filter to their watchlist tickers, run backtest (Redis-cached), generate LLM report, deliver via Telegram

Result: ~100-200 API calls instead of 5000.

### Schedule Execution

Not per-user cron jobs. Instead:

1. One global APScheduler cron fires every minute
2. Queries: "which active, non-paused users have a schedule matching this minute?"
3. Batches those users into a single scan run
4. Market hours awareness: US stock scans only fire on NYSE trading days, crypto scans fire daily

### On-Demand Scans

`/scan` and `/scan TICKER` bypass the scheduler, run immediately for the single user. Subject to rate limits (10/hour) and scan lock (no concurrent scans per user).

## Deployment

### Infrastructure

- **Platform:** Railway (recommended for simplicity and managed add-ons)
- **Container:** Single Docker image, single process (bot + scheduler + services)
- **Postgres:** Railway managed add-on (free tier → $7/mo)
- **Redis:** Railway managed add-on (free tier → $3/mo)
- **Python:** 3.12 (not 3.14 — better library compatibility for production)

### Cost Estimate

| Item | Monthly Cost |
|------|-------------|
| Railway container (1 vCPU, 512MB) | $5 - $10 |
| Managed Postgres | $0 - $7 |
| Managed Redis | $0 - $3 |
| Gemini API (Flash) | $0 - $20 |
| yfinance, DuckDuckGo, Telegram | Free |
| **Total** | **$5 - $40** |

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
CMD ["python", "src/bot.py"]
```

Environment variables (set in Railway dashboard): `DATABASE_URL`, `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`.

### Operations

- **Health check** — aiohttp server on port 8080, `/health` endpoint
- **Logging** — structured JSON to stdout (Railway collects automatically)
- **Graceful shutdown** — SIGTERM handler finishes in-flight scans, closes connections
- **DB migrations** — Alembic, run on deploy before app starts
- **Monitoring** — scan_logs table: query failed scans, avg scan time, signals/day
- **Backups** — managed Postgres daily automatic backups

## Error Handling

### External API Failures

**yfinance down / rate limited:**
- Retry 2x with exponential backoff (2s, 8s)
- If still failing, skip ticker and note in report: "NVDA: data unavailable"
- If >50% of tickers fail, send user: "Market data issues, will retry next window"
- Log to scan_logs with status=failed

**Gemini API down / quota exceeded:**
- Existing model fallback chain handles most cases (2.5-flash → 2.0-flash → 1.5-pro → 1.5-flash → pro)
- If all models fail, deliver raw signal data without LLM analysis
- User still gets: ticker, strategy, confidence, SL/TP, backtest WR
- Footer: "AI analysis temporarily unavailable"

**DuckDuckGo blocked / slow:**
- 5s timeout per ticker, non-blocking
- Report generates without news context if news fails
- News is enrichment, not a gate

**Telegram API down:**
- Retry delivery 3x over 60 seconds
- If still failing, mark scan_log as done, delivery=failed
- Next successful delivery: "You missed a report — /scan to refresh"

### User Edge Cases

| Case | Response |
|------|----------|
| Empty watchlist + /scan | "No tickers in your watchlist. Try /presets or /watch AAPL" |
| Invalid ticker on /watch | Validate against yfinance: "Couldn't find XYZFAKE. Check the symbol and try again." |
| Spam /scan | scan_lock prevents concurrent scans. Rate limit: 10/hour. "Your last scan is still running, hang tight." |
| User blocks bot | Telegram returns 403 → set is_active=false, stop scheduling. Reactivate on /start. |
| Watchlist > 50 tickers | "Watchlist full (50 max). /unwatch some tickers first." |
| Report > 4096 chars | Split into multiple messages: summary header + individual signal cards |
| No signals found | "All quiet on your watchlist today. 0 signals from 25 tickers scanned." |

### Security

- No user secrets stored — Telegram auth only
- Bot token stored in env vars, never in code
- SQLAlchemy ORM with parameterized queries (no string formatting)
- Ticker symbols validated on add
- Per-user and global rate limiting

## Scope Boundaries

### In V1
- Multi-tenant Telegram bot with user registration
- Watchlist management with presets
- Scheduled and on-demand scans with smart batching
- Personalized LLM-powered reports delivered via Telegram
- Scan logging for engagement metrics
- Graceful error handling and degradation

### Not in V1
- Position tracker (add/monitor/size/remove) — comes in V2
- Web dashboard or web-hosted reports
- Payment / subscription management
- User-configurable strategy parameters
- Push notifications beyond Telegram
- Admin dashboard

## New Dependencies

| Package | Purpose |
|---------|---------|
| python-telegram-bot | Async Telegram bot framework |
| SQLAlchemy + asyncpg | Async Postgres ORM |
| alembic | Database migrations |
| redis[hiredis] | Async Redis client |
| APScheduler | In-process job scheduling |
| aiohttp | Health check endpoint |
