"""
Configuration for OpenClaw Financial Intelligence.
"""

# Asset Lists

CRYPTO_ASSETS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD",
    "AVAX-USD", "DOGE-USD", "DOT-USD", "TRX-USD", "LINK-USD", "MATIC-USD",
    "SHIB-USD", "LTC-USD", "BCH-USD", "UNI-USD", "NEAR-USD", "ATOM-USD",
    "ICP-USD", "FIL-USD", "APT-USD"
]

# US AI Industry Chain (curated). Deduped union of all layered presets below.
# Used by `--mode AI` in scan.py / simulate.py / mcp_server.py.
AI_LIST = [
    # Platforms / SaaS / AI services
    "MSFT", "GOOGL", "AMZN", "META", "AAPL", "CRM", "ADBE", "PLTR",
    "SNOW", "ORCL", "NOW", "AI", "DDOG", "CRWD",
    # Datacenter infrastructure (REIT + GPU cloud)
    "EQIX", "DLR", "IRM", "CRWV",
    # Silicon (GPU / ASIC / CPU / Memory + foundry ADR)
    "NVDA", "AMD", "INTC", "QCOM", "AVGO", "MRVL", "ARM",
    "MU", "WDC", "STX", "PSTG", "TSM",
    # Semi equipment
    "AMAT", "LRCX", "KLAC", "TER", "KLIC",
    # Networking (switch + optical + high-speed interconnect)
    # JNPR removed — Juniper Networks acquired by HPE (2025), delisted.
    "ANET", "CSCO", "ALAB", "COHR", "LITE", "AAOI", "FN",
    # Server / OEM / ODM
    "SMCI", "DELL", "HPE", "BELFB", "HPQ",
    # Power (grid + generation + gas pipelines)
    "ETN", "VRT", "HUBB", "EMR", "ROK",
    "CEG", "VST", "GEV", "BE", "ET", "KMI", "WMB",
    # Cooling / thermal (VRT shared with Power)
    "NVT", "CARR", "TT", "JCI",
    # Analog / Power IC / PCB / Connectors
    "MPWR", "TXN", "ADI", "ON", "MCHP", "WOLF",
    "TTMI", "APH", "TEL",
    # Physical AI / Robotics (ROK shared with Power)
    "TSLA", "SYM", "ZBRA",
]

# US scan universe — aliased to AI_LIST. The original mixed list
# (banks/drugs/index ETFs/crypto proxies) was retired in favor of the curated
# AI industry chain. `--mode US` and `--mode AI` are now equivalent.
US_STOCKS = AI_LIST

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
    "SNPS", "LMT", "SBUX", "AMT", "MU", "MDLZ", "MO", "SO", "INTC",
    "EOG", "CVS", "ZTS", "PYPL", "DUK", "SLB", "TGT", "BDX", "ITW",
    "CSX", "CL", "NOC", "ICE", "HUM", "WM", "CME", "ORCL", "FCX",
    "PH", "MCK", "PSA", "USB", "EMR", "PNC", "APH", "GIS", "MAR", "AON",
    "MCO", "ECL", "FDX", "HCA", "NXPI", "RSG", "MSI", "AJG", "COF", "ROP",
    "CARR", "PSX", "AEP", "PCAR", "D", "MNST", "OXY", "DXCM", "SRE", "TRV",
    "MET", "AIG", "GD", "ROST", "CTAS", "WMB", "JCI", "FIS", "EXC", "KMB",
    "STZ", "LULU", "TRGP", "PAYX", "IDXX", "KMI", "DOW", "CTVA", "YUM", "OTIS",
    "ALB", "EA", "PRU", "BIIB", "ED", "XEL", "MTD", "PEG", "FAST", "WELL",
    "VLO", "PCG", "AMP", "AME", "ILMN", "DLTR", "CSGP", "ANET", "VRSK", "CPRT"
]

# Alias used by simulate.py --mode SP100 (top 100 subset).
SP500_TOP_100 = SP500_TOP_200[:100]

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

# --- Bot Configuration ---
BOT_CONFIG = {
    "watchlist_max": 50,
    "rate_limit_scans_per_hour": 10,
    "scan_lock_ttl_seconds": 300,
    "backtest_cache_ttl_days": 7,
    "default_schedule_times": ["08:00", "20:00"],
    "default_lang": "EN",
    "default_scan_mode": "US",
    "default_strategies": ["TRINITY", "PANIC"],
}

PRESET_WATCHLISTS = {
    "SP500 Top 20": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "UNH", "XOM", "JNJ",
                      "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "LLY", "PEP"],
    "FAANG+": ["META", "AAPL", "AMZN", "NVDA", "GOOGL", "MSFT", "TSLA", "NFLX"],

    # --- AI Industry Chain (layered) ---
    "AI Platforms": ["MSFT", "GOOGL", "AMZN", "META", "AAPL", "CRM", "ADBE",
                      "PLTR", "SNOW", "ORCL", "NOW", "AI", "DDOG", "CRWD"],
    "AI Infrastructure": ["EQIX", "DLR", "IRM", "CRWV"],
    "AI Silicon": ["NVDA", "AMD", "INTC", "QCOM", "AVGO", "MRVL", "ARM",
                    "MU", "WDC", "STX", "PSTG", "TSM"],
    "AI Semi Equipment": ["AMAT", "LRCX", "KLAC", "TER", "KLIC"],
    "AI Networking": ["ANET", "CSCO", "AVGO", "MRVL", "ALAB",
                       "COHR", "LITE", "AAOI", "FN"],
    "AI Server": ["SMCI", "DELL", "HPE", "BELFB", "HPQ"],
    "AI Power": ["ETN", "VRT", "HUBB", "EMR", "ROK", "CEG", "VST", "GEV",
                  "BE", "ET", "KMI", "WMB"],
    "AI Cooling": ["VRT", "NVT", "CARR", "TT", "JCI"],
    "AI Analog/Interconnect": ["MPWR", "TXN", "ADI", "ON", "MCHP", "WOLF",
                                "TTMI", "APH", "TEL"],
    "AI Robotics": ["TSLA", "SYM", "ROK", "ZBRA"],
}

# Strategy edge stats from 3y AI universe portfolio backtest. Refreshed
# 2026-05-13. Update when AI_LIST changes materially or quarterly. Used by
# core/report_builder.py to classify signals (TAKE / WATCH / SKIP).
STRATEGY_EDGE_STATS = {
    "trinity": {
        "wr_pct": 67.6, "avg_pnl": 186, "trades": 296, "edge": "positive",
        "label": "workhorse",
    },
    "panic": {
        "wr_pct": 81.0, "avg_pnl": 469, "trades": 63, "edge": "positive",
        "label": "rare but huge",
    },
    "2b_reversal": {
        "wr_pct": 55.8, "avg_pnl": -44, "trades": 104, "edge": "negative",
        "label": "negative edge",
    },
}
