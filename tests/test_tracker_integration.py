import unittest
import sys
import os
# Add project root and src
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'src'))
import json
import shutil
from src.tracker.service import TrackerService
from src.track import save_positions, load_positions, POSITIONS_FILE

class TestTrackerIntegration(unittest.TestCase):
    def setUp(self):
        """Setup isolated environment"""
        self.test_dir = "tests/data"
        os.makedirs(self.test_dir, exist_ok=True)
        # Override global POSITIONS_FILE for testing
        # Note: Ideally main code should allow config injection.
        # For this test, we might rely on the fact that save/load in track.py 
        # uses a global we can patch or we can just test Service logic + Persistence manually.
        pass

    def test_end_to_end_flow(self):
        """
        Simulates: Add -> Save -> Load -> Update
        """
        # 1. Initialize Service
        service = TrackerService()
        
        # 2. Add Position
        # Entry 50000, 1 BTC, TP1 55000
        service.add_position("BTC-TEST", 50000, 1.0, side="LONG", tp1=55000)
        
        # 3. Simulate Persistence (Save to JSON)
        # We need to temporarily redirect the save path in track.py logic
        # OR just test that service state is serializable.
        # Let's manually invoke save logic similar to track.py
        
        test_file = "tests/data/test_positions.json"
        
        # Save Logic
        data = []
        for ticker, pos in service.positions.items():
            data.append({
                "ticker": ticker,
                "entry_price": pos.entry_price,
                "qty": pos.qty,
                "side": pos.side,
                "tp1": pos.tp1,
                "sl": pos.current_sl,
                "breakeven": pos.is_breakeven_active,
                "tp1_hit": pos.tp1_hit
            })
        with open(test_file, 'w') as f:
            json.dump(data, f)
            
        # 4. Clear Service
        new_service = TrackerService()
        self.assertEqual(len(new_service.positions), 0)
        
        # 5. Load Logic
        with open(test_file, 'r') as f:
            loaded_data = json.load(f)
            for p in loaded_data:
                new_service.add_position(p['ticker'], p['entry_price'], p['qty'], p['side'], p.get('tp1'))
                # Restore Mock State
                pos = new_service.positions[p['ticker']]
                pos.current_sl = p['sl']
                pos.is_breakeven_active = p['breakeven']
        
        # 6. Verify Restoration
        self.assertIn("BTC-TEST", new_service.positions)
        btc_pos = new_service.positions["BTC-TEST"]
        self.assertEqual(btc_pos.entry_price, 50000)
        self.assertEqual(btc_pos.qty, 1.0)
        
        # 7. MARKET UPDATE (Integration with Data Fetcher)
        # This part usually hits the API. We can mock fetch_data or use a MockObject.
        # For "Real" test requested by user, we might want to actually skip mocking 
        # if we want to test API, but that's flaky. 
        # Let's mock the update_market method's data fetching part 
        # or inject a fake fetcher.
        
        # In this integration test, let's trust the logic works if unit tests passed,
        # and focus on the Service orchestration.
        
        # Mocking fetch_data at module level
        import src.tracker.service as service_module
        original_fetch = service_module.fetch_data
        
        # Mock Data Frame
        import pandas as pd
        mock_df = pd.DataFrame({
            'Close': [51000, 52000, 53000], 
            'High': [51500, 52500, 53500],
            'Low': [50500, 51500, 52500],
            'Volume': [100, 100, 100]
        })
        # Calculate Mock ATR (Simplified)
        mock_df['ATR_14'] = 1000.0 
        
        service_module.fetch_data = lambda t, period: mock_df
        
        # Update
        report, alerts = new_service.update_market()
        
        # Verify Report
        self.assertTrue(len(report) > 0)
        self.assertIn("BTC-TEST", report[0])
        self.assertIn("$53000.00", report[0]) # Should pick last close
        
        # Cleanup
        service_module.fetch_data = original_fetch
        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == '__main__':
    unittest.main()
