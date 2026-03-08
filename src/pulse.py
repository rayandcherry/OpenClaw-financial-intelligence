import os
import sys
from dotenv import load_dotenv
import pandas as pd

# Local Imports
from core.data_fetcher import fetch_data
from core.scanner import scan_market
from core.indicators import calculate_indicators
from core.news import get_market_news
from backtest import Backtester

load_dotenv()

def analyze_ticker(ticker):
    print(f"\n🔍 Analyzing {ticker}...")
    
    # 1. Technical Analysis
    df = fetch_data(ticker, period="1y")
    if df is None:
        print("Data fetch failed.")
        return
        
    df = calculate_indicators(df)
    current = df.iloc[-1]
    
    tech_summary = f"""
    Price: ${current['Close']:.2f}
    RSI: {current['RSI_14']:.1f}
    SMA200: ${current['SMA_200']:.2f} ({'BULL' if current['Close'] > current['SMA_200'] else 'BEAR'})
    ATR: {current['ATR_14']:.2f}
    Regime: {current.get('Regime', 'N/A')}
    """
    
    # 2. Simulation (Quant)
    bt = Backtester([ticker], period="3y")
    bt.load_data()
    bt.run(min_confidence=0) # Run all signals found
    stats = bt.get_summary_metrics()
    
    quant_summary = f"""
    3y Backtest ROI: {stats['roi']}%
    Win Rate: {stats['wr']}%
    Total Trades: {stats['trades']}
    """
    
    # 3. News (Sentiment)
    news = get_market_news(f"{ticker} market news", max_results=3)
    
    print("\n=== 1. TECHNICAL ANALYSIS ===")
    print(tech_summary)
    
    print("\n=== 2. QUANT ANALYSIS (3y Simulation) ===")
    print(quant_summary)
    
    print("\n=== 3. SENTIMENT ANALYSIS (News) ===")
    print(news)

if __name__ == "__main__":
    analyze_ticker("SPY")
    analyze_ticker("BTC-USD")
