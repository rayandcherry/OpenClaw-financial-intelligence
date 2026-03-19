from __future__ import annotations

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

    async def acquire_scan_lock(self, user_id: int) -> bool:
        return await self.redis.set(
            f"scan_lock:{user_id}", "running", nx=True, ex=self.scan_lock_ttl
        )

    async def release_scan_lock(self, user_id: int) -> None:
        await self.redis.delete(f"scan_lock:{user_id}")

    async def check_rate_limit(self, user_id: int, max_per_hour: int = None) -> bool:
        if max_per_hour is None:
            max_per_hour = BOT_CONFIG["rate_limit_scans_per_hour"]
        key = f"rate:{user_id}:scans"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 3600)
        return count <= max_per_hour

    async def get_rate_limit_ttl(self, user_id: int) -> int:
        """Return seconds until rate limit resets, or 0 if no limit active."""
        ttl = await self.redis.ttl(f"rate:{user_id}:scans")
        return max(ttl, 0)

    async def close(self):
        await self.redis.close()
