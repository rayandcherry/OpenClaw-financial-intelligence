"""Fed + key macro economic event calendar for proactive heads-up.

Hardcoded sources:
- FOMC 2026 (federalreserve.gov/monetarypolicy/fomccalendars.htm)

Computed (rule-based, ±2d accuracy — verify exact dates at bls.gov before trading):
- Beige Book: Wednesday 2 weeks before FOMC day 2
- CPI: 2nd Wednesday of month
- Core PCE: last Friday of month (BEA Personal Income & Outlays)
- NFP: first Friday of month
- Retail Sales: ~15th of month, snapped to next business day
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


@dataclass(frozen=True)
class FedEvent:
    date: date
    name: str
    category: str   # FOMC | CPI | PCE | NFP | Retail | Beige
    impact: str     # high | medium
    notes: str = ""


# Day 2 of each FOMC meeting = rate decision (14:00 ET) + Powell presser (14:30 ET)
FOMC_2026 = [
    date(2026, 1, 29),
    date(2026, 3, 19),
    date(2026, 5, 7),
    date(2026, 6, 18),
    date(2026, 7, 30),
    date(2026, 9, 17),
    date(2026, 10, 29),
    date(2026, 12, 10),
]


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the n-th occurrence of `weekday` (Mon=0..Sun=6) in (year, month)."""
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(weeks=n - 1)


def _last_weekday_in_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    while end.weekday() != weekday:
        end -= timedelta(days=1)
    return end


def _first_business_day_on_or_after(d: date) -> date:
    while d.weekday() >= 5:  # Sat/Sun
        d += timedelta(days=1)
    return d


def _prior_month_label(year: int, month: int) -> str:
    if month == 1:
        return f"Dec {year - 1}"
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{months[month - 2]} {year}"


def _beige_book_for(fomc_date: date) -> date:
    """Beige Book: Wednesday on or before (FOMC day 2 - 14 days)."""
    target = fomc_date - timedelta(days=14)
    while target.weekday() != 2:  # Wed
        target -= timedelta(days=1)
    return target


def build_calendar(year: int) -> list[FedEvent]:
    """Build the full year's event list, sorted by date."""
    events: list[FedEvent] = []

    if year == 2026:
        for d in FOMC_2026:
            events.append(FedEvent(
                d, "FOMC Rate Decision", "FOMC", "high",
                "14:00 ET decision + 14:30 ET Powell press conf",
            ))
            events.append(FedEvent(
                _beige_book_for(d), "Beige Book", "Beige", "medium",
                f"Pre-FOMC ({d:%b %d})",
            ))

    for month in range(1, 13):
        prior = _prior_month_label(year, month)

        events.append(FedEvent(
            _nth_weekday(year, month, 4, 1),  # 1st Fri
            f"NFP ({prior})", "NFP", "high",
            "8:30 ET — biggest single labor print",
        ))
        events.append(FedEvent(
            _nth_weekday(year, month, 2, 2),  # 2nd Wed
            f"CPI ({prior})", "CPI", "high",
            "8:30 ET — Fed inflation focus",
        ))
        events.append(FedEvent(
            _first_business_day_on_or_after(date(year, month, 15)),
            f"Retail Sales ({prior})", "Retail", "medium",
            "8:30 ET",
        ))
        events.append(FedEvent(
            _last_weekday_in_month(year, month, 4),  # last Fri
            f"Core PCE ({prior})", "PCE", "high",
            "8:30 ET — Fed's preferred inflation gauge",
        ))

    return sorted(events, key=lambda e: e.date)


def get_upcoming_events(today: Optional[date] = None,
                         days_ahead: int = 7) -> list[FedEvent]:
    """Events in [today, today + days_ahead], inclusive."""
    today = today or date.today()
    end = today + timedelta(days=days_ahead)
    cal = build_calendar(today.year)
    if end.year != today.year:
        cal += build_calendar(today.year + 1)
    return [e for e in cal if today <= e.date <= end]


def format_calendar_block(today: Optional[date] = None,
                          days_ahead: int = 7) -> str:
    """Telegram-Markdown-V1 block for the next `days_ahead` days.
    Empty window → 'clear' line. Used by report_builder + standalone CLI."""
    today = today or date.today()
    events = get_upcoming_events(today, days_ahead)

    if not events:
        return f"📅 *Fed Calendar* _(next {days_ahead}d)_: clear"

    lines = [f"📅 *Fed Calendar* _(next {days_ahead}d)_"]
    for e in events:
        delta = (e.date - today).days
        if delta == 0:
            marker = "🔴 TODAY"
        elif delta == 1:
            marker = "🚨 TOMORROW"
        elif delta <= 3:
            marker = f"⚠️ T+{delta}"
        else:
            marker = f"T+{delta}"
        impact = "🔥" if e.impact == "high" else "·"
        lines.append(f"• {marker} {e.date:%a %b %d} {impact} {e.name}")

    return "\n".join(lines)
