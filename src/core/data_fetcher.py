import yfinance as yf
import pandas as pd

def fetch_data(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False)
        if df.empty:
            return None
        # Flatten MultiIndex if present (yfinance update fix)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Deduplicate columns (fix for yfinance/threading issue returning doubled columns)
        if not df.columns.is_unique:
            df = df.loc[:, ~df.columns.duplicated()]
        
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None
