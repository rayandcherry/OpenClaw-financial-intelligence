import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from main import scan_market, process_ticker

class TestMainIntegration(unittest.TestCase):

    @patch('main.fetch_data')
    @patch('main.calculate_indicators')
    @patch('main.check_trinity_setup')
    def test_process_ticker_trinity_found(self, mock_trinity, mock_calc, mock_fetch):
        # Setup
        mock_fetch.return_value = pd.DataFrame({'Close': [100]})
        mock_calc.return_value = pd.DataFrame({'Close': [100]})
        
        mock_trinity.return_value = {
            'strategy': 'Trinity',
            'price': 100,
            'metrics': {},
            'plan': {'stop_loss': 90, 'take_profit': 120, 'risk_reward': 2.0},
            'stats': {'total': {'wr': 50}}
        }
        
        result = process_ticker("AAPL")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['ticker'], "AAPL")
        self.assertEqual(result['strategy'], "Trinity")
        
    @patch('main.fetch_data')
    def test_process_ticker_fetch_fail(self, mock_fetch):
        mock_fetch.return_value = None
        result = process_ticker("BAD_TICKER")
        self.assertIsNone(result)

    @patch('main.process_ticker')
    def test_scan_market_multithreading(self, mock_process):
        # Simulate 2 hits and 1 miss
        mock_process.side_effect = [
            {'ticker': 'A', 'strategy': 'Trinity'},
            None,
            {'ticker': 'C', 'strategy': 'Panic'}
        ]
        
        tickers = ['A', 'B', 'C']
        results = scan_market(tickers)
        
        self.assertEqual(len(results), 2)
        found_tickers = sorted([r['ticker'] for r in results])
        self.assertEqual(found_tickers, ['A', 'C'])

if __name__ == '__main__':
    unittest.main()
