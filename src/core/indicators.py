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

def backtest_performance(df, strategy_type, signal_indices):
    """
    Lightweight backtester to calculate Win Rate for the identified strategy.
    
    Args:
        df: DataFrame with OHLC + ATR
        strategy_type: 'trinity' or 'panic'
        signal_indices: List of index positions where this signal triggered in the past
    
    Returns:
        dict: {win_rate: float, total_trades: int}
    """
    if not signal_indices:
        return {"win_rate": 0.0, "total_trades": 0}

    wins = 0
    losses = 0
    
    # Parameters based on strategy
    tp_mult = 2.0 if strategy_type == 'trinity' else 3.0
    sl_mult = 2.0 if strategy_type == 'trinity' else 1.0
    
    for idx in signal_indices:
        if idx >= len(df) - 1: # Cannot test the most recent candle (it's the current signal)
            continue
            
        entry_price = df['Close'].iloc[idx]
        atr = df['ATR_14'].iloc[idx]
        
        if pd.isna(atr):
            continue

        tp_price = entry_price + (atr * tp_mult)
        sl_price = entry_price - (atr * sl_mult)
        
        # Look forward up to 20 candles
        future_candles = df.iloc[idx+1 : idx+21]
        
        for _, row in future_candles.iterrows():
            if row['High'] >= tp_price:
                wins += 1
                break
            if row['Low'] <= sl_price:
                losses += 1
                break
                
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0.0
    
    return {"win_rate": round(win_rate, 1), "total_trades": total}

def check_trinity_setup(row, df_context=None) -> dict:
    """
    Trinity Strategy (Updated): Trend Pullback + ATR Risk + Backtest.
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

    # --- DYNAMIC RISK MANAGEMENT ---
    stop_loss = round(price - (2.0 * atr), 2)
    stop_loss = min(stop_loss, sma200)
    risk = price - stop_loss
    take_profit = round(price + (risk * 2), 2)

    # --- HISTORICAL BACKTEST (Optional) ---
    stats = {"win_rate": 0, "total_trades": 0}
    if df_context is not None:
        mask = (df_context['Close'] > df_context['SMA_200']) & \
               ((df_context['Close'] - df_context['EMA_50']) / df_context['EMA_50'] >= -0.015) & \
               ((df_context['Close'] - df_context['EMA_50']) / df_context['EMA_50'] <= 0.03) & \
               (df_context['RSI_14'] >= 35) & (df_context['RSI_14'] <= 65)
        
        signal_indices = df_context.index[mask].tolist()
        int_indices = [df_context.index.get_loc(i) for i in signal_indices]
        stats = backtest_performance(df_context, 'trinity', int_indices)

    return {
        "strategy": "trinity",
        "price": price,
        "metrics": {
            "dist_to_ema": f"{round(dist_to_ema_pct*100, 2)}%",
            "rsi": round(rsi, 1),
            "macd_bullish": bool(macd > macd_signal)
        },
        "stats": stats,
        "plan": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": "1:2 (ATR Based)"
        }
    }

def check_panic_setup(row, df_context=None) -> dict:
    """
    Panic Strategy (Updated): Mean Reversion + ATR Targets + Backtest.
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

    # Logic 3: Capitulation Volume (RVOL > 1.2)
    if rvol < 1.2:
        return None

    # --- DYNAMIC RISK MANAGEMENT ---
    stop_loss = round(price - (1.0 * atr), 2)
    take_profit = round(price + (3.0 * atr), 2)

    # --- HISTORICAL BACKTEST (Optional) ---
    stats = {"win_rate": 0, "total_trades": 0}
    if df_context is not None:
        mask = (df_context['Close'] < df_context['BBL_20_2.0']) & \
               (df_context['RSI_14'] < 30) & \
               (df_context['RVOL'] > 1.2)
        
        signal_indices = df_context.index[mask].tolist()
        int_indices = [df_context.index.get_loc(i) for i in signal_indices]
        stats = backtest_performance(df_context, 'panic', int_indices)

    return {
        "strategy": "panic",
        "price": price,
        "metrics": {
            "rsi": round(rsi, 1),
            "rvol": round(rvol, 1),
            "dist_below_bb": f"{round(((bbl - price)/bbl)*100, 1)}%"
        },
        "stats": stats,
        "plan": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": "1:3 (ATR Based)"
        }
    }
