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
    assert results is None


@pytest.mark.asyncio
async def test_scan_rate_limited(scan_svc, mock_redis):
    mock_redis.check_rate_limit = AsyncMock(return_value=False)
    results = await scan_svc.scan_for_user(user_id=1, tickers=["AAPL"])
    assert results is None


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

    assert len(results[1]) == 2
    assert len(results[2]) == 1


def test_filter_by_strategies(scan_svc):
    signals = [
        {"ticker": "AAPL", "strategy": "trinity"},
        {"ticker": "NVDA", "strategy": "panic"},
        {"ticker": "MSFT", "strategy": "2B_Reversal"},
    ]
    # Only trinity enabled
    filtered = scan_svc._filter_by_strategies(signals, ["TRINITY"])
    assert len(filtered) == 1
    assert filtered[0]["ticker"] == "AAPL"

    # 2B enabled (matches 2B_Reversal)
    filtered = scan_svc._filter_by_strategies(signals, ["2B"])
    assert len(filtered) == 1
    assert filtered[0]["ticker"] == "MSFT"

    # All enabled
    filtered = scan_svc._filter_by_strategies(signals, ["TRINITY", "PANIC", "2B"])
    assert len(filtered) == 3

    # None means no filter
    filtered = scan_svc._filter_by_strategies(signals, None)
    assert len(filtered) == 3


def test_filter_by_mode():
    from src.bot.services.scan_service import ScanService
    tickers = ["AAPL", "NVDA", "BTC-USD", "ETH-USD"]

    assert ScanService.filter_by_mode(tickers, "ALL") == tickers
    assert ScanService.filter_by_mode(tickers, None) == tickers
    assert ScanService.filter_by_mode(tickers, "US") == ["AAPL", "NVDA"]
    assert ScanService.filter_by_mode(tickers, "CRYPTO") == ["BTC-USD", "ETH-USD"]
