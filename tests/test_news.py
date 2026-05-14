import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.news import get_market_news, news_query_for_ticker

class TestNews(unittest.TestCase):
    
    @patch('core.news.DDGS')
    def test_get_news_success(self, mock_ddgs_cls):
        # Setup Mock
        mock_instance = mock_ddgs_cls.return_value
        # Mocking .news() instead of .text()
        mock_instance.news.return_value = [
            {'title': 'Good News', 'body': 'Stock goes up', 'url': 'http://good.com'},
            {'title': 'Bad News', 'body': 'Stock goes down', 'url': 'http://bad.com'}
        ]
        
        result = get_market_news("AAPL stock news")
        
        self.assertIn("Good News", result)
        self.assertIn("Stock goes up", result)
        self.assertIn("Bad News", result)
        
    @patch('core.news.DDGS')
    def test_get_news_empty(self, mock_ddgs_cls):
        mock_instance = mock_ddgs_cls.return_value
        mock_instance.news.return_value = []
        
        result = get_market_news("NotExist stock news")
        self.assertEqual(result, "No recent news found.")

class TestNewsQueryForTicker(unittest.TestCase):

    def test_ambiguous_ticker_gets_company_name(self):
        # "ON" alone returns headlines for unrelated companies (e.g. StubHub).
        # Prepending "Onsemi" disambiguates.
        self.assertEqual(news_query_for_ticker("ON"), "Onsemi ON stock news")

    def test_unambiguous_ticker_unchanged(self):
        self.assertEqual(news_query_for_ticker("NVDA"), "NVDA stock news")
        self.assertEqual(news_query_for_ticker("MSFT"), "MSFT stock news")

    def test_lowercase_input_normalized(self):
        self.assertEqual(news_query_for_ticker("on"), "Onsemi ON stock news")
        self.assertEqual(news_query_for_ticker("nvda"), "NVDA stock news")

    def test_covers_known_problem_tickers(self):
        # Sanity: every entry we put in _TICKER_COMPANY_NAMES resolves with
        # disambiguating context (more words than the bare "<sym> stock news").
        for sym in ("AI", "BE", "ET", "NOW", "ARM", "TT", "FN", "SYM", "ON"):
            q = news_query_for_ticker(sym)
            assert sym in q and "stock news" in q
            assert len(q.split()) > 3, f"{sym} should have company name prepended (got {q!r})"


if __name__ == '__main__':
    unittest.main()
