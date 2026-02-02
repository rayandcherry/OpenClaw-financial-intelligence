import json
import os
from datetime import datetime, timedelta

CACHE_FILE = "data/cache/backtest_stats.json"

class BacktestCache:
    def __init__(self, ttl_days=7):
        self.ttl_days = ttl_days
        self.cache_file = CACHE_FILE
        self.cache = self._load_cache()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

    def _load_cache(self):
        if not os.path.exists(self.cache_file):
            return {}
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self):
        self._ensure_dir()
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save cache: {e}")

    def get(self, ticker, period):
        """Returns cached stats if valid, else None."""
        key = f"{ticker}_{period}"
        entry = self.cache.get(key)
        
        if not entry:
            return None
            
        # Check TTL
        cached_date = datetime.fromisoformat(entry['timestamp'])
        if datetime.now() - cached_date > timedelta(days=self.ttl_days):
            return None # Expired
            
        return entry['stats']

    def set(self, ticker, period, stats):
        """Saves stats to cache."""
        key = f"{ticker}_{period}"
        self.cache[key] = {
            "timestamp": datetime.now().isoformat(),
            "stats": stats
        }
        self._save_cache()
