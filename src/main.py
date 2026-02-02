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
        # Pass the full DF for backtesting context
        trinity_result = check_trinity_setup(latest, df)
        panic_result = check_panic_setup(latest, df)
        reversal_result = check_2b_setup(latest, df)
        
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

        elif reversal_result:
            candidates.append({
                "ticker": ticker,
                **reversal_result
            })
            print(f"🔄 FOUND 2B REVERSAL: {ticker}")

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
