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
    
    # --- 6. Market Regime Classification ---
    # Bull: Price > SMA200 & SMA200 Rising
    # Bear: Price < SMA200 & SMA200 Falling
    # Sideways: Else
    sma200_slope = df['SMA_200'].diff()
    
    conditions = [
        (close > df['SMA_200']) & (sma200_slope > 0),
        (close < df['SMA_200']) & (sma200_slope < 0)
    ]
    choices = ['Bull', 'Bear']
    df['Regime'] = np.select(conditions, choices, default='Sideways')
    
    return df

def backtest_regime_performance(df, strategy_type):
    """
    Advanced Backtester: 
    1. Identifies all past signals based on strategy logic.
    2. Simulates trades with Dynamic ATR SL/TP.
    3. Segregates performance by Market Regime (Bull/Bear/Sideways).
    4. Checks for recent strategy decay (Self-Correction).
    """
    if df.empty:
        return {}

    # 1. Identify Signals
    if strategy_type == 'trinity':
        # Trend Pullback: Price > SMA200, Pullback to EMA50, RSI Healthy
        signals = (df['Close'] > df['SMA_200']) & \
                  ((df['Close'] - df['EMA_50']) / df['EMA_50'] >= -0.015) & \
                  ((df['Close'] - df['EMA_50']) / df['EMA_50'] <= 0.03) & \
                  (df['RSI_14'] >= 35) & (df['RSI_14'] <= 65)
        tp_mult, sl_mult = 2.0, 2.0
        
    elif strategy_type == 'panic':
        # Mean Reversion: Price < BB Low, RSI < 30, High Vol
        signals = (df['Close'] < df['BBL_20_2.0']) & \
                  (df['RSI_14'] < 30) & \
                  (df['RVOL'] > 1.2)
        tp_mult, sl_mult = 3.0, 1.0
    
    signal_indices = df.index[signals].tolist()
    
    # 2. Run Simulation
    results = []
    
    for date_idx in signal_indices:
        idx = df.index.get_loc(date_idx)
        if idx >= len(df) - 1: continue # Skip current candle
        
        entry_row = df.iloc[idx]
        entry_price = entry_row['Close']
        atr = entry_row['ATR_14']
        regime = entry_row['Regime']
        
        if pd.isna(atr): continue

        # Dynamic Exits
        sl = entry_price - (atr * sl_mult)
        tp = entry_price + (atr * tp_mult)
        
        # Check outcome (look forward 20 days max)
        outcome = 'hold'
        future_candles = df.iloc[idx+1 : idx+21]
        
        for _, row in future_candles.iterrows():
            if row['High'] >= tp:
                outcome = 'win'
                break
            if row['Low'] <= sl:
                outcome = 'loss'
                break
        
        # Record trade
        results.append({
            'date': date_idx,
            'regime': regime,
            'outcome': outcome
        })

    # 3. Aggregate Stats
    df_res = pd.DataFrame(results)
    stats = {
        "total": {"wr": 0, "count": 0},
        "bull": {"wr": 0, "count": 0},
        "bear": {"wr": 0, "count": 0},
        "sideways": {"wr": 0, "count": 0},
        "recent_decay": False,
        "warning": None
    }
    
    if df_res.empty:
        return stats

    # Calculate Win Rates Helper
    def calc_wr(d):
        if d.empty: return 0, 0
        wins = len(d[d['outcome'] == 'win'])
        total = len(d[d['outcome'].isin(['win', 'loss'])]) # Exclude 'hold' from denominator
        if total == 0: return 0, 0
        return round((wins / total) * 100, 1), total

    stats['total']['wr'], stats['total']['count'] = calc_wr(df_res)
    stats['bull']['wr'], stats['bull']['count'] = calc_wr(df_res[df_res['regime'] == 'Bull'])
    stats['bear']['wr'], stats['bear']['count'] = calc_wr(df_res[df_res['regime'] == 'Bear'])
    stats['sideways']['wr'], stats['sideways']['count'] = calc_wr(df_res[df_res['regime'] == 'Sideways'])

    # 4. Self-Correction (Recent 14 Days vs Total)
    # Check trades in the last 14 days of data available in the DF
    last_date = df.index[-1]
    recent_cutoff = last_date - pd.Timedelta(days=14)
    recent_trades = df_res[df_res['date'] >= recent_cutoff]
    
    if not recent_trades.empty:
        recent_wr, recent_count = calc_wr(recent_trades)
        # Threshold: If recent WR < 50% of Total WR AND trade count >= 2
        if recent_count >= 2 and recent_wr < (stats['total']['wr'] * 0.5):
            stats['recent_decay'] = True
            stats['warning'] = f"Strategy Failure Warning: Recent win rate ({recent_wr}%) is significantly below historical average ({stats['total']['wr']}%)"

    return stats

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

    # --- REGIME BACKTEST ---
    stats = backtest_regime_performance(df_context, 'trinity') if df_context is not None else {}
    
    # Confidence Score Calc
    confidence = 80 # Base
    if stats.get('recent_decay'): confidence = 20
    if stats.get('total', {}).get('wr', 0) > 60: confidence += 10

    return {
        "strategy": "trinity",
        "price": price,
        "confidence": confidence,
        "metrics": {
            "dist_to_ema": f"{round(dist_to_ema_pct*100, 2)}%",
            "rsi": round(rsi, 1),
            "macd_bullish": bool(macd > macd_signal),
            "regime": row.get('Regime', 'Unknown')
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

    # --- REGIME BACKTEST ---
    stats = backtest_regime_performance(df_context, 'panic') if df_context is not None else {}

    # Confidence Score Calc
    confidence = 75 # Base for Panic (Riskier)
    if stats.get('recent_decay'): confidence = 15 # Severe penalty
    if stats.get('total', {}).get('wr', 0) > 70: confidence += 15 # High reward if history supports

    return {
        "strategy": "panic",
        "price": price,
        "confidence": confidence,
        "metrics": {
            "rsi": round(rsi, 1),
            "rvol": round(rvol, 1),
            "dist_below_bb": f"{round(((bbl - price)/bbl)*100, 1)}%",
            "regime": row.get('Regime', 'Unknown')
        },
        "stats": stats,
        "plan": {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": "1:3 (ATR Based)"
        }
    }
