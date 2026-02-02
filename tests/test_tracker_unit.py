import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tracker.position import PositionManager
from src.tracker.risk import CapitalAllocator

class TestPositionManager(unittest.TestCase):
    def test_long_lifecycle(self):
        """Test Long: Entry -> Breakeven -> Trailing Stop -> Exit"""
        # Entry: 100, ATR=2. SL=96 (100-2*2)
        pos = PositionManager("TEST", 100, 10, side="LONG", atr_at_entry=2.0)
        self.assertEqual(pos.current_sl, 96.0)
        
        # 1. Price Rise (Not enough for BE)
        # BE Trigger: Entry + 1.5*ATR = 100 + 3 = 103
        pos.update(102.5, 2.0)
        self.assertFalse(pos.is_breakeven_active)
        self.assertEqual(pos.current_sl, 96.0)
        
        # 2. Hit Breakeven Trigger
        res = pos.update(104.0, 2.0)
        self.assertTrue(pos.is_breakeven_active)
        # SL should be moved to slightly above entry (e.g. 100 * 1.001 = 100.1)
        self.assertGreater(pos.current_sl, 100.0)
        self.assertEqual(res['health'], "SAFE (Risk Free)")
        
        # 3. Trailing Stop
        # Price hits 110. SL should be 110 - 2*2 = 106
        res = pos.update(110.0, 2.0)
        self.assertEqual(pos.current_sl, 106.0)
        
        # 4. Pullback (SL shouldn't drop)
        res = pos.update(108.0, 2.0)
        self.assertEqual(pos.current_sl, 106.0) # Maintains 106
        
        # 5. Exit
        res = pos.update(105.0, 2.0)
        self.assertEqual(res['action'], "EXIT_STOP_LOSS")

    def test_ladder_exit(self):
        """Test TP1 Logic"""
        # Entry 100, ATR 2. Default TP1 = 104
        pos = PositionManager("TEST", 100, 10, side="LONG", atr_at_entry=2.0)
        
        # Move price to 103.9
        res = pos.update(103.9, 2.0)
        self.assertFalse(res['tp1_hit'])
        
        # Move price to 104.1
        res = pos.update(104.1, 2.0)
        self.assertTrue(res['tp1_hit'])
        self.assertEqual(res['action'], "SELL_HALF_TP1")
        
        # Maintain TP1 state (no double alert)
        res = pos.update(105.0, 2.0)
        self.assertTrue(res['tp1_hit'])
        self.assertIsNone(res['action'])

class TestCapitalAllocator(unittest.TestCase):
    def setUp(self):
        self.allocator = CapitalAllocator(account_balance=100000, max_risk_per_trade_pct=0.02)
        
    def test_kelly_constrained_by_risk(self):
        """Case: Kelly suggests huge size, but restricted by 2% Max Risk"""
        # WinRate 90%, Reward 2.0 -> Kelly ~85% allocation!
        # But Max Risk is 2k (2% of 100k).
        # Trade: Entry 100, SL 90. Risk/Share = 10.
        # Max Size = 2000 / 10 = 200 shares.
        
        res = self.allocator.calculate_position_size("TEST", 100, 90, win_rate_pct=90)
        
        self.assertEqual(res['constraint'], "Risk Limit")
        self.assertEqual(res['qty'], 200.0)
        self.assertEqual(res['max_loss'], 2000.0)

    def test_kelly_constrained_by_edge(self):
        """Case: Weak edge, Kelly restricts size below Risk limit"""
        # WinRate 55%, Reward 1.0 (1:1). 
        # Kelly = (1*0.55 - 0.45)/1 = 0.10. Half-Kelly = 0.05 (5% allocation)
        # Entry 100, SL 95. Risk/Share = 5.
        # 5% Capital = 5000. Shares = 50.
        # Risk Limit = 2000. Risk of 50 shares = 250. 
        # Wait, if I buy 50 shares, risk is 250. This is < 2000. So Kelly constrains?
        # NO.
        # Let's verify logic. Kelly suggests buying $5000 worth.
        # Risk Limit allows risking $2000. With $5/share risk, that's 400 shares ($40,000 worth).
        # So Kelly (50 shares) < Risk Limit (400 shares).
        # Constraint should be Kelly.
        
        res = self.allocator.calculate_position_size("TEST", 100, 95, win_rate_pct=55, reward_ratio=1.0)
        
        self.assertEqual(res['constraint'], "Kelly Criterion")
        self.assertLess(res['qty'], 100) # Should be around 50

if __name__ == '__main__':
    unittest.main()
