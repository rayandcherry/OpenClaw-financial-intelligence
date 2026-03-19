from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from src.core.scanner import scan_market
from src.core.news import get_market_news

logger = logging.getLogger(__name__)


class ScanService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self._executor = ThreadPoolExecutor(max_workers=10)

    def shutdown(self):
        """Shut down the thread pool, waiting for in-flight scans to finish."""
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("Scan service executor shut down")

    @staticmethod
    def filter_by_mode(tickers: list[str], scan_mode: str) -> list[str]:
        """Filter tickers by scan mode (US/CRYPTO/ALL)."""
        if not scan_mode or scan_mode == "ALL":
            return tickers
        if scan_mode == "CRYPTO":
            return [t for t in tickers if t.endswith("-USD")]
        if scan_mode == "US":
            return [t for t in tickers if not t.endswith("-USD")]
        return tickers

    def dedupe_tickers(self, user_tickers: dict[int, list[str]]) -> list[str]:
        unique = set()
        for tickers in user_tickers.values():
            unique.update(tickers)
        return list(unique)

    SCAN_TIMEOUT = 120  # seconds - yfinance can hang
    NEWS_TIMEOUT = 10   # seconds per ticker

    async def _run_scan(self, tickers: list[str]) -> list[dict]:
        return await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(self._executor, scan_market, tickers),
            timeout=self.SCAN_TIMEOUT,
        )

    async def _fetch_news(self, ticker: str) -> str:
        return await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(self._executor, get_market_news, ticker),
            timeout=self.NEWS_TIMEOUT,
        )

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

    # Map user-facing strategy names to scanner output names
    _STRATEGY_NAME_MAP = {
        "trinity": {"trinity"},
        "panic": {"panic"},
        "2b": {"2b_reversal", "2b reversal", "2b"},
    }

    def _filter_by_strategies(self, signals: list[dict], strategies: list[str] | None) -> list[dict]:
        """Filter signals to only include user's enabled strategies."""
        if not strategies:
            return signals
        allowed = set()
        for s in strategies:
            matches = self._STRATEGY_NAME_MAP.get(s.lower(), {s.lower()})
            allowed.update(matches)
        return [s for s in signals if s.get("strategy", "").lower() in allowed]

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
        self, user_tickers: dict[int, list[str]],
        user_strategies: dict[int, list[str] | None] | None = None,
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
            if user_strategies and user_id in user_strategies:
                user_signals = self._filter_by_strategies(user_signals, user_strategies[user_id])
            results[user_id] = user_signals

        return results
