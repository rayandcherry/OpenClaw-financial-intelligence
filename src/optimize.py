import sys
import os
import itertools
import pandas as pd
import yfinance as yf

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtest import Backtester
from src.config import RISK_PARAMS, STRATEGY_PARAMS
from src.core.data_fetcher import get_sp500_tickers

def fetch_benchmark(period='1y'):
    print(f"📊 Fetching SPY benchmark for {period}...")
    spy = yf.download("SPY", period=period, progress=False)
    if spy.empty:
        return 0.0
    
    if isinstance(spy.columns, pd.MultiIndex):
        spy = spy.xs('SPY', axis=1, level=1, drop_level=False) 
        # Safe way:
        close_col = spy['Close']
        if isinstance(close_col, pd.DataFrame):
             close_col = close_col.iloc[:, 0] # Take first column if multiple
        
        start_price = float(close_col.iloc[0])
        end_price = float(close_col.iloc[-1])
    else:
        start_price = float(spy.iloc[0]['Close'])
        end_price = float(spy.iloc[-1]['Close'])

    roi = ((end_price - start_price) / start_price) * 100
    print(f"📉 SPY ROI: {roi:.2f}%")
    return roi

def optimize():
    print("🚀 Starting SP500 Optimization Loop...")
    
    # 1. Fetch SP500 Data
    tickers = get_sp500_tickers()
    if not tickers:
        print("Failed to fetch SP500. Falling back to Config top 200.")
        from src.config import SP500_TOP_200
        tickers = SP500_TOP_200
        
    print(f"Testing on {len(tickers)} tickers.")
    
    tester = Backtester(tickers, period="1y") 
    tester.load_data() # Cache data
    
    benchmark_roi = fetch_benchmark("1y")
    
    # 2. Define Parameter Grid (Trinity Win Rate Focus)
    # Constraints: Size 10-30%
    # To achieve ~20% size with ~5% stop distance (typical for 2-3 ATR), Risk % should be ~1.0-1.5%
    
    # We will vary SAFETY parameters to boost Win Rate
    # Higher Win Rate usually comes from:
    # 1. Wider Initial Stop (Give it room to breathe) -> initial_sl_atr: 3.0
    # 2. Stricter Entry (Only best setups) -> RSI 40-60
    
    # 2. Define Parameter Grid (SP500 Scale)
    
    base_risk = {
        "risk_per_trade": 0.015,   
        "max_position_size": 0.20, # 20% Max (5 positions) to allow decent diversification
        "initial_sl_atr": 3.0,     # Wide stop is good
        "breakeven_trigger_atr": 1.5,
        "trailing_stop_atr": 2.5
    }
    
    profiles = [
        {
            "name": "SP500: High Precision (Current Best)",
            "risk": base_risk,
            "trinity": {
                "rsi_min": 40, 
                "rsi_max": 60
            }
        },
        {
            "name": "SP500: Balanced (More Volume)",
            "risk": base_risk,
            "trinity": {
                "rsi_min": 35, 
                "rsi_max": 65
            }
        }
    ]
    
    best_roi = -999
    best_profile = None
    
    print(f"\n🧪 Testing {len(profiles)} Configurations on {len(tickers)} tickers...")
    
    for p in profiles:
        print(f"\n👉 Running Profile: {p['name']}")
        
        # Reset Portfolio
        tester.portfolio = type(tester.portfolio)()
        
        # Run Backtest
        strat_params = {"TRINITY": p['trinity']}
        tester.run(min_confidence=60, strategies=["TRINITY"], strategy_params=strat_params, risk_params=p['risk'])
        
        # Stats
        stats = tester.get_summary_metrics()
        print(f"   [Result] ROI: {stats['roi']}% | WR: {stats['wr']}% | Trades: {stats['trades']} | PnL: ${stats['pnl']}")
        
        if stats['roi'] > best_roi:
            best_roi = stats['roi']
            best_profile = p
            
    print("\n" + "="*40)
    print(f"🏆 Optimization Winner: {best_profile['name']}")
    print(f"📈 Best ROI: {best_roi:.2f}% (vs SPY {benchmark_roi:.2f}%)")
    
    if best_roi > benchmark_roi:
        print("✅ SUCCESS: Strategy beats benchmark.")
        print("To apply, update src/config.py with these params:")
        print(best_profile)
    else:
        print("❌ FAILURE: Strategy underperformed benchmark.")
        
if __name__ == "__main__":
    optimize()
