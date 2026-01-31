import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    Applies professional-grade technical indicators.
    Now includes: SMA, EMA, RSI, Bollinger Bands, Volume Profile, MACD, ATR.
    """
    if df.empty:
        return df

    # --- 1. Data Prep ---
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    # --- 2. Trend & Momentum (Existing) ---
    df['SMA_200'] = close.rolling(window=200).mean()
    df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
    
    # RSI Calculation (Wilder's Smoothing)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    # --- 3. Volatility & Panic (Existing + New) ---
    # Bollinger Bands
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    
    df['BBL_20_2.0'] = sma20 - (2 * std20) # Lower
    
    # Volume Spikes
    df['Vol_SMA_20'] = volume.rolling(window=20).mean()
    df['RVOL'] = volume / df['Vol_SMA_20']

    # --- 4. NEW: MACD (Moving Average Convergence Divergence) ---
    # Good for confirming the trend direction alongside RSI
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # --- 5. NEW: ATR (Average True Range) for Dynamic Stops ---
    # Calculate True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # ATR 14 smoothing
    df['ATR_14'] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    return df

def check_trinity_setup(row, params=None) -> dict:
    """
    Trinity Strategy (Updated): Trend Pullback + ATR Risk Management.
    """
    price = row['Close']
    sma200 = row.get('SMA_200')
    ema50 = row.get('EMA_50')
    rsi = row.get('RSI_14')
    macd = row.get('MACD')
    macd_signal = row.get('MACD_Signal')
    atr = row.get('ATR_14')

    if pd.isna(sma200) or pd.isna(ema50) or pd.isna(rsi) or pd.isna(atr):
        return None

    # Logic 1: Trend (Price > SMA200)
    if price <= sma200:
        return None

    # Logic 2: Value (Near EMA50)
    dist_to_ema_pct = (price - ema50) / ema50
    if not (-0.015 <= dist_to_ema_pct <= 0.03):
        return None

    # Logic 3: Momentum (RSI Healthy)
    if not (35 <= rsi <= 65):
        return None

    # --- DYNAMIC RISK MANAGEMENT (The Pro Upgrade) ---
    # Instead of fixed 3%, use 2x ATR. This adapts to the stock's personality.
    stop_loss = round(price - (2.0 * atr), 2)
    
    # Safety Check: Don't let SL be ABOVE SMA200 (Major support)
    stop_loss = min(stop_loss, sma200)
    
    risk = price - stop_loss
    take_profit = round(price + (risk * 2), 2) # 1:2 R/R

    return {
        "strategy": "trinity",
        "price": price,
        "metrics": {
            "dist_to_ema": f"{round(dist_to_ema_pct*100, 2)}%",
            "rsi": round(rsi, 1),
            "macd_bullish": bool(macd > macd_signal)
        },
        "plan": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": "1:2 (ATR Based)"
        }
    }

def check_panic_setup(row, params=None) -> dict:
    """
    Panic Strategy (Updated): Mean Reversion + ATR Targets.
    """
    price = row['Close']
    bbl = row.get('BBL_20_2.0')
    rsi = row.get('RSI_14')
    rvol = row.get('RVOL')
    atr = row.get('ATR_14')

    if pd.isna(bbl) or pd.isna(rsi) or pd.isna(rvol) or pd.isna(atr):
        return None

    # Logic 1: Crash (Below Lower Band)
    if price >= bbl:
        return None

    # Logic 2: Extreme Fear (RSI < 30)
    if rsi >= 30:
        return None

    # Logic 3: Capitulation Volume (RVOL > 1.2) - Filter out "slow bleeds"
    if rvol < 1.2:
        return None

    # --- DYNAMIC RISK MANAGEMENT ---
    # Catching a falling knife requires a TIGHT stop.
    stop_loss = round(price - (1.0 * atr), 2)
    risk = price - stop_loss
    
    # Target is usually the Reversion to Mean (e.g., Price + 3x ATR)
    take_profit = round(price + (3.0 * atr), 2)

    return {
        "strategy": "panic",
        "price": price,
        "metrics": {
            "rsi": round(rsi, 1),
            "rvol": round(rvol, 1),
            "dist_below_bb": f"{round(((bbl - price)/bbl)*100, 1)}%"
        },
        "plan": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": "1:3 (ATR Based)"
        }
    }
