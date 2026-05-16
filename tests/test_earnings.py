"""Unit tests for per-position earnings calendar + cache (no network)."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from src.core import earnings as earnings_mod
from src.core.earnings import (
    EARNINGS_NEAR_THRESHOLD_DAYS,
    EarningsCache,
    EarningsInfo,
    get_position_earnings,
)


@pytest.fixture
def tmp_cache(tmp_path):
    cache_file = str(tmp_path / "earnings.json")
    return EarningsCache(cache_file=cache_file, ttl_days=7)


# --- EarningsInfo.is_near ---

def test_is_near_within_threshold():
    info = EarningsInfo("NVDA", date(2026, 5, 20), days_away=5)
    assert info.is_near is True


def test_is_near_at_zero():
    info = EarningsInfo("NVDA", date(2026, 5, 15), days_away=0)
    assert info.is_near is True


def test_is_near_past_threshold():
    info = EarningsInfo("NVDA", date(2026, 5, 25), days_away=EARNINGS_NEAR_THRESHOLD_DAYS + 1)
    assert info.is_near is False


def test_is_near_negative_days():
    """Past earnings (already happened) should not flag as near."""
    info = EarningsInfo("NVDA", date(2026, 5, 10), days_away=-5)
    assert info.is_near is False


def test_is_near_none():
    info = EarningsInfo("XYZ", None, None)
    assert info.is_near is False


# --- EarningsCache TTL + persistence ---

def test_cache_miss_when_empty(tmp_cache):
    assert tmp_cache.get("NVDA") is None
    assert tmp_cache.has_fresh_entry("NVDA") is False


def test_cache_round_trip(tmp_cache):
    tmp_cache.set("NVDA", date(2026, 5, 20))
    assert tmp_cache.has_fresh_entry("NVDA") is True
    assert tmp_cache.get("NVDA") == date(2026, 5, 20)


def test_cache_ttl_expiry(tmp_cache):
    tmp_cache.set("NVDA", date(2026, 5, 20))
    # Manually age the entry past the 7-day TTL.
    aged = (datetime.now() - timedelta(days=8)).isoformat()
    tmp_cache._data["NVDA"]["fetched_at"] = aged
    assert tmp_cache.has_fresh_entry("NVDA") is False
    assert tmp_cache.get("NVDA") is None


def test_cache_caches_none_negative_result(tmp_cache):
    """Cache a 'no future earnings' result so we don't refetch every monitor."""
    tmp_cache.set("XYZ", None)
    assert tmp_cache.has_fresh_entry("XYZ") is True
    assert tmp_cache.get("XYZ") is None  # honors cached-None within TTL


def test_cache_persists_across_instances(tmp_path):
    cache_file = str(tmp_path / "earnings.json")
    c1 = EarningsCache(cache_file=cache_file, ttl_days=7)
    c1.set("NVDA", date(2026, 5, 20))
    c2 = EarningsCache(cache_file=cache_file, ttl_days=7)
    assert c2.get("NVDA") == date(2026, 5, 20)


# --- get_position_earnings (with cache injection) ---

def test_get_position_earnings_cache_hit_skips_fetch(tmp_cache):
    """Fresh cache entry → fetch_next_earnings is NOT called."""
    tmp_cache.set("NVDA", date(2026, 5, 20))
    with patch.object(earnings_mod, "fetch_next_earnings") as mock_fetch:
        info = get_position_earnings("NVDA", today=date(2026, 5, 15), cache=tmp_cache)
    mock_fetch.assert_not_called()
    assert info.next_date == date(2026, 5, 20)
    assert info.days_away == 5
    assert info.is_near is True


def test_get_position_earnings_cache_miss_fetches(tmp_cache):
    with patch.object(earnings_mod, "fetch_next_earnings", return_value=date(2026, 6, 1)) as mock_fetch:
        info = get_position_earnings("TSM", today=date(2026, 5, 15), cache=tmp_cache)
    mock_fetch.assert_called_once_with("TSM")
    assert info.next_date == date(2026, 6, 1)
    assert info.days_away == 17
    assert info.is_near is False
    # Result is now cached for next call.
    assert tmp_cache.get("TSM") == date(2026, 6, 1)


def test_get_position_earnings_handles_missing_data(tmp_cache):
    """yfinance returns None → EarningsInfo with None fields."""
    with patch.object(earnings_mod, "fetch_next_earnings", return_value=None):
        info = get_position_earnings("UNKNOWN", today=date(2026, 5, 15), cache=tmp_cache)
    assert info.next_date is None
    assert info.days_away is None
    assert info.is_near is False
