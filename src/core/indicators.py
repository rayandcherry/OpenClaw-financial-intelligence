import pandas as pd
import pandas_ta as ta

def calculate_indicators(df):
    """
    Applies technical indicators to the dataframe using pandas_ta.
    """
    if df.empty:
        return df

    # Simple Moving Averages
    df.ta.sma(length=200, append=True)
    df.ta.sma(length=50, append=True)
    
    # Exponential Moving Averages
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=20, append=True)
    
    # RSI
    df.ta.rsi(length=14, append=True)
    
    # Bollinger Bands
    df.ta.bbands(length=20, std=2.0, append=True)
    
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
