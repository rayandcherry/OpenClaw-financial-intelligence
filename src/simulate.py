import sys
import os
import argparse

# Add root to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtest import Backtester, Portfolio
from src.config import US_STOCKS, CRYPTO_ASSETS, SP500_TOP_100

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Paper Trading Simulation")
    parser.add_argument('--mode', type=str, default='US', choices=['US', 'CRYPTO', 'ALL', 'SP100'], help='Asset class to backtest')
    parser.add_argument('--period', type=str, default='3y', help='Data lookback period (e.g. 1y, 2y, 3y)')
    parser.add_argument('--optimize', action='store_true', help='Run optimization loop to find best parameters')
    parser.add_argument('--strategy', type=str, help='Filter for specific strategy (TRINITY, PANIC, 2B)')
    
    parser.add_argument('--ticker', type=str, help='Specific ticker to simulate (overrides mode)')
    
    args = parser.parse_args()
    
    tickers = []
    if args.ticker:
        tickers = [args.ticker]
    elif args.mode == 'US':
        tickers = US_STOCKS
    elif args.mode == 'SP100':
        tickers = SP500_TOP_100
    elif args.mode == 'CRYPTO':
        tickers = CRYPTO_ASSETS
    else:
        tickers = US_STOCKS + CRYPTO_ASSETS
    
    # Filter Strategies
    target_strategies = [args.strategy] if args.strategy else None
    
    print(f"🚀 Starting Simulation for {len(tickers)} tickers over {args.period}...")
    if target_strategies:
        print(f"🎯 Target Strategy: {target_strategies}")
    
    sim = Backtester(tickers, period=args.period)
    sim.load_data()
    
    if args.optimize:
        print("\n🧪 Running Optimization (Testing Confidence Thresholds: 60, 70, 80, 90)...")
        best_roi = -999
        best_conf = 0
        results = []
        
        for conf in [60, 70, 80, 90]:
            print(f"   > Testing Min Confidence: {conf}...")
            # Reset Portfolio for each run
            sim.portfolio = type(sim.portfolio)() 
            sim.run(min_confidence=conf, strategies=target_strategies)
            
            final_equity = sim.portfolio.equity_curve[-1]['equity']
            roi = ((final_equity - sim.portfolio.initial_balance) / sim.portfolio.initial_balance) * 100
            trades = len(sim.portfolio.history)
            
            results.append((conf, roi, trades))
            if roi > best_roi:
                best_roi = roi
                best_conf = conf
                
        print("\n🏆 Optimization Results:")
        for conf, roi, trades in results:
            marker = "  (*)" if conf == best_conf else ""
            print(f"   Confidence {conf}: ROI {roi:.2f}% ({trades} trades){marker}")
            
        print(f"\n✅ Best Parameter: Min Confidence = {best_conf}")
        # Rerun best for report
        sim.portfolio = type(sim.portfolio)()
        sim.run(min_confidence=best_conf, strategies=target_strategies)
        
    else:
        sim.run(min_confidence=70, strategies=target_strategies) # Default
    
    print("\n" + "="*40)
    print(sim.generate_report())
    print("="*40)

if __name__ == "__main__":
    main()
