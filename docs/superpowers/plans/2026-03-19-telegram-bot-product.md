# OpenClaw Telegram Bot Product — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Productize OpenClaw as a multi-tenant Telegram bot service where swing traders configure watchlists, set scan schedules, and receive personalized intelligence reports.

**Architecture:** Single-process async Python app. Telegram bot layer (python-telegram-bot) handles user interaction. Application layer wraps existing sync scanner/backtester via `run_in_executor`. Postgres stores users/watchlists/schedules/logs. Redis replaces file-based backtest cache and adds rate limiting. APScheduler fires batched scans per time slot.

**Tech Stack:** python-telegram-bot (async), SQLAlchemy + asyncpg, Alembic, redis[hiredis], APScheduler, aiohttp (health check), Docker

**Spec:** `docs/superpowers/specs/2026-03-19-telegram-bot-product-design.md`

---

## File Structure

### New Files

```
src/
  bot.py                      # Entry point — wires bot + scheduler + health check
  bot/
    __init__.py
    handlers/
      __init__.py
      start.py                # /start onboarding conversation handler
      watchlist.py            # /watchlist, /watch, /unwatch, /presets
      scan.py                 # /scan command (on-demand)
      schedule.py             # /schedule, /pause, /resume
      settings.py             # /settings, /lang, /mode, /strategies
      help.py                 # /help
    services/
      __init__.py
      user_service.py         # User CRUD, activation, preferences
      scan_service.py         # Wraps existing scanner with batching + fan-out
      schedule_service.py     # APScheduler setup, batch trigger logic
      report_formatter.py     # Signal dicts → Telegram markdown
    db/
      __init__.py
      models.py               # SQLAlchemy ORM models (users, watchlists, schedules, scan_logs)
      session.py              # Async engine + session factory
      migrations/              # Alembic migrations directory
    redis_client.py           # Async Redis: cache, rate limiting, scan locks
    health.py                 # aiohttp /health endpoint
Dockerfile
alembic.ini
docker-compose.yml            # Local dev: postgres + redis + app
```

### Modified Files

```
src/config.py                 # Add BOT_CONFIG section (rate limits, schedule defaults, watchlist cap)
src/core/cache_manager.py     # Keep as-is (Redis client is a new parallel implementation, not a replacement of this file)
requirements.txt              # Add new dependencies
```

### Test Files

```
tests/
  bot/
    __init__.py
    test_models.py            # ORM model tests
    test_user_service.py      # User CRUD tests
    test_scan_service.py      # Batching, fan-out, executor bridge tests
    test_report_formatter.py  # Signal dict → Telegram message formatting
    test_schedule_service.py  # Schedule trigger logic tests
    test_redis_client.py      # Cache, rate limit, lock tests
    test_handlers.py          # Bot command handler tests (mocked bot)
    test_integration.py       # Full flow integration test (marked integration)
```

---

## Task 1: Project Setup & Dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-prod.txt`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `alembic.ini`
- Create: `src/bot/__init__.py`
- Create: `src/bot/handlers/__init__.py`
- Create: `src/bot/services/__init__.py`
- Create: `src/bot/db/__init__.py`
- Modify: `src/config.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add production dependencies**

In `requirements.txt`, append:
```
python-telegram-bot>=21.0
SQLAlchemy[asyncio]>=2.0
asyncpg>=0.29
psycopg2-binary>=2.9
alembic>=1.13
redis[hiredis]>=5.0
APScheduler>=3.10
aiohttp>=3.9
```

- [ ] **Step 2: Create requirements-prod.txt**

```
-r requirements.txt
gunicorn>=21.0
```

- [ ] **Step 3: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY src/ src/
COPY alembic.ini .
COPY src/bot/db/migrations/ src/bot/db/migrations/

EXPOSE 8080

CMD ["python", "src/bot.py"]
```

- [ ] **Step 4: Create docker-compose.yml for local dev**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: openclaw
      POSTGRES_USER: openclaw
      POSTGRES_PASSWORD: localdev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

- [ ] **Step 5: Create alembic.ini**

```ini
[alembic]
script_location = src/bot/db/migrations
sqlalchemy.url = postgresql+asyncpg://openclaw:localdev@localhost:5432/openclaw

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 6: Add bot config to src/config.py**

Append to the end of `src/config.py`:
```python
# --- Bot Configuration ---
BOT_CONFIG = {
    "watchlist_max": 50,
    "rate_limit_scans_per_hour": 10,
    "scan_lock_ttl_seconds": 300,
    "backtest_cache_ttl_days": 7,
    "default_schedule_times": ["08:00", "20:00"],
    "default_lang": "EN",
    "default_scan_mode": "ALL",
    "default_strategies": ["TRINITY", "PANIC", "2B"],
}

PRESET_WATCHLISTS = {
    "SP500 Top 20": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "UNH", "XOM", "JNJ",
                      "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "LLY", "PEP"],
    "FAANG+": ["META", "AAPL", "AMZN", "NVDA", "GOOGL", "MSFT", "TSLA", "NFLX"],
    "Crypto Major": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD",
                      "AVAX-USD", "DOT-USD", "MATIC-USD", "LINK-USD"],
}
```

- [ ] **Step 7: Add to .gitignore**

Append:
```
.superpowers/
```

- [ ] **Step 8: Create package init files**

Create empty `__init__.py` files:
- `src/bot/__init__.py`
- `src/bot/handlers/__init__.py`
- `src/bot/services/__init__.py`
- `src/bot/db/__init__.py`
- `tests/bot/__init__.py`

- [ ] **Step 9: Install dependencies and verify**

```bash
pip install -r requirements.txt
python -c "import telegram; import sqlalchemy; import psycopg2; import redis; import apscheduler; import aiohttp; print('All imports OK')"
```

- [ ] **Step 10: Commit**

```bash
git add requirements.txt requirements-prod.txt Dockerfile docker-compose.yml alembic.ini src/bot/ src/config.py .gitignore tests/bot/__init__.py
git commit -m "feat(bot): project setup with dependencies, Docker, and config"
```

---

## Task 2: Database Models & Migrations

**Files:**
- Create: `src/bot/db/models.py`
- Create: `src/bot/db/session.py`
- Create: `src/bot/db/migrations/env.py`
- Create: `src/bot/db/migrations/script.py.mako`
- Create: `src/bot/db/migrations/versions/` (auto-generated)
- Create: `tests/bot/test_models.py`

- [ ] **Step 1: Write model tests**

`tests/bot/test_models.py`:
```python
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from src.bot.db.models import Base, User, UserWatchlist, UserSchedule, ScanLog


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_create_user(db):
    user = User(telegram_id=123456789, username="trader1")
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    assert user.telegram_id == 123456789
    assert user.lang == "EN"
    assert user.scan_mode == "ALL"
    assert user.strategies == ["TRINITY", "PANIC", "2B"]
    assert user.is_active is True


def test_telegram_id_unique(db):
    db.add(User(telegram_id=111, username="a"))
    db.commit()
    db.add(User(telegram_id=111, username="b"))
    with pytest.raises(Exception):
        db.commit()


def test_user_watchlist(db):
    user = User(telegram_id=222, username="trader2")
    db.add(user)
    db.commit()
    wl = UserWatchlist(user_id=user.id, ticker="AAPL")
    db.add(wl)
    db.commit()
    assert wl.ticker == "AAPL"
    assert wl.user_id == user.id


def test_user_schedule(db):
    user = User(telegram_id=333, username="trader3")
    db.add(user)
    db.commit()
    from datetime import time
    sched = UserSchedule(user_id=user.id, scan_time=time(8, 0))
    db.add(sched)
    db.commit()
    assert sched.is_paused is False


def test_scan_log(db):
    user = User(telegram_id=444, username="trader4")
    db.add(user)
    db.commit()
    log = ScanLog(
        user_id=user.id,
        triggered_by="manual",
        tickers_count=25,
        signals_found=3,
        status="done",
        report_text="Test report",
    )
    db.add(log)
    db.commit()
    assert log.signals_found == 3
    assert log.triggered_by == "manual"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.bot.db.models'`

- [ ] **Step 3: Implement models**

`src/bot/db/models.py`:
```python
from datetime import datetime, time
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Time,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(Text, nullable=True)
    lang = Column(Text, nullable=False, default="EN")
    scan_mode = Column(Text, nullable=False, default="ALL")
    strategies = Column(ARRAY(Text), nullable=False, default=["TRINITY", "PANIC", "2B"])
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    watchlists = relationship("UserWatchlist", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("UserSchedule", back_populates="user", cascade="all, delete-orphan")
    scan_logs = relationship("ScanLog", back_populates="user", cascade="all, delete-orphan")


class UserWatchlist(Base):
    __tablename__ = "user_watchlists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(Text, nullable=False)
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="watchlists")


class UserSchedule(Base):
    __tablename__ = "user_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_time = Column(Time, nullable=False)
    is_paused = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="schedules")


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    triggered_by = Column(Text, nullable=False)
    tickers_count = Column(Integer, nullable=False, default=0)
    signals_found = Column(Integer, nullable=False, default=0)
    status = Column(Text, nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    report_text = Column(Text, nullable=True)

    user = relationship("User", back_populates="scan_logs")
```

- [ ] **Step 4: Implement async session factory**

`src/bot/db/session.py`:
```python
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://openclaw:localdev@localhost:5432/openclaw")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    """For testing or first-run. Production uses Alembic."""
    from src.bot.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/bot/test_models.py -v
```
Expected: PASS (tests use SQLite in-memory, not async engine)

Note: The ARRAY type won't work in SQLite. The test for `strategies` field will need a workaround. Update the `User` model to handle this:

In `test_models.py`, add at the top after imports:
```python
from unittest.mock import patch

# For SQLite testing, strategies defaults to a JSON string representation
# Production uses PostgreSQL ARRAY type
```

And update the `test_create_user` assertion to account for SQLite not supporting ARRAY:
```python
def test_create_user(db):
    user = User(telegram_id=123456789, username="trader1", strategies=["TRINITY", "PANIC", "2B"])
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    assert user.telegram_id == 123456789
    assert user.lang == "EN"
    assert user.scan_mode == "ALL"
    assert user.is_active is True
```

- [ ] **Step 6: Set up Alembic migrations**

Create `src/bot/db/migrations/env.py`:
```python
import asyncio
import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from src.bot.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    engine = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `src/bot/db/migrations/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `src/bot/db/migrations/versions/` as an empty directory (with `__init__.py` placeholder).

- [ ] **Step 7: Generate initial migration** (requires running Postgres from docker-compose)

```bash
docker compose up -d postgres
alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 8: Commit**

```bash
git add src/bot/db/ tests/bot/test_models.py alembic.ini
git commit -m "feat(bot): database models and Alembic migrations"
```

---

## Task 3: Redis Client — Cache, Rate Limits, Locks

**Files:**
- Create: `src/bot/redis_client.py`
- Create: `tests/bot/test_redis_client.py`

- [ ] **Step 1: Write Redis client tests**

`tests/bot/test_redis_client.py`:
```python
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.setex = AsyncMock(return_value=True)
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    r.ttl = AsyncMock(return_value=-2)  # key doesn't exist
    r.delete = AsyncMock(return_value=1)
    return r


@pytest.mark.asyncio
async def test_get_backtest_cache_miss(mock_redis):
    from src.bot.redis_client import RedisClient
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    result = await client.get_backtest("AAPL", "3y")
    assert result is None
    mock_redis.get.assert_called_once_with("backtest:AAPL_3y")


@pytest.mark.asyncio
async def test_get_backtest_cache_hit(mock_redis):
    from src.bot.redis_client import RedisClient
    stats = {"wr": 62.0, "count": 47}
    mock_redis.get = AsyncMock(return_value=json.dumps(stats).encode())
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    result = await client.get_backtest("AAPL", "3y")
    assert result == stats


@pytest.mark.asyncio
async def test_set_backtest_cache(mock_redis):
    from src.bot.redis_client import RedisClient
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    client.backtest_ttl = 7 * 86400
    stats = {"wr": 62.0}
    await client.set_backtest("AAPL", "3y", stats)
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_acquire_scan_lock(mock_redis):
    from src.bot.redis_client import RedisClient
    mock_redis.set = AsyncMock(return_value=True)
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    client.scan_lock_ttl = 300
    result = await client.acquire_scan_lock(123)
    assert result is True
    mock_redis.set.assert_called_once_with("scan_lock:123", "running", nx=True, ex=300)


@pytest.mark.asyncio
async def test_acquire_scan_lock_already_held(mock_redis):
    from src.bot.redis_client import RedisClient
    mock_redis.set = AsyncMock(return_value=False)
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    client.scan_lock_ttl = 300
    result = await client.acquire_scan_lock(123)
    assert result is False


@pytest.mark.asyncio
async def test_check_rate_limit_under(mock_redis):
    from src.bot.redis_client import RedisClient
    mock_redis.incr = AsyncMock(return_value=3)
    mock_redis.ttl = AsyncMock(return_value=1800)
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    allowed = await client.check_rate_limit(123, max_per_hour=10)
    assert allowed is True


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded(mock_redis):
    from src.bot.redis_client import RedisClient
    mock_redis.incr = AsyncMock(return_value=11)
    mock_redis.ttl = AsyncMock(return_value=1800)
    client = RedisClient.__new__(RedisClient)
    client.redis = mock_redis
    allowed = await client.check_rate_limit(123, max_per_hour=10)
    assert allowed is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_redis_client.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Redis client**

`src/bot/redis_client.py`:
```python
import json
import os
import redis.asyncio as redis
from src.config import BOT_CONFIG


class RedisClient:
    def __init__(self):
        self.redis = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=False,
        )
        self.backtest_ttl = BOT_CONFIG["backtest_cache_ttl_days"] * 86400
        self.scan_lock_ttl = BOT_CONFIG["scan_lock_ttl_seconds"]

    # --- Backtest Cache ---

    async def get_backtest(self, ticker: str, period: str) -> dict | None:
        data = await self.redis.get(f"backtest:{ticker}_{period}")
        if data is None:
            return None
        return json.loads(data)

    async def set_backtest(self, ticker: str, period: str, stats: dict) -> None:
        await self.redis.setex(
            f"backtest:{ticker}_{period}",
            self.backtest_ttl,
            json.dumps(stats),
        )

    # --- Scan Locks ---

    async def acquire_scan_lock(self, user_id: int) -> bool:
        return await self.redis.set(
            f"scan_lock:{user_id}", "running", nx=True, ex=self.scan_lock_ttl
        )

    async def release_scan_lock(self, user_id: int) -> None:
        await self.redis.delete(f"scan_lock:{user_id}")

    # --- Rate Limiting ---

    async def check_rate_limit(self, user_id: int, max_per_hour: int = None) -> bool:
        if max_per_hour is None:
            max_per_hour = BOT_CONFIG["rate_limit_scans_per_hour"]
        key = f"rate:{user_id}:scans"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 3600)
        return count <= max_per_hour

    async def close(self):
        await self.redis.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bot/test_redis_client.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/redis_client.py tests/bot/test_redis_client.py
git commit -m "feat(bot): async Redis client for cache, locks, and rate limiting"
```

---

## Task 4: User Service

**Files:**
- Create: `src/bot/services/user_service.py`
- Create: `tests/bot/test_user_service.py`

- [ ] **Step 1: Write user service tests**

`tests/bot/test_user_service.py`:
```python
import pytest
from datetime import time
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.bot.db.models import Base, User, UserWatchlist, UserSchedule
from src.bot.services.user_service import UserService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def svc(db):
    return UserService(db)


def test_register_new_user(svc, db):
    user = svc.register(telegram_id=111, username="alice")
    assert user.id is not None
    assert user.telegram_id == 111
    assert user.is_active is True


def test_register_existing_reactivates(svc, db):
    user1 = svc.register(telegram_id=222, username="bob")
    user1.is_active = False
    db.commit()
    user2 = svc.register(telegram_id=222, username="bob_updated")
    assert user2.id == user1.id
    assert user2.is_active is True
    assert user2.username == "bob_updated"


def test_get_by_telegram_id(svc, db):
    svc.register(telegram_id=333, username="carol")
    user = svc.get_by_telegram_id(333)
    assert user is not None
    assert user.username == "carol"


def test_get_by_telegram_id_not_found(svc, db):
    assert svc.get_by_telegram_id(999) is None


def test_set_watchlist(svc, db):
    user = svc.register(telegram_id=444, username="dave")
    svc.add_tickers(user.id, ["AAPL", "NVDA", "BTC-USD"])
    tickers = svc.get_watchlist(user.id)
    assert set(tickers) == {"AAPL", "NVDA", "BTC-USD"}


def test_add_tickers_deduplicates(svc, db):
    user = svc.register(telegram_id=555, username="eve")
    svc.add_tickers(user.id, ["AAPL", "NVDA"])
    svc.add_tickers(user.id, ["AAPL", "MSFT"])
    tickers = svc.get_watchlist(user.id)
    assert sorted(tickers) == ["AAPL", "MSFT", "NVDA"]


def test_remove_ticker(svc, db):
    user = svc.register(telegram_id=666, username="frank")
    svc.add_tickers(user.id, ["AAPL", "NVDA"])
    svc.remove_ticker(user.id, "AAPL")
    assert svc.get_watchlist(user.id) == ["NVDA"]


def test_watchlist_cap(svc, db):
    user = svc.register(telegram_id=777, username="grace")
    tickers = [f"T{i}" for i in range(50)]
    svc.add_tickers(user.id, tickers)
    over = svc.add_tickers(user.id, ["EXTRA"])
    assert over == ["EXTRA"]  # returns rejected tickers


def test_set_schedule(svc, db):
    user = svc.register(telegram_id=888, username="heidi")
    svc.set_schedules(user.id, [time(8, 0), time(20, 0)])
    scheds = svc.get_schedules(user.id)
    assert len(scheds) == 2


def test_update_preferences(svc, db):
    user = svc.register(telegram_id=999, username="ivan")
    svc.update_preferences(user.id, lang="ZH", scan_mode="CRYPTO")
    user = svc.get_by_telegram_id(999)
    assert user.lang == "ZH"
    assert user.scan_mode == "CRYPTO"


def test_deactivate(svc, db):
    user = svc.register(telegram_id=1010, username="judy")
    svc.deactivate(user.id)
    user = svc.get_by_telegram_id(1010)
    assert user.is_active is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_user_service.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement UserService**

`src/bot/services/user_service.py`:
```python
from datetime import time as dt_time
from sqlalchemy.orm import Session
from src.bot.db.models import User, UserWatchlist, UserSchedule
from src.config import BOT_CONFIG


class UserService:
    def __init__(self, session: Session):
        self.session = session

    def register(self, telegram_id: int, username: str = None) -> User:
        user = self.session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_active = True
            if username:
                user.username = username
            self.session.commit()
            return user
        user = User(
            telegram_id=telegram_id,
            username=username,
            strategies=BOT_CONFIG["default_strategies"],
        )
        self.session.add(user)
        self.session.commit()
        return user

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.session.query(User).filter_by(telegram_id=telegram_id).first()

    def add_tickers(self, user_id: int, tickers: list[str]) -> list[str]:
        existing = {wl.ticker for wl in self.session.query(UserWatchlist).filter_by(user_id=user_id).all()}
        cap = BOT_CONFIG["watchlist_max"]
        rejected = []
        for t in tickers:
            t_upper = t.upper()
            if t_upper in existing:
                continue
            if len(existing) >= cap:
                rejected.append(t_upper)
                continue
            self.session.add(UserWatchlist(user_id=user_id, ticker=t_upper))
            existing.add(t_upper)
        self.session.commit()
        return rejected

    def remove_ticker(self, user_id: int, ticker: str) -> None:
        self.session.query(UserWatchlist).filter_by(user_id=user_id, ticker=ticker.upper()).delete()
        self.session.commit()

    def get_watchlist(self, user_id: int) -> list[str]:
        rows = self.session.query(UserWatchlist).filter_by(user_id=user_id).all()
        return [r.ticker for r in rows]

    def set_schedules(self, user_id: int, times: list[dt_time]) -> None:
        self.session.query(UserSchedule).filter_by(user_id=user_id).delete()
        for t in times:
            self.session.add(UserSchedule(user_id=user_id, scan_time=t))
        self.session.commit()

    def get_schedules(self, user_id: int) -> list[UserSchedule]:
        return self.session.query(UserSchedule).filter_by(user_id=user_id).all()

    def update_preferences(self, user_id: int, **kwargs) -> None:
        user = self.session.query(User).get(user_id)
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        self.session.commit()

    def deactivate(self, user_id: int) -> None:
        user = self.session.query(User).get(user_id)
        user.is_active = False
        self.session.commit()

    def get_users_for_time(self, scan_time: dt_time) -> list[User]:
        schedule_rows = (
            self.session.query(UserSchedule)
            .filter_by(scan_time=scan_time, is_paused=False)
            .all()
        )
        user_ids = [s.user_id for s in schedule_rows]
        if not user_ids:
            return []
        return (
            self.session.query(User)
            .filter(User.id.in_(user_ids), User.is_active == True)
            .all()
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bot/test_user_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/services/user_service.py tests/bot/test_user_service.py
git commit -m "feat(bot): user service with registration, watchlists, and schedules"
```

---

## Task 5: Report Formatter

**Files:**
- Create: `src/bot/services/report_formatter.py`
- Create: `tests/bot/test_report_formatter.py`

- [ ] **Step 1: Write formatter tests**

`tests/bot/test_report_formatter.py`:
```python
import pytest
from src.bot.services.report_formatter import ReportFormatter


@pytest.fixture
def sample_signal():
    return {
        "ticker": "NVDA",
        "strategy": "trinity",
        "price": 142.30,
        "confidence": 85,
        "metrics": {"rsi": 48.5, "regime": "Bull", "dist_to_ema": "1.2%"},
        "stats": {"total": {"wr": 62.0, "count": 47}},
        "plan": {"stop_loss": 134.10, "take_profit": 158.70, "risk_reward": "1:2 (ATR Based)"},
        "side": "LONG",
        "date": "2026-03-19",
    }


@pytest.fixture
def formatter():
    return ReportFormatter()


def test_format_signal_card(formatter, sample_signal):
    card = formatter.format_signal_card(sample_signal)
    assert "NVDA" in card
    assert "Trinity" in card or "trinity" in card.lower()
    assert "85" in card
    assert "134.10" in card or "134.1" in card
    assert "62" in card  # win rate


def test_format_report_with_signals(formatter, sample_signal):
    report = formatter.format_report([sample_signal], total_scanned=25)
    assert "1 signal" in report.lower() or "1 Signal" in report
    assert "25" in report
    assert "NVDA" in report


def test_format_report_no_signals(formatter):
    report = formatter.format_report([], total_scanned=25)
    assert "0 signal" in report.lower() or "quiet" in report.lower() or "All quiet" in report


def test_format_report_splits_long_messages(formatter, sample_signal):
    # Create enough signals to exceed 4096 chars
    signals = [dict(sample_signal, ticker=f"T{i:03d}") for i in range(20)]
    messages = formatter.format_report_messages(signals, total_scanned=100)
    assert isinstance(messages, list)
    assert all(len(m) <= 4096 for m in messages)
    assert len(messages) >= 1


def test_strategy_emoji(formatter):
    assert formatter._strategy_emoji("trinity") == "🟢"
    assert formatter._strategy_emoji("panic") == "🔴"
    assert formatter._strategy_emoji("2B_Reversal") == "🟡"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_report_formatter.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement ReportFormatter**

`src/bot/services/report_formatter.py`:
```python
from datetime import datetime, timezone


STRATEGY_EMOJIS = {
    "trinity": "🟢",
    "panic": "🔴",
    "2b_reversal": "🟡",
}

STRATEGY_LABELS = {
    "trinity": "Trinity (Trend Pullback)",
    "panic": "Panic (Mean Reversion)",
    "2b_reversal": "2B Reversal",
}

TELEGRAM_MAX_LENGTH = 4096


class ReportFormatter:

    def _strategy_emoji(self, strategy: str) -> str:
        return STRATEGY_EMOJIS.get(strategy.lower(), "⚪")

    def _strategy_label(self, strategy: str) -> str:
        return STRATEGY_LABELS.get(strategy.lower(), strategy)

    def format_signal_card(self, signal: dict) -> str:
        emoji = self._strategy_emoji(signal["strategy"])
        label = self._strategy_label(signal["strategy"])
        stats = signal.get("stats", {}).get("total", {})
        wr = stats.get("wr", "N/A")
        count = stats.get("count", "N/A")
        plan = signal.get("plan", {})

        lines = [
            f"{emoji} *{signal['ticker']}* — {label}",
            f"Confidence: {signal['confidence']}/100",
            f"Price: ${signal['price']:.2f} | SL: ${plan.get('stop_loss', 0):.2f} | TP: ${plan.get('take_profit', 0):.2f}",
            f"Backtest WR: {wr}% ({count} trades)",
        ]

        news = signal.get("news")
        if news:
            lines.append(f"News: {news}")

        return "\n".join(lines)

    def format_report(self, signals: list[dict], total_scanned: int) -> str:
        messages = self.format_report_messages(signals, total_scanned)
        return messages[0] if messages else ""

    def format_report_messages(self, signals: list[dict], total_scanned: int) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
        count = len(signals)

        if count == 0:
            header = (
                f"📊 *OpenClaw Scan Report* — {now}\n\n"
                f"All quiet on your watchlist today. "
                f"0 signals from {total_scanned} tickers scanned.\n\n"
                f"/scan to refresh | /watchlist to edit tickers\n\n"
                f"⚠️ Not financial advice. Do your own research."
            )
            return [header]

        header = (
            f"📊 *OpenClaw Scan Report* — {now}\n\n"
            f"*{count} signal{'s' if count != 1 else ''}* found "
            f"from {total_scanned} tickers scanned\n"
        )
        footer = (
            "\n/scan to refresh | /watchlist to edit tickers\n\n"
            "⚠️ Not financial advice. Do your own research."
        )

        cards = [self.format_signal_card(s) for s in signals]
        separator = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        # Try to fit everything in one message
        full = header + separator + separator.join(cards) + separator + footer
        if len(full) <= TELEGRAM_MAX_LENGTH:
            return [full]

        # Split: header first, then one card per message if needed
        messages = [header]
        current = ""
        for card in cards:
            entry = separator + card
            if len(current) + len(entry) + len(footer) > TELEGRAM_MAX_LENGTH:
                if current:
                    messages.append(current)
                current = entry
            else:
                current += entry

        if current:
            messages.append(current + footer)
        else:
            messages[-1] += footer

        return messages
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bot/test_report_formatter.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/services/report_formatter.py tests/bot/test_report_formatter.py
git commit -m "feat(bot): report formatter for Telegram signal cards"
```

---

## Task 6: Scan Service — Executor Bridge & Smart Batching

**Files:**
- Create: `src/bot/services/scan_service.py`
- Create: `tests/bot/test_scan_service.py`

- [ ] **Step 1: Write scan service tests**

`tests/bot/test_scan_service.py`:
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot.services.scan_service import ScanService


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.acquire_scan_lock = AsyncMock(return_value=True)
    r.release_scan_lock = AsyncMock()
    r.check_rate_limit = AsyncMock(return_value=True)
    r.get_backtest = AsyncMock(return_value=None)
    r.set_backtest = AsyncMock()
    return r


@pytest.fixture
def scan_svc(mock_redis):
    return ScanService(redis_client=mock_redis)


@pytest.mark.asyncio
async def test_scan_single_user(scan_svc, mock_redis):
    signal = {"ticker": "AAPL", "strategy": "trinity", "confidence": 80,
              "price": 150.0, "plan": {"stop_loss": 140, "take_profit": 170},
              "stats": {"total": {"wr": 60, "count": 30}}, "side": "LONG", "date": "2026-03-19",
              "metrics": {}}

    with patch("src.bot.services.scan_service.scan_market", return_value=[signal]):
        with patch("src.bot.services.scan_service.get_market_news", return_value="Good news"):
            results = await scan_svc.scan_for_user(user_id=1, tickers=["AAPL", "MSFT"])

    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    mock_redis.acquire_scan_lock.assert_called_once_with(1)
    mock_redis.release_scan_lock.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_scan_locked_user(scan_svc, mock_redis):
    mock_redis.acquire_scan_lock = AsyncMock(return_value=False)
    results = await scan_svc.scan_for_user(user_id=1, tickers=["AAPL"])
    assert results is None  # locked


@pytest.mark.asyncio
async def test_scan_rate_limited(scan_svc, mock_redis):
    mock_redis.check_rate_limit = AsyncMock(return_value=False)
    results = await scan_svc.scan_for_user(user_id=1, tickers=["AAPL"])
    assert results is None  # rate limited


def test_dedupe_tickers(scan_svc):
    user_tickers = {
        1: ["AAPL", "NVDA", "MSFT"],
        2: ["NVDA", "TSLA", "BTC-USD"],
        3: ["AAPL", "BTC-USD", "ETH-USD"],
    }
    unique = scan_svc.dedupe_tickers(user_tickers)
    assert sorted(unique) == sorted(["AAPL", "BTC-USD", "ETH-USD", "MSFT", "NVDA", "TSLA"])


@pytest.mark.asyncio
async def test_batch_scan(scan_svc, mock_redis):
    signals = [
        {"ticker": "AAPL", "strategy": "trinity", "confidence": 80, "price": 150.0,
         "plan": {}, "stats": {"total": {"wr": 60, "count": 30}}, "side": "LONG",
         "date": "2026-03-19", "metrics": {}},
        {"ticker": "NVDA", "strategy": "panic", "confidence": 75, "price": 140.0,
         "plan": {}, "stats": {"total": {"wr": 55, "count": 20}}, "side": "LONG",
         "date": "2026-03-19", "metrics": {}},
    ]
    user_tickers = {
        1: ["AAPL", "NVDA"],
        2: ["NVDA"],
    }
    with patch("src.bot.services.scan_service.scan_market", return_value=signals):
        with patch("src.bot.services.scan_service.get_market_news", return_value=""):
            results = await scan_svc.batch_scan(user_tickers)

    assert len(results[1]) == 2  # user 1 gets both
    assert len(results[2]) == 1  # user 2 gets only NVDA
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_scan_service.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement ScanService**

`src/bot/services/scan_service.py`:
```python
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from src.core.scanner import scan_market
from src.core.news import get_market_news

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10)


class ScanService:
    def __init__(self, redis_client):
        self.redis = redis_client

    def dedupe_tickers(self, user_tickers: dict[int, list[str]]) -> list[str]:
        unique = set()
        for tickers in user_tickers.values():
            unique.update(tickers)
        return list(unique)

    async def _run_scan(self, tickers: list[str]) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, scan_market, tickers)

    async def _fetch_news(self, ticker: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, get_market_news, ticker)

    async def _enrich_signals(self, signals: list[dict]) -> list[dict]:
        for signal in signals:
            try:
                news = await self._fetch_news(signal["ticker"])
                signal["news"] = news
            except Exception as e:
                logger.warning(f"News fetch failed for {signal['ticker']}: {e}")
                signal["news"] = None
        return signals

    async def scan_for_user(
        self, user_id: int, tickers: list[str], triggered_by: str = "manual"
    ) -> list[dict] | None:
        if not await self.redis.check_rate_limit(user_id):
            return None

        if not await self.redis.acquire_scan_lock(user_id):
            return None

        try:
            signals = await self._run_scan(tickers)
            signals = await self._enrich_signals(signals)
            return signals
        finally:
            await self.redis.release_scan_lock(user_id)

    async def batch_scan(
        self, user_tickers: dict[int, list[str]]
    ) -> dict[int, list[dict]]:
        all_tickers = self.dedupe_tickers(user_tickers)
        all_signals = await self._run_scan(all_tickers)
        all_signals = await self._enrich_signals(all_signals)

        signal_by_ticker = {}
        for s in all_signals:
            signal_by_ticker[s["ticker"]] = s

        results = {}
        for user_id, tickers in user_tickers.items():
            user_signals = [signal_by_ticker[t] for t in tickers if t in signal_by_ticker]
            results[user_id] = user_signals

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bot/test_scan_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/services/scan_service.py tests/bot/test_scan_service.py
git commit -m "feat(bot): scan service with executor bridge and smart batching"
```

---

## Task 7: Schedule Service

**Files:**
- Create: `src/bot/services/schedule_service.py`
- Create: `tests/bot/test_schedule_service.py`

- [ ] **Step 1: Write schedule service tests**

`tests/bot/test_schedule_service.py`:
```python
import pytest
from datetime import time, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot.services.schedule_service import ScheduleService


@pytest.fixture
def mock_user_svc():
    svc = MagicMock()
    return svc


@pytest.fixture
def mock_scan_svc():
    return AsyncMock()


@pytest.fixture
def mock_report_fmt():
    fmt = MagicMock()
    fmt.format_report_messages = MagicMock(return_value=["Test report"])
    return fmt


@pytest.fixture
def schedule_svc(mock_user_svc, mock_scan_svc, mock_report_fmt):
    return ScheduleService(
        user_service=mock_user_svc,
        scan_service=mock_scan_svc,
        report_formatter=mock_report_fmt,
    )


def test_collect_users_for_time(schedule_svc, mock_user_svc):
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.telegram_id = 111
    mock_user_svc.get_users_for_time.return_value = [mock_user]

    users = schedule_svc.collect_users_for_time(time(8, 0))
    assert len(users) == 1
    mock_user_svc.get_users_for_time.assert_called_once_with(time(8, 0))


def test_build_user_tickers_map(schedule_svc, mock_user_svc):
    user1 = MagicMock()
    user1.id = 1
    user2 = MagicMock()
    user2.id = 2
    mock_user_svc.get_watchlist.side_effect = [["AAPL", "NVDA"], ["NVDA", "BTC-USD"]]

    ticker_map = schedule_svc.build_user_tickers_map([user1, user2])
    assert ticker_map == {1: ["AAPL", "NVDA"], 2: ["NVDA", "BTC-USD"]}


@pytest.mark.asyncio
async def test_execute_batch_delivers_reports(schedule_svc, mock_scan_svc, mock_report_fmt):
    mock_scan_svc.batch_scan = AsyncMock(return_value={
        1: [{"ticker": "AAPL", "strategy": "trinity"}],
        2: [],
    })
    mock_report_fmt.format_report_messages.side_effect = [
        ["Report for user 1"],
        ["All quiet"],
    ]

    user_tickers = {1: ["AAPL", "NVDA"], 2: ["BTC-USD"]}
    user_telegram_map = {1: 111, 2: 222}

    deliver = AsyncMock()
    await schedule_svc.execute_batch(user_tickers, user_telegram_map, deliver)

    assert deliver.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_schedule_service.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement ScheduleService**

`src/bot/services/schedule_service.py`:
```python
import logging
from datetime import time as dt_time, datetime, timezone
from src.bot.services.report_formatter import ReportFormatter

logger = logging.getLogger(__name__)


class ScheduleService:
    def __init__(self, user_service, scan_service, report_formatter: ReportFormatter = None):
        self.user_service = user_service
        self.scan_service = scan_service
        self.report_formatter = report_formatter or ReportFormatter()

    def collect_users_for_time(self, scan_time: dt_time) -> list:
        return self.user_service.get_users_for_time(scan_time)

    def build_user_tickers_map(self, users: list) -> dict[int, list[str]]:
        result = {}
        for user in users:
            tickers = self.user_service.get_watchlist(user.id)
            if tickers:
                result[user.id] = tickers
        return result

    async def execute_batch(
        self,
        user_tickers: dict[int, list[str]],
        user_telegram_map: dict[int, int],
        deliver_fn,
    ):
        if not user_tickers:
            return

        results = await self.scan_service.batch_scan(user_tickers)

        for user_id, signals in results.items():
            telegram_id = user_telegram_map.get(user_id)
            if telegram_id is None:
                continue

            total_scanned = len(user_tickers.get(user_id, []))
            messages = self.report_formatter.format_report_messages(signals, total_scanned)

            for msg in messages:
                try:
                    await deliver_fn(telegram_id, msg)
                except Exception as e:
                    logger.error(f"Delivery failed for user {user_id}: {e}")

    async def trigger_scheduled_scan(self, scan_time: dt_time, deliver_fn):
        users = self.collect_users_for_time(scan_time)
        if not users:
            return

        user_tickers = self.build_user_tickers_map(users)
        user_telegram_map = {u.id: u.telegram_id for u in users}

        logger.info(f"Scheduled scan at {scan_time}: {len(users)} users, "
                     f"{len(self.scan_service.dedupe_tickers(user_tickers))} unique tickers")

        await self.execute_batch(user_tickers, user_telegram_map, deliver_fn)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/bot/test_schedule_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/services/schedule_service.py tests/bot/test_schedule_service.py
git commit -m "feat(bot): schedule service with batch trigger and fan-out delivery"
```

---

## Task 8: Telegram Bot Handlers

**Files:**
- Create: `src/bot/handlers/start.py`
- Create: `src/bot/handlers/watchlist.py`
- Create: `src/bot/handlers/scan.py`
- Create: `src/bot/handlers/schedule.py`
- Create: `src/bot/handlers/settings.py`
- Create: `src/bot/handlers/help.py`
- Create: `tests/bot/test_handlers.py`

- [ ] **Step 1: Write handler tests**

`tests/bot/test_handlers.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_update(text="/start", chat_id=111, user_id=111, username="testuser"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_chat.id = chat_id
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def make_context(args=None):
    ctx = MagicMock()
    ctx.args = args or []
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_start_handler_registers_user():
    from src.bot.handlers.start import start_handler

    update = make_update("/start")
    ctx = make_context()

    mock_user_svc = MagicMock()
    mock_user_svc.register.return_value = MagicMock(id=1, telegram_id=111)

    with patch("src.bot.handlers.start.get_user_service", return_value=mock_user_svc):
        await start_handler(update, ctx)

    mock_user_svc.register.assert_called_once_with(telegram_id=111, username="testuser")
    update.message.reply_text.assert_called_once()
    reply_text = update.message.reply_text.call_args[0][0]
    assert "OpenClaw" in reply_text


@pytest.mark.asyncio
async def test_watchlist_handler_shows_list():
    from src.bot.handlers.watchlist import watchlist_handler

    update = make_update("/watchlist")
    ctx = make_context()

    mock_user_svc = MagicMock()
    mock_user_svc.get_by_telegram_id.return_value = MagicMock(id=1)
    mock_user_svc.get_watchlist.return_value = ["AAPL", "NVDA"]

    with patch("src.bot.handlers.watchlist.get_user_service", return_value=mock_user_svc):
        await watchlist_handler(update, ctx)

    reply_text = update.message.reply_text.call_args[0][0]
    assert "AAPL" in reply_text
    assert "NVDA" in reply_text


@pytest.mark.asyncio
async def test_watch_handler_adds_tickers():
    from src.bot.handlers.watchlist import watch_handler

    update = make_update("/watch AAPL NVDA")
    ctx = make_context(args=["AAPL", "NVDA"])

    mock_user_svc = MagicMock()
    mock_user_svc.get_by_telegram_id.return_value = MagicMock(id=1)
    mock_user_svc.add_tickers.return_value = []

    with patch("src.bot.handlers.watchlist.get_user_service", return_value=mock_user_svc):
        await watch_handler(update, ctx)

    mock_user_svc.add_tickers.assert_called_once_with(1, ["AAPL", "NVDA"])


@pytest.mark.asyncio
async def test_scan_handler_returns_report():
    from src.bot.handlers.scan import scan_handler

    update = make_update("/scan")
    ctx = make_context()

    mock_user_svc = MagicMock()
    mock_user_svc.get_by_telegram_id.return_value = MagicMock(id=1)
    mock_user_svc.get_watchlist.return_value = ["AAPL"]

    mock_scan_svc = AsyncMock()
    mock_scan_svc.scan_for_user = AsyncMock(return_value=[{"ticker": "AAPL"}])

    mock_fmt = MagicMock()
    mock_fmt.format_report_messages.return_value = ["Report text"]

    with patch("src.bot.handlers.scan.get_user_service", return_value=mock_user_svc):
        with patch("src.bot.handlers.scan.get_scan_service", return_value=mock_scan_svc):
            with patch("src.bot.handlers.scan.get_report_formatter", return_value=mock_fmt):
                await scan_handler(update, ctx)

    update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_help_handler():
    from src.bot.handlers.help import help_handler

    update = make_update("/help")
    ctx = make_context()
    await help_handler(update, ctx)

    reply_text = update.message.reply_text.call_args[0][0]
    assert "/scan" in reply_text
    assert "/watchlist" in reply_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/bot/test_handlers.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement help handler** (simplest first)

`src/bot/handlers/help.py`:
```python
from telegram import Update
from telegram.ext import ContextTypes


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*OpenClaw Commands*\n\n"
        "*Scanning*\n"
        "/scan — Scan your watchlist now\n"
        "/scan TICKER — Scan a single ticker\n\n"
        "*Watchlist*\n"
        "/watchlist — Show your watchlist\n"
        "/watch AAPL NVDA — Add tickers\n"
        "/unwatch AAPL — Remove a ticker\n"
        "/presets — Browse preset watchlists\n\n"
        "*Schedule*\n"
        "/schedule — Show scan schedule\n"
        "/schedule 8:00 20:00 — Set scan times (UTC)\n"
        "/pause — Pause scheduled scans\n"
        "/resume — Resume scheduled scans\n\n"
        "*Settings*\n"
        "/settings — Show preferences\n"
        "/lang EN|ZH — Set language\n"
        "/mode US|CRYPTO|ALL — Set scan mode\n"
        "/strategies — Toggle strategies\n\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
```

- [ ] **Step 4: Create service locator for dependency injection in handlers**

`src/bot/handlers/__init__.py`:
```python
"""
Service locator for bot handlers.

Services are set during bot startup (bot.py) and accessed by handlers.
This avoids passing services through telegram-bot's context on every call.
"""

_services = {}


def set_services(user_service, scan_service, report_formatter, redis_client):
    _services["user_service"] = user_service
    _services["scan_service"] = scan_service
    _services["report_formatter"] = report_formatter
    _services["redis_client"] = redis_client


def get_user_service():
    return _services["user_service"]


def get_scan_service():
    return _services["scan_service"]


def get_report_formatter():
    return _services["report_formatter"]


def get_redis_client():
    return _services["redis_client"]
```

- [ ] **Step 5: Implement start handler**

`src/bot/handlers/start.py`:
```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service
from src.config import PRESET_WATCHLISTS


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    tg_user = update.effective_user

    user = user_svc.register(telegram_id=tg_user.id, username=tg_user.username)

    preset_names = list(PRESET_WATCHLISTS.keys())
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"preset:{name}")]
        for name in preset_names
    ]
    keyboard.append([InlineKeyboardButton("Custom (add later)", callback_data="preset:skip")])

    text = (
        "Welcome to *OpenClaw* 🦞\n\n"
        "I scan markets for trading signals using three strategies "
        "(Trinity, Panic, 2B) and deliver intelligence reports right here.\n\n"
        "*Quick setup — pick a watchlist:*\n"
        "Or just type /scan AAPL to try it now."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
```

- [ ] **Step 6: Implement watchlist handlers**

`src/bot/handlers/watchlist.py`:
```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service
from src.config import PRESET_WATCHLISTS


async def watchlist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    tickers = user_svc.get_watchlist(user.id)
    if not tickers:
        await update.message.reply_text(
            "Your watchlist is empty.\n\nUse /watch AAPL NVDA to add tickers or /presets to browse lists."
        )
        return

    ticker_list = ", ".join(tickers)
    await update.message.reply_text(
        f"*Your Watchlist* ({len(tickers)} tickers)\n\n{ticker_list}\n\n"
        f"/watch to add | /unwatch to remove",
        parse_mode="Markdown",
    )


async def _validate_ticker(ticker: str) -> bool:
    """Check if ticker exists on yfinance. Runs in executor to avoid blocking."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from src.core.data_fetcher import fetch_data

    loop = asyncio.get_event_loop()
    _pool = ThreadPoolExecutor(max_workers=1)
    result = await loop.run_in_executor(_pool, fetch_data, ticker, "5d")
    return result is not None and not result.empty


async def watch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    tickers = context.args
    if not tickers:
        await update.message.reply_text("Usage: /watch AAPL NVDA BTC-USD")
        return

    # Validate tickers against yfinance
    valid = []
    invalid = []
    for t in tickers:
        t_upper = t.upper()
        if await _validate_ticker(t_upper):
            valid.append(t_upper)
        else:
            invalid.append(t_upper)

    msg_parts = []
    if valid:
        rejected = user_svc.add_tickers(user.id, valid)
        added = [t for t in valid if t not in rejected]
        if added:
            msg_parts.append(f"Added: {', '.join(added)}")
        if rejected:
            msg_parts.append(f"Watchlist full (50 max), couldn't add: {', '.join(rejected)}")
    if invalid:
        msg_parts.append(f"Not found: {', '.join(invalid)} — check the symbol and try again.")
    if not msg_parts:
        msg_parts.append("Those tickers are already in your watchlist.")

    await update.message.reply_text("\n".join(msg_parts))


async def unwatch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /unwatch AAPL")
        return

    ticker = context.args[0].upper()
    user_svc.remove_ticker(user.id, ticker)
    await update.message.reply_text(f"Removed {ticker} from your watchlist.")


async def presets_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"{name} ({len(tickers)})", callback_data=f"preset:{name}")]
        for name, tickers in PRESET_WATCHLISTS.items()
    ]

    await update.message.reply_text(
        "*Preset Watchlists*\n\nPick one to load:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def preset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("preset:"):
        return

    preset_name = data[len("preset:"):]
    if preset_name == "skip":
        await query.edit_message_text("No worries! Use /watch AAPL NVDA to add tickers anytime.")
        return

    tickers = PRESET_WATCHLISTS.get(preset_name)
    if not tickers:
        await query.edit_message_text("Preset not found.")
        return

    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(query.from_user.id)
    if not user:
        return

    rejected = user_svc.add_tickers(user.id, tickers)
    added_count = len(tickers) - len(rejected)
    await query.edit_message_text(
        f"Loaded *{preset_name}* — {added_count} tickers added to your watchlist.\n\n"
        f"Use /scan to run your first scan!",
        parse_mode="Markdown",
    )
```

- [ ] **Step 7: Implement scan handler**

`src/bot/handlers/scan.py`:
```python
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service, get_scan_service, get_report_formatter


async def scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    scan_svc = get_scan_service()
    fmt = get_report_formatter()

    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    # Single ticker mode: /scan NVDA
    if context.args:
        tickers = [context.args[0].upper()]
    else:
        tickers = user_svc.get_watchlist(user.id)

    if not tickers:
        await update.message.reply_text(
            "No tickers to scan. Use /watch AAPL NVDA or /presets to add some."
        )
        return

    await update.message.reply_text(f"Scanning {len(tickers)} ticker{'s' if len(tickers) != 1 else ''}...")

    signals = await scan_svc.scan_for_user(user_id=user.id, tickers=tickers)

    if signals is None:
        await update.message.reply_text(
            "Your last scan is still running, hang tight. Or you've hit the rate limit (10/hour)."
        )
        return

    messages = fmt.format_report_messages(signals, total_scanned=len(tickers))
    for msg in messages:
        await update.message.reply_text(msg, parse_mode="Markdown")
```

- [ ] **Step 8: Implement schedule handler**

`src/bot/handlers/schedule.py`:
```python
from datetime import time as dt_time
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service


async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if not context.args:
        scheds = user_svc.get_schedules(user.id)
        if not scheds:
            await update.message.reply_text(
                "No scan schedule set.\n\nUsage: /schedule 8:00 20:00"
            )
            return
        lines = []
        for s in scheds:
            status = "⏸ paused" if s.is_paused else "▶️ active"
            lines.append(f"  {s.scan_time.strftime('%H:%M')} UTC — {status}")
        await update.message.reply_text(
            f"*Your Scan Schedule*\n\n" + "\n".join(lines) + "\n\n/pause | /resume",
            parse_mode="Markdown",
        )
        return

    times = []
    for arg in context.args:
        try:
            parts = arg.split(":")
            times.append(dt_time(int(parts[0]), int(parts[1])))
        except (ValueError, IndexError):
            await update.message.reply_text(f"Invalid time format: {arg}. Use HH:MM (e.g., 8:00)")
            return

    user_svc.set_schedules(user.id, times)
    time_strs = ", ".join(t.strftime("%H:%M") for t in times)
    await update.message.reply_text(f"Schedule set: {time_strs} UTC daily.")


async def pause_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return
    from src.bot.db.models import UserSchedule
    for sched in user_svc.get_schedules(user.id):
        sched.is_paused = True
    user_svc.session.commit()
    await update.message.reply_text("Scheduled scans paused. /resume to restart.")


async def resume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return
    for sched in user_svc.get_schedules(user.id):
        sched.is_paused = False
    user_svc.session.commit()
    await update.message.reply_text("Scheduled scans resumed.")
```

- [ ] **Step 9: Implement settings handler**

`src/bot/handlers/settings.py`:
```python
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.handlers import get_user_service


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    strategies = ", ".join(user.strategies) if user.strategies else "All"
    await update.message.reply_text(
        f"*Your Settings*\n\n"
        f"Language: {user.lang}\n"
        f"Scan Mode: {user.scan_mode}\n"
        f"Strategies: {strategies}\n\n"
        f"/lang EN|ZH — change language\n"
        f"/mode US|CRYPTO|ALL — change scan mode",
        parse_mode="Markdown",
    )


async def lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return

    if not context.args or context.args[0].upper() not in ("EN", "ZH"):
        await update.message.reply_text("Usage: /lang EN or /lang ZH")
        return

    lang = context.args[0].upper()
    user_svc.update_preferences(user.id, lang=lang)
    await update.message.reply_text(f"Language set to {lang}.")


async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        return

    if not context.args or context.args[0].upper() not in ("US", "CRYPTO", "ALL"):
        await update.message.reply_text("Usage: /mode US, /mode CRYPTO, or /mode ALL")
        return

    mode = context.args[0].upper()
    user_svc.update_preferences(user.id, scan_mode=mode)
    await update.message.reply_text(f"Scan mode set to {mode}.")


ALL_STRATEGIES = ["TRINITY", "PANIC", "2B"]


async def strategies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_svc = get_user_service()
    user = user_svc.get_by_telegram_id(update.effective_user.id)
    if not user:
        await update.message.reply_text("Use /start to set up your account first.")
        return

    if not context.args:
        current = user.strategies or ALL_STRATEGIES
        lines = [f"  {'✅' if s in current else '❌'} {s}" for s in ALL_STRATEGIES]
        await update.message.reply_text(
            f"*Active Strategies*\n\n" + "\n".join(lines) +
            "\n\nToggle: /strategies TRINITY (toggles on/off)",
            parse_mode="Markdown",
        )
        return

    toggle = context.args[0].upper()
    if toggle not in ALL_STRATEGIES:
        await update.message.reply_text(f"Unknown strategy. Choose from: {', '.join(ALL_STRATEGIES)}")
        return

    current = list(user.strategies or ALL_STRATEGIES)
    if toggle in current:
        current.remove(toggle)
        if not current:
            await update.message.reply_text("You need at least one strategy active.")
            return
        action = "disabled"
    else:
        current.append(toggle)
        action = "enabled"

    user_svc.update_preferences(user.id, strategies=current)
    await update.message.reply_text(f"{toggle} {action}. Active: {', '.join(current)}")
```

- [ ] **Step 10: Run handler tests to verify they pass**

```bash
pytest tests/bot/test_handlers.py -v
```
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add src/bot/handlers/ tests/bot/test_handlers.py
git commit -m "feat(bot): Telegram command handlers with onboarding, watchlist, scan, schedule, settings"
```

---

## Task 9: Health Check Endpoint

**Files:**
- Create: `src/bot/health.py`

- [ ] **Step 1: Implement health check**

`src/bot/health.py`:
```python
import logging
from aiohttp import web

logger = logging.getLogger(__name__)


async def health_check(request):
    return web.json_response({"status": "ok"})


async def start_health_server(port: int = 8080):
    app = web.Application()
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server running on port {port}")
    return runner
```

- [ ] **Step 2: Commit**

```bash
git add src/bot/health.py
git commit -m "feat(bot): aiohttp health check endpoint"
```

---

## Task 10: Bot Entry Point — Wire Everything Together

**Files:**
- Create: `src/bot.py`

- [ ] **Step 1: Implement bot.py**

`src/bot.py`:
```python
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from bot.db.models import Base
from bot.db.session import DATABASE_URL
from bot.redis_client import RedisClient
from bot.services.user_service import UserService
from bot.services.scan_service import ScanService
from bot.services.schedule_service import ScheduleService
from bot.services.report_formatter import ReportFormatter
from bot.handlers import set_services
from bot.handlers.start import start_handler
from bot.handlers.watchlist import watchlist_handler, watch_handler, unwatch_handler, presets_handler, preset_callback
from bot.handlers.scan import scan_handler
from bot.handlers.schedule import schedule_handler, pause_handler, resume_handler
from bot.handlers.settings import settings_handler, lang_handler, mode_handler, strategies_handler
from bot.handlers.help import help_handler
from bot.health import start_health_server

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_sync_engine():
    """Create sync engine for UserService (ORM operations are simple and fast)."""
    url = os.getenv("DATABASE_SYNC_URL")
    if not url:
        # Convert asyncpg URL to psycopg2 for sync access
        url = DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    return create_engine(url)


async def scheduled_scan_tick(bot, schedule_service: ScheduleService):
    """Called every minute by APScheduler. Checks if any users need scanning."""
    now = datetime.now(timezone.utc).time().replace(second=0, microsecond=0)

    async def deliver(telegram_id: int, text: str):
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")

    await schedule_service.trigger_scheduled_scan(now, deliver)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Initialize services
    sync_engine = create_sync_engine()
    Base.metadata.create_all(sync_engine)  # Dev convenience; prod uses Alembic
    db_session = Session(sync_engine)

    redis_client = RedisClient()
    user_service = UserService(db_session)
    scan_service = ScanService(redis_client=redis_client)
    report_formatter = ReportFormatter()
    schedule_service = ScheduleService(user_service, scan_service, report_formatter)

    set_services(user_service, scan_service, report_formatter, redis_client)

    # Build Telegram bot
    app = ApplicationBuilder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("watchlist", watchlist_handler))
    app.add_handler(CommandHandler("watch", watch_handler))
    app.add_handler(CommandHandler("unwatch", unwatch_handler))
    app.add_handler(CommandHandler("presets", presets_handler))
    app.add_handler(CommandHandler("scan", scan_handler))
    app.add_handler(CommandHandler("schedule", schedule_handler))
    app.add_handler(CommandHandler("pause", pause_handler))
    app.add_handler(CommandHandler("resume", resume_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("lang", lang_handler))
    app.add_handler(CommandHandler("mode", mode_handler))
    app.add_handler(CommandHandler("strategies", strategies_handler))
    app.add_handler(CallbackQueryHandler(preset_callback, pattern="^preset:"))

    # Schedule: check every minute for users who need scanning
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_scan_tick,
        "interval",
        minutes=1,
        args=[app.bot, schedule_service],
    )

    logger.info("Starting OpenClaw bot...")

    # Start health check + scheduler alongside the bot
    async def post_init(application):
        await start_health_server(port=int(os.getenv("HEALTH_PORT", "8080")))
        scheduler.start()
        logger.info("Scheduler and health check started")

    async def post_shutdown(application):
        scheduler.shutdown()
        await redis_client.close()
        db_session.close()
        logger.info("Shutdown complete")

    app.post_init = post_init
    app.post_shutdown = post_shutdown
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import chain works**

```bash
cd /Users/bytedance/features/OpenClaw-financial-intelligence
python -c "
import sys; sys.path.insert(0, 'src')
from bot.handlers.help import help_handler
from bot.services.report_formatter import ReportFormatter
from bot.services.scan_service import ScanService
from bot.redis_client import RedisClient
print('All imports OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/bot.py
git commit -m "feat(bot): main entry point wiring bot, scheduler, health check, and services"
```

---

## Task 11: Run Full Test Suite & Fix Issues

**Files:**
- All test files

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 2: Fix any failures**

Address import issues, missing mocks, or assertion mismatches.

- [ ] **Step 3: Run existing tests to confirm no regressions**

```bash
pytest tests/test_main.py tests/test_indicators.py tests/test_tracker_unit.py -v
```
Expected: PASS — existing tests unaffected

- [ ] **Step 4: Commit fixes**

```bash
git add -u
git commit -m "fix(bot): resolve test issues and confirm no regressions"
```

---

## Task 12: Local Integration Test

**Files:**
- Create: `tests/bot/test_integration.py`

- [ ] **Step 1: Write integration smoke test**

`tests/bot/test_integration.py`:
```python
"""
Integration test for bot services working together.
Requires: docker compose up -d (postgres + redis)
"""
import pytest


@pytest.mark.integration
def test_user_registration_and_scan_flow():
    """Full flow: register user → add watchlist → mock scan → format report."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.bot.db.models import Base, User
    from src.bot.services.user_service import UserService
    from src.bot.services.report_formatter import ReportFormatter

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user_svc = UserService(db)

        # Register
        user = user_svc.register(telegram_id=12345, username="test_trader")
        assert user.id is not None

        # Add watchlist
        rejected = user_svc.add_tickers(user.id, ["AAPL", "NVDA", "BTC-USD"])
        assert rejected == []
        assert len(user_svc.get_watchlist(user.id)) == 3

        # Format a mock report
        fmt = ReportFormatter()
        signals = [
            {
                "ticker": "AAPL",
                "strategy": "trinity",
                "price": 150.0,
                "confidence": 82,
                "metrics": {},
                "stats": {"total": {"wr": 60.0, "count": 40}},
                "plan": {"stop_loss": 140.0, "take_profit": 170.0},
                "side": "LONG",
                "date": "2026-03-19",
            }
        ]
        messages = fmt.format_report_messages(signals, total_scanned=3)
        assert len(messages) >= 1
        assert "AAPL" in messages[0]
        assert "Trinity" in messages[0] or "trinity" in messages[0].lower()

    engine.dispose()
```

- [ ] **Step 2: Run integration test**

```bash
pytest tests/bot/test_integration.py -v -m integration
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/bot/test_integration.py
git commit -m "test(bot): integration smoke test for user registration and report flow"
```

---

## Summary

| Task | What It Builds | Key Files |
|------|---------------|-----------|
| 1 | Project setup, deps, Docker, config | requirements.txt, Dockerfile, docker-compose.yml, config.py |
| 2 | Database models + Alembic | db/models.py, db/session.py, migrations/ |
| 3 | Redis client (cache, locks, rate limits) | redis_client.py |
| 4 | User service (CRUD, watchlists, schedules) | services/user_service.py |
| 5 | Report formatter (signals → Telegram) | services/report_formatter.py |
| 6 | Scan service (executor bridge, batching) | services/scan_service.py |
| 7 | Schedule service (batch trigger, fan-out) | services/schedule_service.py |
| 8 | Telegram handlers (all commands) | handlers/*.py |
| 9 | Health check endpoint | health.py |
| 10 | Entry point (wire everything) | bot.py |
| 11 | Full test suite validation | all tests |
| 12 | Integration smoke test | test_integration.py |
