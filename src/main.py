import os
import sys
import datetime
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
        is_trinity = check_trinity_setup(latest, STRATEGY_PARAMS['TRINITY'])
        is_panic = check_panic_setup(latest, STRATEGY_PARAMS['PANIC'])
        
        if is_trinity:
            candidates.append({
                "ticker": ticker,
                "strategy": "TRINITY",
                "price": latest['Close'],
                "rsi": latest['RSI_14'],
                "bb_lower": latest['BBL_20_2.0'],
                "sma200": latest['SMA_200'],
                "ema50": latest['EMA_50']
            })
            print(f"✅ FOUND TRINITY: {ticker}")
            
        elif is_panic:
            candidates.append({
                "ticker": ticker,
                "strategy": "PANIC",
                "price": latest['Close'],
                "rsi": latest['RSI_14'],
                "bb_lower": latest['BBL_20_2.0']
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
        data_summary += f"- **{c['ticker']}** ({c['strategy']}): Price ${c['price']:.2f}, RSI {c['rsi']:.2f}\n"
        
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
