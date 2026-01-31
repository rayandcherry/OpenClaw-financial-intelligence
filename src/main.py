import os
import sys
import datetime
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# Local Imports
from config import US_STOCKS, CRYPTO_ASSETS, STRATEGY_PARAMS
from core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup
from core.news import get_market_news
from core.llm_client import GeminiClient
from core.notifier import send_telegram_report

# Load Env
load_dotenv()

def fetch_data(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty:
            return None
        # Flatten MultiIndex if present (yfinance update fix)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def scan_market(tickers):
    candidates = []
    
    print(f"🔍 Scanning {len(tickers)} assets...")
    
    for ticker in tickers:
        df = fetch_data(ticker)
        if df is None:
            continue
            
        # Calc Indicators
        df = calculate_indicators(df)
        
        # Get latest row
        latest = df.iloc[-1]
        
        # Check Strategies
        trinity_result = check_trinity_setup(latest)
        panic_result = check_panic_setup(latest)
        
        if trinity_result:
            candidates.append({
                "ticker": ticker,
                **trinity_result
            })
            print(f"✅ FOUND TRINITY: {ticker}")
            
        elif panic_result:
            candidates.append({
                "ticker": ticker,
                **panic_result
            })
            print(f"🚨 FOUND PANIC: {ticker}")

    return candidates

def main():
    # 1. Configuration
    mode = os.getenv("SCAN_MODE", "ALL").upper()
    target_tickers = []
    
    if mode == "US":
        target_tickers = US_STOCKS
    elif mode == "CRYPTO":
        target_tickers = CRYPTO_ASSETS
    else:
        target_tickers = US_STOCKS + CRYPTO_ASSETS

    # 2. Execution
    candidates = scan_market(target_tickers)
    
    if not candidates:
        print("No candidates found matching strategies.")
        return

    # 3. Context & News Gathering
    data_summary = ""
    news_context = ""
    
    print("\n📰 Fetching Context...")
    for c in candidates:
        # Format Technical Data
        metric_str = ", ".join([f"{k}={v}" for k, v in c['metrics'].items()])
        plan_str = f"SL=${c['plan']['stop_loss']}, TP=${c['plan']['take_profit']} ({c['plan']['risk_reward']})"
        
        data_summary += f"- **{c['ticker']}** ({c['strategy'].upper()}): Price ${c['price']:.2f} | {metric_str} | Plan: {plan_str}\n"
        
        # Fetch News (Limit to prevent API bloat)
        news = get_market_news(f"{c['ticker']} stock crypto news", max_results=2)
        news_context += f"**{c['ticker']} News:**\n{news}\n\n"

    # 4. LLM Analysis
    print("🧠 Generating Intelligence Report...")
    try:
        # Load System Prompt
        with open("src/prompts/SOUL.md", "r") as f:
            system_prompt = f.read()
            
        client = GeminiClient()
        report = client.generate_report(data_summary, news_context, system_prompt)
        
        # 5. Delivery
        print("\n📨 Sending Report...")
        send_telegram_report(report)
        
    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except Exception as e:
        print(f"Runtime Error: {e}")

if __name__ == "__main__":
    main()
