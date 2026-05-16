import re
from datetime import datetime, timedelta, timezone

try:
    from ddgs import DDGS
except ImportError:  # fallback for old envs still on the renamed package
    from duckduckgo_search import DDGS

# Strip backticks/newlines so headlines render cleanly inside Telegram-MD.
_SANITIZE_RE = re.compile(r'[`\r\n]+')

# Freshness: drop anything older than this when we can parse a date.
_MAX_AGE_DAYS = 14

# Tickers whose symbol alone is ambiguous to news engines (common words,
# prepositions, very short two-letter codes). For these, prepend the company
# name so DDG/Bing surface the right entity. Caught after a scan returned
# StubHub/News Corp headlines for ticker "ON" (Onsemi).
# Extend when adding word-like symbols to AI_LIST.
_TICKER_COMPANY_NAMES = {
    "AI": "C3.ai",
    "ARM": "Arm Holdings",
    "BE": "Bloom Energy",
    "ET": "Energy Transfer",
    "FN": "Fabrinet",
    "NOW": "ServiceNow",
    "ON": "Onsemi",
    "SYM": "Symbotic",
    "TT": "Trane Technologies",
}


def news_query_for_ticker(ticker: str) -> str:
    """Build a disambiguated news search query for a ticker symbol.

    For word-like or ambiguous tickers (see _TICKER_COMPANY_NAMES), prepend the
    company name so search engines surface the right entity. Falls back to a
    plain "<TICKER> stock news" query for unambiguous symbols.
    """
    sym = (ticker or "").upper().strip()
    name = _TICKER_COMPANY_NAMES.get(sym)
    if name:
        return f"{name} {sym} stock news"
    return f"{sym} stock news"


def _sanitize(text: str) -> str:
    """Single-line, no-backticks — keeps headlines safe inside Telegram-MD."""
    if not text:
        return ""
    flat = _SANITIZE_RE.sub(' ', str(text))
    return flat.strip()[:400]


def _is_fresh(raw_date) -> bool:
    """Return True if date is unknown (can't filter) or within _MAX_AGE_DAYS."""
    if not raw_date:
        return True
    try:
        if isinstance(raw_date, str):
            # DDG returns ISO-8601 like "2026-04-10T12:34:56"
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
        elif isinstance(raw_date, (int, float)):
            dt = datetime.fromtimestamp(raw_date, tz=timezone.utc)
        else:
            return True
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(days=_MAX_AGE_DAYS)
    except (ValueError, TypeError):
        return True


def format_news_lines(news_str, max_items=2, prefix="  📰 ", title_max_len=90):
    """Turn the raw string from get_market_news() into a small list of trimmed
    headline lines suitable for the daily report / monitor.

    Returns [] when the string is empty, an error placeholder, or unparseable.
    Body text is discarded — only the title before the first ": " is kept.
    """
    if not news_str:
        return []
    if news_str.startswith("No recent") or news_str.startswith("Could not"):
        return []
    out = []
    for raw in news_str.split("\n"):
        raw = raw.strip()
        if not raw.startswith("- "):
            continue
        text = raw[2:]
        title = text.split(": ", 1)[0]
        title = title[:title_max_len].rstrip()
        if title:
            out.append(f"{prefix}{title}")
        if len(out) >= max_items:
            break
    return out


def get_market_news(query, max_results=3):
    """
    Fetches recent news for a given ticker or topic using DuckDuckGo.
    Used to filter out fundamental risks (e.g., bankruptcy, lawsuits).

    Applies client-side freshness filter (<= _MAX_AGE_DAYS old) to avoid
    stale context being mislabelled as "recent news". DDG server-side
    timelimit filtering is avoided because it triggers 403s.
    """
    try:
        # Over-fetch so the freshness filter still yields max_results.
        results = DDGS().news(query, max_results=max_results * 3)
        if not results:
            return "No recent news found."

        news_summary = []
        for r in results:
            if not _is_fresh(r.get('date')):
                continue
            title = _sanitize(r.get('title', 'No Title'))
            snippet = _sanitize(r.get('body', r.get('url', '')))
            news_summary.append(f"- {title}: {snippet}")
            if len(news_summary) >= max_results:
                break

        if not news_summary:
            return "No recent news found."
        return "\n".join(news_summary)
    except Exception as e:
        return f"Could not fetch news: {e}"
