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


@pytest.mark.asyncio
async def test_execute_batch_deactivates_blocked_user(schedule_svc, mock_user_svc, mock_scan_svc, mock_report_fmt):
    mock_scan_svc.batch_scan = AsyncMock(return_value={
        1: [{"ticker": "AAPL", "strategy": "trinity"}],
    })
    mock_report_fmt.format_report_messages.return_value = ["Report"]

    # Simulate Telegram 403 Forbidden
    forbidden_error = Exception("Forbidden: bot was blocked by the user")
    deliver = AsyncMock(side_effect=forbidden_error)

    user_tickers = {1: ["AAPL"]}
    user_telegram_map = {1: 111}

    with patch("src.bot.services.schedule_service._is_blocked_error", return_value=True):
        await schedule_svc.execute_batch(user_tickers, user_telegram_map, deliver)

    mock_user_svc.deactivate.assert_called_once_with(1)
    # Should only attempt delivery once (no retries for blocked users)
    assert deliver.call_count == 1
