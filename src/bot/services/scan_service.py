from __future__ import annotations

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

    async def _safe_fetch_news(self, ticker: str) -> tuple[str, str | None]:
        """Fetch news for a ticker, returning (ticker, news_text) or (ticker, None) on failure."""
        try:
            news = await self._fetch_news(ticker)
            return ticker, news
        except Exception as e:
            logger.warning(f"News fetch failed for {ticker}: {e}")
            return ticker, None

    async def _enrich_signals(self, signals: list[dict]) -> list[dict]:
        if not signals:
            return signals
        # Fetch news for all signals concurrently
        tasks = [self._safe_fetch_news(s["ticker"]) for s in signals]
        results = await asyncio.gather(*tasks)
        news_map = dict(results)
        for signal in signals:
            signal["news"] = news_map.get(signal["ticker"])
        return signals

    def _filter_by_strategies(self, signals: list[dict], strategies: list[str] | None) -> list[dict]:
        """Filter signals to only include user's enabled strategies."""
        if not strategies:
            return signals
        # Normalize: strategy names in signals are lowercase ("trinity", "panic", "2B_Reversal")
        allowed = {s.lower() for s in strategies}
        # Also map "2b" -> matches "2b_reversal"
        return [s for s in signals if s.get("strategy", "").lower() in allowed
                or any(s.get("strategy", "").lower().startswith(a.lower()) for a in strategies)]

    async def scan_for_user(
        self, user_id: int, tickers: list[str], strategies: list[str] | None = None,
        triggered_by: str = "manual",
    ) -> list[dict] | None:
        if not await self.redis.check_rate_limit(user_id):
            return None

        if not await self.redis.acquire_scan_lock(user_id):
            return None

        try:
            signals = await self._run_scan(tickers)
            signals = self._filter_by_strategies(signals, strategies)
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
