import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup, check_2b_setup

class TestIndicators(unittest.TestCase):
    def setUp(self):
        # Create a mock DataFrame with enough data
        dates = pd.date_range(start='2023-01-01', periods=300)
        self.df = pd.DataFrame({
            'Open': [100.0] * 300,
            'High': [105.0] * 300,
            'Low': [95.0] * 300,
            'Close': [100.0] * 300,
            'Volume': [1000] * 300
        }, index=dates)

    def test_calculate_indicators_adds_columns(self):
        df_calc = calculate_indicators(self.df.copy())
        expected_cols = ['SMA_200', 'EMA_50', 'RSI_14', 'BBL_20_2.0', 'ATR_14', 'MACD']
        for col in expected_cols:
            self.assertIn(col, df_calc.columns)

    def test_trinity_setup_valid(self):
        # Construct a Trinity Setup:
        # 1. Price > SMA200 (UPTREND)
        # 2. Price near EMA50 (PULLBACK)
        # 3. RSI neutral
        
        df = self.df.copy()
        df = calculate_indicators(df) 
        
        latest = df.iloc[-1].copy()
        latest['Close'] = 150.0
        latest['SMA_200'] = 140.0         # Trend OK
        latest['EMA_50'] = 152.0          # Pullback Target
        latest['RSI_14'] = 50.0           # Neutral
        latest['MACD'] = 0.5
        latest['MACD_Signal'] = 0.4       # Bullish MACD
        latest['ATR_14'] = 2.0
        
        # Distance = |150 - 152| / 152 = 1.3% < 3% -> OK
        
        result = check_trinity_setup(latest, df)
        self.assertIsNotNone(result)
        self.assertEqual(result['strategy'], 'trinity')

    def test_trinity_setup_downtrend(self):
        df = self.df.copy()
        df = calculate_indicators(df)
        
        latest = df.iloc[-1].copy()
        latest['Close'] = 90.0
        latest['SMA_200'] = 100.0         # Price < SMA200 -> Downtrend
        latest['EMA_50'] = 95.0
        latest['RSI_14'] = 50.0
        latest['ATR_14'] = 2.0
        
        result = check_trinity_setup(latest, df)
        self.assertIsNone(result)

    def test_panic_setup_valid(self):
        # Panic Setup:
        # 1. Close < Lower BB
        # 2. RSI < 30
        
        df = self.df.copy()
        df = calculate_indicators(df)
        
        latest = df.iloc[-1].copy()
        latest['Close'] = 80.0
        latest['BBL_20_2.0'] = 82.0       # Below BB
        latest['RSI_14'] = 25.0           # Oversold
        latest['RVOL'] = 1.5              # High Volume
        latest['ATR_14'] = 2.0
        
        result = check_panic_setup(latest, df)
        self.assertIsNotNone(result)
        self.assertEqual(result['strategy'], 'panic')

    def test_panic_setup_not_oversold(self):
        df = self.df.copy()
        df = calculate_indicators(df)
        
        latest = df.iloc[-1].copy()
        latest['Close'] = 80.0
        latest['BBL_20_2.0'] = 82.0
        latest['RSI_14'] = 35.0           # Not Oversold
        latest['RVOL'] = 1.5
        latest['ATR_14'] = 2.0
        
        result = check_panic_setup(latest, df)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
