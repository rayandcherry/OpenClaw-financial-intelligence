import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    Applies technical indicators to the dataframe using standard pandas.
    """
    if df.empty:
        return df

    # Helper for RSI
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Use EMA for RSI if preferred, but simple rolling is standard in some libs. 
        # For precision with pandas_ta default (Wilder's Smoothing), we use ewm:
        # gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
        # loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
        # Let's stick to simple Wilders-like EMA for consistency with tradingview
        gain = delta.where(delta > 0, 0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = gain / loss
        return 100 - (100 / (1 + rs))

    close = df['Close']

    # Simple Moving Averages
    df['SMA_200'] = close.rolling(window=200).mean()
    df['SMA_50'] = close.rolling(window=50).mean()
    
    # Exponential Moving Averages
    df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
    df['EMA_20'] = close.ewm(span=20, adjust=False).mean()
    
    # RSI (14)
    df['RSI_14'] = calculate_rsi(close, 14)
    
    # Bollinger Bands (20, 2.0)
    # Middle Band = SMA 20
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    
    df['BBL_20_2.0'] = sma20 - (2 * std20) # Lower
    df['BBU_20_2.0'] = sma20 + (2 * std20) # Upper
    
    return df

def check_trinity_setup(row, params):
    """
    Trinity Strategy: Trend Pullback.
    Criteria:
    1. Price > SMA 200 (Long term uptrend)
    2. Price is pulling back to EMA 50 (within range)
    """
    price = row['Close']
    sma200 = row.get('SMA_200')
    ema50 = row.get('EMA_50')
    rsi = row.get('RSI_14')

    if pd.isna(sma200) or pd.isna(ema50):
        return False

    # 1. Trend Filter: Price must be above SMA 200
    is_uptrend = price > sma200

    # 2. Pullback: Price is near EMA 50 (e.g., within 2% above or slightly below)
    # We look for a constructive test of the line
    dist_to_ema = (price - ema50) / ema50
    is_pullback = -0.015 <= dist_to_ema <= 0.03  # Tweakable range

    # 3. RSI Check: Not overbought, not crashing
    is_healthy_rsi = params['rsi_min'] < rsi < params['rsi_max']

    return is_uptrend and is_pullback and is_healthy_rsi

def check_panic_setup(row, params):
    """
    Panic Strategy: Mean Reversion.
    Criteria:
    1. Price < Bollinger Band Lower
    2. RSI < Oversold Threshold (30)
    """
    price = row['Close']
    bbl = row.get('BBL_20_2.0')
    rsi = row.get('RSI_14')

    if pd.isna(bbl) or pd.isna(rsi):
        return False

    is_below_bb = price < bbl
    is_oversold = rsi < params['rsi_oversold']

    return is_below_bb and is_oversold
