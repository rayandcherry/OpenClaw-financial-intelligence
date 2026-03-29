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
