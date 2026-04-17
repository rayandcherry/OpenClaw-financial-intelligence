import re
from datetime import datetime, timedelta, timezone

try:
    from ddgs import DDGS
except ImportError:  # fallback for old envs still on the renamed package
    from duckduckgo_search import DDGS

# Strip characters that could break out of a fenced context or carry
# instruction-like content into the LLM prompt.
_SANITIZE_RE = re.compile(r'[`\r\n]+')

# Freshness: drop anything older than this when we can parse a date.
_MAX_AGE_DAYS = 14


def _sanitize(text: str) -> str:
    """Single-line, no-backticks — defensive against prompt injection via news."""
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
