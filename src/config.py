"""
Configuration for OpenClaw Financial Intelligence.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Trading account size — used by tracker sizing (Kelly + VaR cap).
# Override via ACCOUNT_BALANCE env var. Default reflects current personal account.
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "30000"))

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
        "rsi_oversold": 30,  # Deep value / panic threshold
        "rvol_min": 1.2      # Capitulation volume floor
    },
    "2B": {
        "lookback_min": 20,
        "lookback_max": 60,
        "rsi_period": 14,
        "sl_limit_pct": 0.05
    },
    "DONCHIAN": {
        # Classic turtle S2 (55-day breakout). Modernized with:
        #  - uptrend filter (Price > SMA200) to avoid bear-market whipsaws
        #  - volatility expansion filter (ATR > 100-day median) for real breakouts
        # Initial SL is 2 ATR; TP is 4 ATR (1:2 RR). PositionManager's trailing
        # stop takes over after breakeven trigger, so big runners aren't capped.
        "lookback": 55,
        "atr_median_window": 100,
        "sl_atr_mult": 2.0,
        "tp_atr_mult": 4.0,
        "require_uptrend": True,
        "require_vol_expansion": True,
    },
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
    "default_strategies": ["TRINITY", "PANIC", "DONCHIAN"],
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

# Strategy edge stats from 3y AI universe solo backtests. Refreshed
# 2026-05-14 AFTER the SL alignment correctness pass — earlier numbers
# (Trinity 67.6%, Panic 81.0% etc.) were inflated because PositionManager
# silently widened every stop to 3×ATR regardless of strategy design.
# Refreshed numbers honor each strategy's intended SL (Trinity/Donchian
# 2×ATR, Panic 1×ATR). Re-run after material AI_LIST changes via:
#   simulate.py --mode AI --strategy <NAME> --period 3y
# Used by core/report_builder.py to classify signals (TAKE / WATCH / SKIP).
# --- Asset Quality Tiers (sizing concentration caps) ---
# Three-tier classification: A=core mega-cap, B=growth mid-cap, C=speculative.
# Cost cap (% of account) controls "overnight gap through SL" exposure. The
# 2% VaR cap (RISK_PARAMS) still enforces single-trade stop-loss loss.
TIER_COST_CAP_PCT = {
    "A": 0.15,   # $4,500 on a $30k account
    "B": 0.10,   # $3,000
    "C": 0.05,   # $1,500
}

ASSET_TIERS = {
    # --- Tier A: core mega-cap, durable cash flow, multi-year compounders ---
    "NVDA": "A", "MSFT": "A", "GOOGL": "A", "AMZN": "A", "META": "A",
    "AAPL": "A", "TSM": "A", "AVGO": "A",

    # --- Tier B: profitable growth, narrower moat or more cyclical ---
    "AMD": "B", "QCOM": "B", "ORCL": "B", "CRM": "B", "ADBE": "B",
    "CSCO": "B", "ANET": "B", "NOW": "B", "MU": "B",
    "LRCX": "B", "AMAT": "B", "KLAC": "B",
    "HPE": "B", "DELL": "B",
    "MRVL": "B", "ARM": "B",
    "TXN": "B", "ADI": "B",
    "ETN": "B", "EQIX": "B", "DLR": "B",
    "EMR": "B", "CARR": "B", "TT": "B", "JCI": "B", "IRM": "B", "ROK": "B",
    "HUBB": "B",
    "DDOG": "B", "CRWD": "B",
    "INTC": "B",

    # --- Tier C: smaller cap, high beta, unproven cash flow, or speculative ---
    "CRWV": "C", "PLTR": "C", "AI": "C", "SYM": "C",
    "BE": "C", "WOLF": "C", "SMCI": "C",
    "ALAB": "C", "COHR": "C", "LITE": "C", "AAOI": "C", "FN": "C",
    "BELFB": "C", "HPQ": "C",
    "STX": "C", "WDC": "C", "PSTG": "C",
    "KLIC": "C", "TER": "C",
    "MPWR": "C", "MCHP": "C", "ON": "C",
    "NVT": "C", "ZBRA": "C",
    "TTMI": "C", "APH": "C", "TEL": "C",
    "GEV": "C", "VST": "C", "CEG": "C", "VRT": "C",
    "KMI": "C", "WMB": "C", "ET": "C",
    "TSLA": "C",  # single-stock volatility, not a quality knock
}


def tier_for(ticker: str) -> str:
    """Return the tier letter ('A'/'B'/'C') for a ticker, defaulting to 'C'
    for anything outside the curated AI universe (treat unknown as risky)."""
    return ASSET_TIERS.get(ticker.upper(), "C")


def tier_cost_cap(ticker: str, account_balance: float = None) -> float:
    """Return the dollar cost cap for a ticker. If account_balance is None,
    uses ACCOUNT_BALANCE from env."""
    if account_balance is None:
        account_balance = ACCOUNT_BALANCE
    return account_balance * TIER_COST_CAP_PCT[tier_for(ticker)]


STRATEGY_EDGE_STATS = {
    "trinity": {
        "wr_pct": 68.5, "avg_pnl": 164, "trades": 336, "edge": "positive",
        "label": "workhorse",
    },
    "panic": {
        "wr_pct": 42.9, "avg_pnl": 117, "trades": 238, "edge": "positive",
        "label": "high-RR scalp",
    },
    "2b_reversal": {
        "wr_pct": 55.8, "avg_pnl": -44, "trades": 104, "edge": "negative",
        "label": "negative edge",
    },
    "donchian": {
        "wr_pct": 62.1, "avg_pnl": 196, "trades": 311, "edge": "positive",
        "label": "trend breakout",
    },
}
