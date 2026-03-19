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
async def test_watch_handler_validates_and_adds():
    from src.bot.handlers.watchlist import watch_handler

    update = make_update("/watch AAPL FAKE")
    ctx = make_context(args=["AAPL", "FAKE"])

    mock_user_svc = MagicMock()
    mock_user_svc.get_by_telegram_id.return_value = MagicMock(id=1)
    mock_user_svc.add_tickers.return_value = []

    with patch("src.bot.handlers.watchlist.get_user_service", return_value=mock_user_svc):
        with patch("src.bot.handlers.watchlist._validate_ticker", side_effect=[True, False]):
            await watch_handler(update, ctx)

    # Only AAPL should be added (FAKE failed validation)
    mock_user_svc.add_tickers.assert_called_once_with(1, ["AAPL"])
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Added: AAPL" in reply_text
    assert "Not found: FAKE" in reply_text


@pytest.mark.asyncio
async def test_help_handler():
    from src.bot.handlers.help import help_handler

    update = make_update("/help")
    ctx = make_context()
    await help_handler(update, ctx)

    reply_text = update.message.reply_text.call_args[0][0]
    assert "/scan" in reply_text
    assert "/watchlist" in reply_text
