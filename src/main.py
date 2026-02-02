import os
import sys
import datetime
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# Local Imports
from config import US_STOCKS, CRYPTO_ASSETS, STRATEGY_PARAMS
from core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup, check_2b_setup
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

        # Deduplicate columns (fix for yfinance/threading issue returning doubled columns)
        if not df.columns.is_unique:
            df = df.loc[:, ~df.columns.duplicated()]
        
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

from concurrent.futures import ThreadPoolExecutor, as_completed

def process_ticker(ticker):
    """
    Worker function to process a single ticker.
    Returns a candidate dict if a strategy matches, else None.
    """
    try:
        df = fetch_data(ticker)
        if df is None:
            return None
            
        # Calc Indicators
        df = calculate_indicators(df)
        
        # Get latest row
        latest = df.iloc[-1]
        
        # Check Strategies
        # Pass the full DF for backtesting context
        trinity_result = check_trinity_setup(latest, df)
        panic_result = check_panic_setup(latest, df)
        reversal_result = check_2b_setup(latest, df)
        
        if trinity_result:
            print(f"✅ FOUND TRINITY: {ticker}")
            return {
                "ticker": ticker,
                **trinity_result
            }
            
        elif panic_result:
            print(f"🚨 FOUND PANIC: {ticker}")
            return {
                "ticker": ticker,
                **panic_result
            }

        elif reversal_result:
            print(f"🔄 FOUND 2B REVERSAL: {ticker}")
            return {
                "ticker": ticker,
                **reversal_result
            }
            
        return None

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

def scan_market(tickers):
    candidates = []
    
    print(f"🔍 Scanning {len(tickers)} assets...")
    
    # Use ThreadPoolExecutor for concurrent scanning
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {executor.submit(process_ticker, t): t for t in tickers}
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    candidates.append(result)
            except Exception as exc:
                print(f"{ticker} generated an exception: {exc}")

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
    
    # Language Selection
    lang = os.getenv("REPORT_LANG", "EN").upper()
    lang_prompt = "English" if lang == "EN" else "Traditional Chinese (繁體中文)"
    
    print("\n📰 Fetching Context...")
    for c in candidates:
        # Format Technical Data
        metric_str = ", ".join([f"{k}={v}" for k, v in c['metrics'].items()])
        plan_str = f"SL=${c['plan']['stop_loss']}, TP=${c['plan']['take_profit']} ({c['plan']['risk_reward']})"
        
        # Format Backtest Data
        stats = c['stats']
        backtest_str = (
            f"WR Total: {stats['total']['wr']}% ({stats['total']['count']} trades) | "
            f"Bull: {stats['bull']['wr']}% ({stats['bull']['count']}) | "
            f"Bear: {stats['bear']['wr']}% ({stats['bear']['count']}) | "
            f"Side: {stats['sideways']['wr']}% ({stats['sideways']['count']})"
        )
        
        if stats.get('warning'):
            backtest_str += f"\n⚠️ WARNING: {stats['warning']}"
        
        data_summary += f"- **{c['ticker']}** ({c['strategy'].upper()}): Price ${c['price']:.2f} | Confidence: {c['confidence']} | {metric_str}\n"
        data_summary += f"  - Backtest: {backtest_str}\n"
        data_summary += f"  - Plan: {plan_str}\n"
        
        # Fetch News (Limit to prevent API bloat)
        news = get_market_news(f"{c['ticker']} stock crypto news", max_results=2)
        news_context += f"**{c['ticker']} News:**\n{news}\n\n"

    # 4. LLM Analysis
    print("🧠 Generating Intelligence Report...")
    try:
        # Load System Prompt
        with open("src/prompts/SOUL.md", "r") as f:
            system_prompt = f.read()
            
        # Append Language Instruction
        system_prompt += f"\n\nIMPORTANT: You must output the final report in **{lang_prompt}**."
            
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
