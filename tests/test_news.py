import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.news import get_market_news

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

if __name__ == '__main__':
    unittest.main()
