import sys
import os
# Insert src at the beginning of the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from backtest import Backtester
except ImportError:
    # Fallback if run from src directory
    from src.backtest import Backtester

# S&P 500 Top 10 (Approx by Market Cap)
# Note: BRK-B often causes data issues in some APIs, using JPM as 10th if needed, but let's try BRK-B first.
# actually yfinance usually handles BRK-B fine.
TOP_10 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", 
    "META", "TSLA", "BRK-B", "LLY", "AVGO"
]

print(f"🔬 Simulating Top 10 S&P 500 Companies: {TOP_10}")
print("Strategy Focus: TRINITY (Trend Following)")

sim = Backtester(TOP_10, period="3y")
sim.load_data()
sim.run(min_confidence=60) # Set a reasonable confidence floor

print(sim.generate_report())
