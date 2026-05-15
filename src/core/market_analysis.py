"""大盤分析 — fetch broad-market gauges and render a Chinese summary block.

Tracks:
- SPY / QQQ / SMH: equity index + AI-relevant ETF
- ^VIX: equity vol gauge
- ^TNX: 10-year Treasury yield (×10 = real yield)
- DX-Y.NYB: DXY dollar index

Renders today's % change + 5d % change, plus a one-line risk sentiment
verdict for the daily brief header.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from src.core.data_fetcher import fetch_data
except ImportError:
    from core.data_fetcher import fetch_data


# Ordered for display in the brief
GAUGES = [
    ("SPY", "SPY", "標普500"),
    ("QQQ", "QQQ", "納指100"),
    ("SMH", "SMH", "半導體"),
    ("^VIX", "VIX", "恐慌指數"),
    ("^TNX", "10Y", "10年期殖利率"),
    ("DX-Y.NYB", "DXY", "美元指數"),
]


@dataclass(frozen=True)
class GaugeReading:
    symbol: str           # yfinance symbol
    display: str          # short display ID
    label: str            # Chinese label
    last: float           # latest close
    chg_pct: float        # today's % change
    chg_5d_pct: float     # 5-day % change


def _read_gauge(symbol: str, display: str, label: str) -> Optional[GaugeReading]:
    """Pull last 10 daily bars; compute today/5d % change. None on fetch fail."""
    df = fetch_data(symbol, period="1mo")
    if df is None or len(df) < 6:
        return None
    closes = df["Close"]
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2])
    chg = (last - prev) / prev * 100 if prev else 0.0
    base_5d = float(closes.iloc[-6])
    chg_5d = (last - base_5d) / base_5d * 100 if base_5d else 0.0
    return GaugeReading(symbol, display, label, last, chg, chg_5d)


def fetch_market_snapshot() -> list[GaugeReading]:
    """Read all gauges; skip any that fail."""
    out: list[GaugeReading] = []
    for sym, disp, lab in GAUGES:
        r = _read_gauge(sym, disp, lab)
        if r is not None:
            out.append(r)
    return out


def sentiment_verdict(readings: list[GaugeReading]) -> str:
    """One-line Chinese risk-sentiment summary."""
    by_disp = {r.display: r for r in readings}
    spy = by_disp.get("SPY")
    qqq = by_disp.get("QQQ")
    vix = by_disp.get("VIX")

    bullish = bearish = 0
    if spy and spy.chg_pct > 0:
        bullish += 1
    elif spy and spy.chg_pct < 0:
        bearish += 1
    if qqq and qqq.chg_pct > 0:
        bullish += 1
    elif qqq and qqq.chg_pct < 0:
        bearish += 1
    if vix:
        if vix.last < 15:
            bullish += 1
        elif vix.last > 22:
            bearish += 1

    if bullish >= 2 and bearish == 0:
        return "情緒：風險偏好 ✓"
    if bearish >= 2 and bullish == 0:
        return "情緒：避險 ⚠️"
    return "情緒：中性"


def _fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _fmt_price(v: float, display: str) -> str:
    """VIX and 10Y are quoted as raw numbers (no $). DXY too."""
    if display in ("VIX", "10Y", "DXY"):
        if display == "10Y":
            # ^TNX is yield × 10; show as %
            return f"{v / 10:.2f}%"
        return f"{v:.2f}"
    return f"${v:.2f}"


def format_market_block(readings: Optional[list[GaugeReading]] = None) -> str:
    """Telegram-Markdown-V1 大盤 block. Empty list → fetch error message."""
    if readings is None:
        readings = fetch_market_snapshot()
    if not readings:
        return "📈 *大盤*: 暫無數據（資料源錯誤）"

    lines = ["📈 *大盤*"]
    for r in readings:
        chg = _fmt_pct(r.chg_pct)
        chg_5d = _fmt_pct(r.chg_5d_pct)
        price = _fmt_price(r.last, r.display)
        lines.append(f"• `{r.display:<3}` {price}  {chg}  _(5日 {chg_5d})_")
    lines.append(sentiment_verdict(readings))
    return "\n".join(lines)
