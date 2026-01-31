"""
Configuration for OpenClaw Financial Intelligence.
"""

# Asset Lists
US_STOCKS = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX",
    "JPM", "V", "LLY", "AVGO", "SPY", "QQQ", "IWM", "COIN", "MSTR"
]

CRYPTO_ASSETS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD",
    "AVAX-USD", "DOGE-USD", "DOT-USD", "TRX-USD", "LINK-USD", "MATIC-USD",
    "SHIB-USD", "LTC-USD", "BCH-USD", "UNI-USD", "NEAR-USD", "ATOM-USD",
    "ICP-USD", "FIL-USD", "APT-USD"
]

# Strategy Parameters
STRATEGY_PARAMS = {
    "TRINITY": {
        "sma_trend": 200,    # Trend filter
        "ema_fast": 50,      # Pullback target
        "rsi_period": 14,
        "rsi_min": 40,       # Not oversold yet
        "rsi_max": 60        # Healthy pullback zone
    },
    "PANIC": {
        "bb_length": 20,
        "bb_std": 2.0,
        "rsi_period": 14,
        "rsi_oversold": 30   # Deep value / panic threshold
    }
}
