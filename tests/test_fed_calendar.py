from datetime import date

from src.core.fed_calendar import (
    FOMC_2026,
    FedEvent,
    build_calendar,
    format_calendar_block,
    get_upcoming_events,
)


def test_fomc_2026_count_and_ordering():
    assert len(FOMC_2026) == 8
    for prev, curr in zip(FOMC_2026, FOMC_2026[1:]):
        assert prev < curr


def test_build_calendar_2026_has_fomc_beige_and_monthly():
    cal = build_calendar(2026)
    cats = {e.category for e in cal}
    assert {"FOMC", "Beige", "CPI", "PCE", "NFP", "Retail"} <= cats
    # 8 FOMC + 8 Beige + 12 each of NFP/CPI/PCE/Retail = 16 + 48 = 64
    assert len(cal) == 64


def test_nfp_is_first_friday():
    cal = build_calendar(2026)
    # NFP Jan 2026: 1st Friday of Jan 2026 = Jan 2 (Fri)
    jan_nfp = next(e for e in cal if e.category == "NFP" and e.date.month == 1)
    assert jan_nfp.date == date(2026, 1, 2)
    assert jan_nfp.date.weekday() == 4


def test_core_pce_is_last_friday():
    cal = build_calendar(2026)
    # Last Friday of May 2026 = May 29
    may_pce = next(e for e in cal if e.category == "PCE" and e.date.month == 5)
    assert may_pce.date == date(2026, 5, 29)
    assert may_pce.date.weekday() == 4


def test_beige_book_is_wednesday_before_fomc():
    cal = build_calendar(2026)
    # FOMC May 7 → Beige Book Wed ~Apr 22 (Wed) or earlier Wed
    beige = next(e for e in cal if e.category == "Beige"
                 and e.notes.startswith("Pre-FOMC (May 07)"))
    assert beige.date.weekday() == 2
    assert (date(2026, 5, 7) - beige.date).days >= 14


def test_get_upcoming_events_inclusive_of_today():
    # CPI for Apr 2026 falls on 2nd Wed of May = May 13 (Wed).
    # On May 13 itself with days_ahead=0 we should still see it.
    today = date(2026, 5, 13)
    events = get_upcoming_events(today, days_ahead=0)
    assert any(e.category == "CPI" for e in events)


def test_get_upcoming_events_window():
    today = date(2026, 5, 15)
    events = get_upcoming_events(today, days_ahead=7)
    # Window covers May 15-22. Should include Retail Sales (May 15)
    # and Core PCE for Apr (last Fri of May = May 29 → NOT in window)
    for e in events:
        assert today <= e.date <= date(2026, 5, 22)


def test_get_upcoming_events_year_crossover():
    today = date(2026, 12, 28)
    events = get_upcoming_events(today, days_ahead=10)
    # Should pull from both 2026 and 2027 calendars
    years = {e.date.year for e in events}
    assert 2027 in years


def test_format_calendar_block_clear_window():
    # Pick a date with no events in next 0 days
    block = format_calendar_block(date(2026, 5, 16), days_ahead=0)  # Sat
    assert "無重要事件" in block


def test_format_calendar_block_today_marker():
    today = date(2026, 5, 7)  # FOMC May
    block = format_calendar_block(today, days_ahead=0)
    assert "🔴 今日" in block
    assert "FOMC 利率決議" in block


def test_format_calendar_block_tomorrow_marker():
    block = format_calendar_block(date(2026, 5, 6), days_ahead=1)
    assert "🚨 明日" in block


def test_format_calendar_block_high_impact_marker():
    block = format_calendar_block(date(2026, 5, 7), days_ahead=0)
    assert "🔥" in block  # FOMC is high-impact
