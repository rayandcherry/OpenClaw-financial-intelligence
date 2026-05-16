"""Per-position earnings calendar — yfinance-backed with a 7-day file cache.

Earnings dates rarely move once announced (~quarterly), so a coarse TTL keeps
the daily monitor cycle cheap without going stale on real revisions. Cache
lives in data/cache/earnings.json alongside the backtest cache.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

try:
    import yfinance as yf
except ImportError:
    yf = None  # tests can monkeypatch fetch_next_earnings directly


CACHE_FILE = "data/cache/earnings.json"
CACHE_TTL_DAYS = 7

# Days-to-earnings ≤ this fires the EARNINGS_NEAR alert. Gap risk is highest
# in the last week — beyond that the user has time to plan trims/exits.
EARNINGS_NEAR_THRESHOLD_DAYS = 5


@dataclass(frozen=True)
class EarningsInfo:
    ticker: str
    next_date: Optional[date]      # None if yfinance has no future date
    days_away: Optional[int]        # signed; negative if already past

    @property
    def is_near(self) -> bool:
        return (self.days_away is not None
                and 0 <= self.days_away <= EARNINGS_NEAR_THRESHOLD_DAYS)


def fetch_next_earnings(ticker: str) -> Optional[date]:
    """Hit yfinance Ticker.calendar for the next earnings date. Returns None
    on any failure (network, missing data, parse error)."""
    if yf is None:
        return None
    try:
        cal = yf.Ticker(ticker).calendar
    except Exception:
        return None
    if not isinstance(cal, dict):
        return None
    raw = cal.get('Earnings Date')
    if not raw:
        return None
    # yfinance returns list[datetime.date]; can be 1 entry (confirmed) or 2
    # (estimated window). Take the earliest — that's the soonest gap risk.
    candidates = raw if isinstance(raw, list) else [raw]
    parsed = []
    for c in candidates:
        if isinstance(c, datetime):
            parsed.append(c.date())
        elif isinstance(c, date):
            parsed.append(c)
    return min(parsed) if parsed else None


class EarningsCache:
    """File-backed cache of next-earnings dates. Keyed by ticker."""

    def __init__(self, cache_file: str = CACHE_FILE, ttl_days: int = CACHE_TTL_DAYS):
        self.cache_file = cache_file
        self.ttl_days = ttl_days
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.cache_file):
            return {}
        try:
            with open(self.cache_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._data, f, indent=2)
        except IOError:
            pass  # cache miss next time is the worst case

    def get(self, ticker: str) -> Optional[date]:
        entry = self._data.get(ticker.upper())
        if not entry:
            return None
        try:
            fetched_at = datetime.fromisoformat(entry['fetched_at'])
        except (KeyError, ValueError):
            return None
        if datetime.now() - fetched_at > timedelta(days=self.ttl_days):
            return None  # expired
        raw_date = entry.get('next_date')
        if not raw_date:
            # Cached negative result — yfinance had nothing. Honor it within
            # TTL so we don't hammer the API for tickers with no schedule.
            return None
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            return None

    def set(self, ticker: str, next_date: Optional[date]) -> None:
        self._data[ticker.upper()] = {
            'next_date': next_date.isoformat() if next_date else None,
            'fetched_at': datetime.now().isoformat(),
        }
        self._save()

    def has_fresh_entry(self, ticker: str) -> bool:
        """True if a non-expired record exists (including cached-None)."""
        entry = self._data.get(ticker.upper())
        if not entry:
            return False
        try:
            fetched_at = datetime.fromisoformat(entry['fetched_at'])
        except (KeyError, ValueError):
            return False
        return datetime.now() - fetched_at <= timedelta(days=self.ttl_days)


_DEFAULT_CACHE: Optional[EarningsCache] = None


def _default_cache() -> EarningsCache:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = EarningsCache()
    return _DEFAULT_CACHE


def get_position_earnings(ticker: str, today: Optional[date] = None,
                           cache: Optional[EarningsCache] = None) -> EarningsInfo:
    """High-level: return cached-or-fresh EarningsInfo for a position.

    `today` overrides the reference date (for tests). `cache` injection lets
    tests use isolated caches.
    """
    cache = cache if cache is not None else _default_cache()
    today = today or date.today()

    if cache.has_fresh_entry(ticker):
        next_date = cache.get(ticker)
    else:
        next_date = fetch_next_earnings(ticker)
        cache.set(ticker, next_date)

    if next_date is None:
        return EarningsInfo(ticker=ticker, next_date=None, days_away=None)
    return EarningsInfo(
        ticker=ticker,
        next_date=next_date,
        days_away=(next_date - today).days,
    )
