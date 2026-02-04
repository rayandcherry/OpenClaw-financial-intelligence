"""
Configuration for OpenClaw Financial Intelligence.
"""

# Asset Lists
# Top 200 US Stocks by Market Cap (Approx)
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

SP500_TOP_200 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "LLY", "AVGO",
    "JPM", "XOM", "UNH", "V", "PG", "MA", "COST", "JNJ", "HD", "MRK",
    "ABBV", "CVX", "CRM", "BAC", "WMT", "KO", "NFLX", "ACN", "PEP", "LIN",
    "TMO", "MCD", "DIS", "AMD", "ADBE", "CSCO", "ABT", "QCOM", "INTU", "CAT",
    "IBM", "GE", "VZ", "CMCSA", "DHR", "NOW", "AXP", "UBER", "TXN", "AMGN",
    "PFE", "PM", "BX", "NEE", "GS", "SPGI", "ISRG", "UNP", "MS", "HON",
    "RTX", "LOW", "COP", "BKNG", "T", "ELV", "SYK", "TJX", "PGR", "LRCX",
    "BLK", "ETN", "BSX", "VRTX", "C", "REGN", "ADI", "SCHW", "PLD", "MMC",
    "CB", "ADP", "MDT", "PANW", "FI", "CI", "KLAC", "GILD", "BMY", "DE",
    "SNPS", "LMT", "SBUX", "AMT", "MU", "MDLZ", "MO", "SO", "ADP", "INTC",
    "EOG", "CVS", "ZTS", "PYPL", "GTE", "DUK", "SLB", "TGT", "BDX", "ITW",
    "CSX", "CL", "NOC", "ATVI", "ICE", "HUM", "WM", "CME", "ORCL", "FCX",
    "PH", "MCK", "PSA", "USB", "EMR", "PNC", "APH", "GENERAL", "MAR", "AON",
    "MCO", "ECL", "FDX", "HCA", "NXPI", "RSG", "MSI", "AJG", "COF", "ROP",
    "CARR", "PSX", "AEP", "PCAR", "D", "MNST", "OXI", "DXCM", "SRE", "TRV",
    "MET", "AIG", "GD", "ROST", "CTAS", "WMB", "JCI", "FIS", "EXC", "KMB",
    "STZ", "LULU", "TRGP", "PAYX", "IDXX", "KMI", "DOW", "CTVA", "YUM", "OTIS",
    "ALB", "EA", "PRU", "BIIB", "ED", "XEL", "MTD", "PEG", "FAST", "WELL",
    "VLO", "PCG", "AMP", "AME", "ILMN", "DLTR", "CSGP", "ANET", "VRSK", "CPRT"
]

# Risk Management Parameters (Dynamic Exits)
RISK_PARAMS = {
    "initial_sl_atr": 3.0,       # Optimized: Wide stop (was 2.0)
    "breakeven_trigger_atr": 1.5, # Profit level to move SL to Breakeven
    "trailing_stop_atr": 2.0,    # Trailing Stop distance
    "tp1_atr": 2.0               # Default TP1/Ladder Exit distance
}

# Strategy Parameters
STRATEGY_PARAMS = {
    "TRINITY": {
        "sma_trend": 200,    # Trend filter
        "ema_fast": 50,      # Pullback target
        "rsi_period": 14,
        "rsi_min": 40,       # Optimized: Stricter entry (was 35)
        "rsi_max": 60        # Optimized: Stricter entry (was 65)
    },
    "PANIC": {
        "bb_length": 20,
        "bb_std": 2.0,
        "rsi_period": 14,
        "rsi_oversold": 30   # Deep value / panic threshold
    },
    "2B": {
        "lookback_min": 20,
        "lookback_max": 60,
        "rsi_period": 14,
        "sl_limit_pct": 0.05
    }
}
