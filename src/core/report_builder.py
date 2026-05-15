"""
Programmatic scan report builder. Used by both the CLI (scan.py) and the
Telegram bot (bot/services/report_formatter.py) so both surfaces produce
identical output.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Iterable

try:
    from src.config import PRESET_WATCHLISTS, STRATEGY_EDGE_STATS
    from src.core.fed_calendar import format_calendar_block
except ImportError:
    from config import PRESET_WATCHLISTS, STRATEGY_EDGE_STATS
    from core.fed_calendar import format_calendar_block


TELEGRAM_MAX_LENGTH = 4096
TELEGRAM_SAFE_CHUNK = 3500  # leave headroom for markdown + headers

STRATEGY_DISPLAY = {
    "trinity": "Trinity",
    "panic": "Panic",
    "2b_reversal": "2B",
    "donchian": "Donchian",
}

STRATEGY_EDGE_LABEL = {
    "positive": "✓",
    "negative": "✗",
}


def _normalize_strategy(strategy: str) -> str:
    """Normalize free-form strategy strings to STRATEGY_EDGE_STATS keys."""
    s = (strategy or "").lower().strip()
    if s in ("2b", "2b reversal", "2b_reversal", "2b-reversal"):
        return "2b_reversal"
    return s


def _build_layer_map() -> dict[str, list[str]]:
    """Reverse index of AI presets: ticker -> list of layer names."""
    layer_map: dict[str, list[str]] = defaultdict(list)
    for preset_name, tickers in PRESET_WATCHLISTS.items():
        if not preset_name.startswith("AI "):
            continue
        layer = preset_name.replace("AI ", "")
        for t in tickers:
            layer_map[t].append(layer)
    return dict(layer_map)


_LAYER_MAP = _build_layer_map()


def _layers_for(ticker: str) -> list[str]:
    return _LAYER_MAP.get(ticker, [])


def _signal_side(signal: dict) -> str:
    side = signal.get("side") or signal.get("plan", {}).get("side")
    if side:
        return str(side).upper()
    strategy = _normalize_strategy(signal.get("strategy", ""))
    if strategy == "2b_reversal":
        metrics = signal.get("metrics") or {}
        if "Bearish" in str(metrics.get("type", "")):
            return "SHORT"
    return "LONG"


def classify_signal(signal: dict) -> tuple[str, str | None]:
    """Return (verdict, reason). verdict ∈ {TAKE, WATCH, SKIP}."""
    strategy_key = _normalize_strategy(signal.get("strategy", ""))
    edge = STRATEGY_EDGE_STATS.get(strategy_key, {}).get("edge")
    confidence = signal.get("confidence", 0) or 0
    stats = signal.get("stats") or {}

    if edge == "negative":
        stat = STRATEGY_EDGE_STATS[strategy_key]
        return "SKIP", f"negative-edge strategy (3y ${stat['avg_pnl']}/trade)"

    if stats.get("recent_decay"):
        return "SKIP", "recent decay warning"

    warning = stats.get("warning")
    if warning and "Low Sample" not in str(warning):
        return "SKIP", "strategy warning"

    if confidence < 40:
        return "SKIP", f"low confidence ({confidence})"

    if confidence >= 70:
        return "TAKE", None

    return "WATCH", f"moderate confidence ({confidence})"


def _fmt_news_lines(news_str: str | None, max_items: int = 2) -> list[str]:
    """Parse the news_str produced by core.news.get_market_news into a small
    list of trimmed headline lines with 📰 prefix. Returns [] when news is
    empty, an error placeholder, or unparseable."""
    if not news_str:
        return []
    if news_str.startswith("No recent") or news_str.startswith("Could not"):
        return []
    out: list[str] = []
    for raw in news_str.split("\n"):
        raw = raw.strip()
        if not raw.startswith("- "):
            continue
        # Format from news.py: "- Title: Body". Keep title only — body is noisy.
        text = raw[2:]
        title = text.split(": ", 1)[0]
        title = title[:90].rstrip()
        if title:
            out.append(f"  📰 {title}")
        if len(out) >= max_items:
            break
    return out


def _fmt_track_line(sim_stats: dict | None) -> str:
    """Render the per-ticker 3y mini-backtest stats. Shows raw WR alongside
    a Wilson 95% lower bound — small samples get visibly honest credit
    instead of a misleadingly tight headline number. ROI is dropped because
    single-ticker portfolio ROI is dominated by idle cash."""
    if not sim_stats:
        return ""
    trades = sim_stats.get("trades", 0) or 0
    if trades == 0:
        return ""
    wr = sim_stats.get("wr", 0) or 0
    wr_lb = sim_stats.get("wr_lb")
    if wr_lb is not None and wr_lb > 0:
        return f"  3y track: WR {wr}% (≥{wr_lb}% CI) / {trades} trades"
    return f"  3y track: WR {wr}% / {trades} trades"


def _fmt_signal_line(signal: dict, include_plan: bool) -> str:
    ticker = signal["ticker"]
    strategy_key = _normalize_strategy(signal.get("strategy", ""))
    strategy_name = STRATEGY_DISPLAY.get(strategy_key, strategy_key.title())
    side = _signal_side(signal)
    confidence = signal.get("confidence", "?")
    layers = _layers_for(ticker)
    layer_label = ", ".join(layers) if layers else "—"
    price = signal.get("price")

    header = f"`{ticker}`  {strategy_name} · {side} · conf {confidence} — _{layer_label}_"

    if not include_plan:
        return header

    plan = signal.get("plan") or {}
    sl = plan.get("stop_loss")
    tp = plan.get("take_profit")
    rr = plan.get("risk_reward", "")
    rr_short = rr.split(" ")[0] if rr else ""

    if price is None or sl is None or tp is None:
        return header

    parts = [header, f"  ${price:.2f} → SL ${sl} / TP ${tp}" + (f" ({rr_short})" if rr_short else "")]

    track = _fmt_track_line(signal.get("sim_stats"))
    if track:
        parts.append(track)

    parts.extend(_fmt_news_lines(signal.get("news")))

    return "\n".join(parts)


def _regime_summary(signals: Iterable[dict]) -> str:
    regimes = Counter()
    for s in signals:
        r = (s.get("metrics") or {}).get("regime")
        if r:
            regimes[r] += 1
    if not regimes:
        return "regime n/a"
    if len(regimes) == 1:
        return f"regime {next(iter(regimes)).lower()}"
    parts = [f"{r.lower()}×{n}" for r, n in regimes.most_common()]
    return "regime mixed (" + ", ".join(parts) + ")"


def _strategy_edge_block() -> str:
    lines = ["📊 *Strategy edge*  _(3y AI universe)_"]
    for key, stat in STRATEGY_EDGE_STATS.items():
        name = STRATEGY_DISPLAY.get(key, key)
        mark = STRATEGY_EDGE_LABEL.get(stat["edge"], "·")
        pnl = stat["avg_pnl"]
        pnl_str = f"+${pnl}" if pnl >= 0 else f"-${abs(pnl)}"
        lines.append(
            f"• {name:<8} WR {stat['wr_pct']:.1f}% · {pnl_str}/trade · {mark} {stat['label']}"
        )
    return "\n".join(lines)


def _layer_block(signals: list[dict]) -> str:
    """Group take/watch/skip signals by layer for fast scanning."""
    by_layer: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for s in signals:
        verdict, _ = classify_signal(s)
        layers = _layers_for(s["ticker"]) or ["—"]
        marker = {"TAKE": "", "WATCH": " ⚠️", "SKIP": " ✗"}[verdict]
        for layer in layers:
            by_layer[layer].append((s["ticker"], marker))

    if not by_layer:
        return ""

    lines = ["🏭 *By AI layer*"]
    for layer in sorted(by_layer.keys()):
        entries = ", ".join(f"{t}{m}" for t, m in by_layer[layer])
        lines.append(f"• {layer}: {entries}")
    return "\n".join(lines)


def _signal_block(verdict: str, signals: list[dict]) -> str:
    if not signals:
        return ""
    headers = {
        "TAKE": "🎯 *Take*",
        "WATCH": "👀 *Watch*",
        "SKIP": "⚠️ *Skip*",
    }
    title = f"{headers[verdict]} ({len(signals)})"
    body_lines = [title, ""]
    for s in signals:
        include_plan = verdict == "TAKE"
        body_lines.append(_fmt_signal_line(s, include_plan=include_plan))
        if verdict in ("WATCH", "SKIP"):
            _, reason = classify_signal(s)
            if reason:
                body_lines[-1] += f" — {reason}"
    return "\n".join(body_lines)


def build_report(
    signals: list[dict],
    total_scanned: int,
    scan_date: datetime | None = None,
) -> str:
    """Build a single-string scan report (may exceed Telegram limit; see
    build_report_messages for chunking)."""
    if scan_date is None:
        scan_date = datetime.now(timezone.utc)
    date_str = scan_date.strftime("%b %d, %Y")

    if not signals:
        return (
            f"*OpenClaw AI Scan*  ·  {date_str}\n"
            f"{total_scanned} tickers · 0 signals\n\n"
            f"All quiet on the AI universe today.\n\n"
            f"{_strategy_edge_block()}\n\n"
            f"{format_calendar_block(scan_date.date(), days_ahead=7)}\n\n"
            f"_⚠️ Not financial advice._"
        )

    # Bucket signals by verdict
    buckets: dict[str, list[dict]] = {"TAKE": [], "WATCH": [], "SKIP": []}
    for s in signals:
        verdict, _ = classify_signal(s)
        buckets[verdict].append(s)

    header = (
        f"*OpenClaw AI Scan*  ·  {date_str}\n"
        f"{total_scanned} tickers · {len(signals)} signal"
        f"{'s' if len(signals) != 1 else ''} · {_regime_summary(signals)}"
    )

    parts = [header]
    for verdict in ("TAKE", "WATCH", "SKIP"):
        block = _signal_block(verdict, buckets[verdict])
        if block:
            parts.append(block)

    parts.append(_strategy_edge_block())
    parts.append(format_calendar_block(scan_date.date(), days_ahead=7))
    parts.append(_layer_block(signals))
    parts.append("_⚠️ Not financial advice._")

    return "\n\n".join(p for p in parts if p)


def build_report_messages(
    signals: list[dict],
    total_scanned: int,
    scan_date: datetime | None = None,
) -> list[str]:
    """Return the report split into Telegram-safe chunks."""
    full = build_report(signals, total_scanned, scan_date)
    if len(full) <= TELEGRAM_SAFE_CHUNK:
        return [full]

    # Split on blank lines between sections so each chunk stays parseable.
    sections = full.split("\n\n")
    chunks: list[str] = []
    current = ""
    for section in sections:
        candidate = section if not current else current + "\n\n" + section
        if len(candidate) > TELEGRAM_SAFE_CHUNK and current:
            chunks.append(current)
            current = section
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
