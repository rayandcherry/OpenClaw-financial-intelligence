import pytest
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tracker.service import TrackerService


@pytest.fixture
def tmp_positions_file():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def mock_fetch():
    """Mock fetch_data so add_position doesn't hit yfinance."""
    df = pd.DataFrame({"Close": [150.0], "High": [155.0], "Low": [145.0], "ATR_14": [3.5]})
    with patch("src.tracker.service.fetch_data", return_value=df):
        with patch("src.tracker.service.calculate_indicators", return_value=df):
            yield


@pytest.fixture
def service(tmp_positions_file, mock_fetch):
    svc = TrackerService(initial_balance=100000)
    svc.positions_file = tmp_positions_file
    return svc


def test_save_and_load_positions(service, tmp_positions_file, mock_fetch):
    service.add_position("AAPL", 150.0, 10, side="LONG")
    service.save_positions()

    assert os.path.exists(tmp_positions_file)
    with open(tmp_positions_file) as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert data[0]["ticker"] == "AAPL"

    svc2 = TrackerService(initial_balance=100000)
    svc2.positions_file = tmp_positions_file
    svc2.load_positions()
    assert "AAPL" in svc2.positions


def test_remove_position(service):
    service.add_position("NVDA", 140.0, 5, side="LONG")
    assert "NVDA" in service.positions
    result = service.remove_position("NVDA")
    assert "NVDA" not in service.positions
    assert result["ticker"] == "NVDA"


def test_remove_nonexistent_position(service):
    result = service.remove_position("FAKE")
    assert result.get("error") is not None


def test_save_empty(service, tmp_positions_file):
    service.save_positions()
    with open(tmp_positions_file) as f:
        data = json.load(f)
    assert data == []


def test_load_missing_file(service):
    service.positions_file = "/tmp/nonexistent_positions_12345.json"
    service.load_positions()
    assert service.positions == {}


def test_tier_a_addon_merges_when_breakeven_locked(service, mock_fetch):
    """NVDA is Tier A; with breakeven active, second add averages up qty + entry."""
    service.add_position("NVDA", 100.0, 10, side="LONG")
    # Force breakeven on the existing position so add-on is eligible.
    service.positions["NVDA"].is_breakeven_active = True
    service.positions["NVDA"].current_sl = 100.1  # locked at entry+0.1%

    # Add 5 more at $120
    service.add_position("NVDA", 120.0, 5, side="LONG")

    pos = service.positions["NVDA"]
    # Average entry = (100*10 + 120*5) / 15 = 106.667
    assert abs(pos.entry_price - 106.6667) < 0.01
    assert pos.qty == 15.0
    # SL preserved at the higher of the locked existing SL and the new ATR stop
    assert pos.current_sl >= 100.1
    assert pos.is_breakeven_active is True


def test_addon_blocked_when_not_breakeven_locked(service, mock_fetch, capsys):
    """Even on Tier A, can't add until the original is risk-free."""
    service.add_position("NVDA", 100.0, 10, side="LONG")
    service.add_position("NVDA", 120.0, 5, side="LONG")  # should be blocked
    captured = capsys.readouterr()
    assert "blocked" in captured.out.lower()
    # Original position untouched
    assert service.positions["NVDA"].qty == 10.0
    assert service.positions["NVDA"].entry_price == 100.0


def test_addon_blocked_for_tier_b(service, mock_fetch, capsys):
    """CSCO is Tier B — no add-on allowed even when breakeven locked."""
    service.add_position("CSCO", 100.0, 10, side="LONG")
    service.positions["CSCO"].is_breakeven_active = True
    service.add_position("CSCO", 110.0, 5, side="LONG")
    captured = capsys.readouterr()
    assert "blocked" in captured.out.lower()
    assert service.positions["CSCO"].qty == 10.0
