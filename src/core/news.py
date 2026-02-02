from duckduckgo_search import DDGS

def get_market_news(query, max_results=3):
    """
    Fetches recent news for a given ticker or topic using DuckDuckGo.
    Used to filter out fundamental risks (e.g., bankruptcy, lawsuits).
    """
    try:
        # Use .news() as .text() is unreliable/deprecated
        results = DDGS().news(query, max_results=max_results)
        if not results:
            return "No recent news found."
            
        news_summary = []
        for r in results:
            title = r.get('title', 'No Title')
            snippet = r.get('body', r.get('url', ''))
            news_summary.append(f"- {title}: {snippet}")
        return "\n".join(news_summary)
    except Exception as e:
        return f"Could not fetch news: {e}"
