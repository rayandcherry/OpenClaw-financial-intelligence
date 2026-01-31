from duckduckgo_search import DDGS

def get_market_news(query, max_results=3):
    """
    Fetches recent news for a given ticker or topic using DuckDuckGo.
    Used to filter out fundamental risks (e.g., bankruptcy, lawsuits).
    """
    try:
        results = DDGS().text(query, max_results=max_results)
        news_summary = []
        for r in results:
            news_summary.append(f"- {r['title']}: {r['href']}")
        return "\n".join(news_summary)
    except Exception as e:
        return f"Could not fetch news: {e}"
