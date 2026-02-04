import yfinance as yf
import pandas as pd
import os

import requests
import io

def get_sp500_tickers():
    """Fetches the current S&P 500 tickers from Wikipedia."""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        tables = pd.read_html(io.StringIO(response.text))
        df = tables[0]
        tickers = df['Symbol'].tolist()
        # Clean tickers (e.g. BRK.B -> BRK-B)
        tickers = [t.replace('.', '-') for t in tickers]
        print(f"Loaded {len(tickers)} SP500 tickers from Wikipedia.")
        return tickers
    except Exception as e:
        print(f"Error fetching SP500 list: {e}")
        return []

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
