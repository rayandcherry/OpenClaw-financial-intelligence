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
    r.ttl = AsyncMock(return_value=-2)
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
