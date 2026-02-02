import unittest
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from main import fetch_data, scan_market
from core.news import get_market_news

class TestRealIntegration(unittest.TestCase):
    """
    These tests connect to REAL external APIs.
    They require internet connection and may be slow.
    """

    def test_real_fetch_data_spy(self):
        print("\nTesting Real yfinance Download (SPY)...")
        df = fetch_data("SPY")
        
        self.assertIsNotNone(df, "Failed to download data for SPY")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty, "DataFrame is empty")
        
        # Check basic columns exists
        expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in expected_cols:
            self.assertIn(col, df.columns, f"Missing column {col}")
            
        # Check length (should be ~1 year of trading days, roughly 250)
        self.assertGreater(len(df), 200, f"Not enough data points: {len(df)}")
        print(f"✅ SPY Downloaded: {len(df)} rows")

    def test_real_news_fetch_nvda(self):
        print("\nTesting Real DuckDuckGo Search (NVDA)...")
        news = get_market_news("NVDA stock news", max_results=2)
        
        self.assertIsInstance(news, str)
        self.assertGreater(len(news), 20, "News string is suspiciously short")
        self.assertNotEqual(news, "No recent news found.", "Should have found some news for NVDA")
        print(f"✅ NVDA News Fetched: {len(news)} chars")

    def test_real_scan_market_subset(self):
        print("\nTesting Real Scan Market (AAPL, BTC-USD)...")
        tickers = ['AAPL', 'BTC-USD']
        
        # This runs the full pipeline: Fetch -> Calculate -> Check Strategies
        candidates = scan_market(tickers)
        
        self.assertIsInstance(candidates, list)
        print(f"✅ Scan Complete. Candidates Found: {len(candidates)}")
        if candidates:
            first = candidates[0]
            self.assertIn('ticker', first)
            self.assertIn('strategy', first)
            print(f"   Sample Candidate: {first['ticker']} ({first['strategy']})")

if __name__ == '__main__':
    unittest.main()
