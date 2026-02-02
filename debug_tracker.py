import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.tracker.service import TrackerService
from src.tracker.position import PositionManager

def test_manual_flow():
    print("=== Testing Position Logic (Manual) ===")
    
    # scenario: Long BTC at 60k, ATR 2000
    pos = PositionManager("BTC-USD", 60000, 1.0, side="LONG", atr_at_entry=2000, tp1=64000)
    
    print(f"Init SL: {pos.current_sl} (Expected ~56000)")
    
    # 1. Price moves up slightly (61k)
    res = pos.update(61000, 2000)
    print(f"Update 61k: {res['health']} | SL: {res['sl']}")
    
    # 2. Price Hits Breakeven Trigger (Entry + 1.5 ATR = 63000)
    res = pos.update(63100, 2000)
    print(f"Update 63.1k (Breakeven Trigger): {res['health']} | SL: {res['sl']} (Expected > 60000)")
    
    # 3. Price Hits TP1
    res = pos.update(64500, 2000)
    print(f"Update 64.5k (TP1): Action: {res['action']}")
    
    # 4. Price sky rockets to 70k (Trailing Stop should move up)
    # High: 70k. SL should comprise be High - 2ATR = 66k
    res = pos.update(70000, 2000)
    print(f"Update 70k: SL: {res['sl']} (Expected ~66000)")
    
    # 5. Crash to 65k (Should Exit)
    res = pos.update(65000, 2000)
    print(f"Update 65k: Action: {res['action']}")

if __name__ == "__main__":
    test_manual_flow()
