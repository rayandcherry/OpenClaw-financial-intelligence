import argparse
import os
import sys
from dotenv import load_dotenv

# Local Imports
from config import US_STOCKS, CRYPTO_ASSETS
from core.scanner import scan_market
from core.news import get_market_news
from core.llm_client import GeminiClient
from core.notifier import send_telegram_report
from backtest import Backtester
from core.cache_manager import BacktestCache

# Load Env
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Real-Time Scanner")
    parser.add_argument('--ticker', type=str, help='Specific ticker to scan (overrides mode)')
    parser.add_argument('--mode', type=str, choices=['US', 'CRYPTO', 'ALL'], help='Asset class to scan')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format (Agent Mode)')
    
    args = parser.parse_args()

    # 1. Configuration
    # CLI arg > Env Var > Default
    mode = args.mode if args.mode else os.getenv("SCAN_MODE", "ALL").upper()
    
    target_tickers = []
    
    if args.ticker:
        target_tickers = [args.ticker]
    elif mode == "US":
        target_tickers = US_STOCKS
    elif mode == "CRYPTO":
        target_tickers = CRYPTO_ASSETS
    else:
        target_tickers = US_STOCKS + CRYPTO_ASSETS

    # 2. Execution
    candidates = scan_market(target_tickers)
    
    if not candidates:
        if args.json:
            import json
            print(json.dumps({"status": "ok", "candidates": []}))
        else:
            print("No candidates found matching strategies.")
        return

    # 3. Context & Enrichment
    data_summary = ""
    news_context = ""
    
    print("\n📰 Fetching Context...")
    for c in candidates:
        # Format Technical Data
        metric_str = ", ".join([f"{k}={v}" for k, v in c['metrics'].items()])
        plan_str = f"SL=${c['plan']['stop_loss']}, TP=${c['plan']['take_profit']} ({c['plan']['risk_reward']})"
        
        # Format Backtest Data
        stats = c['stats']
        backtest_str = (
            f"WR Total: {stats['total']['wr']}% | "
            f"Bull: {stats['bull']['wr']}% | "
            f"Bear: {stats['bear']['wr']}%"
        )
        
        data_summary += f"- **{c['ticker']}** ({c['strategy'].upper()}): Price ${c['price']:.2f} | Confidence: {c['confidence']} | {metric_str}\n"
        data_summary += f"  - Backtest: {backtest_str}\n"
        
        # Regression Simulation
        print(f"🔄 Running Regression Sim for {c['ticker']}...")
        cache = BacktestCache()
        sim_stats = cache.get(c['ticker'], "3y")
        
        from_cache = False
        if sim_stats:
            print(f"⚡ Cache Hit for {c['ticker']}")
            from_cache = True
        else:
            bt = Backtester([c['ticker']], period="3y")
            bt.load_data()
            bt.run(min_confidence=60)
            sim_stats = bt.get_summary_metrics()
            cache.set(c['ticker'], "3y", sim_stats)
        
        sim_str = f"ROI: {sim_stats['roi']}% | WR: {sim_stats['wr']}% | Trades: {sim_stats['trades']} | PnL: ${sim_stats['pnl']}"
        if from_cache: sim_str += " (Cached)"
        
        data_summary += f"  - Simulation (Regression Test 3y): {sim_str}\n"
        data_summary += f"  - Plan: {plan_str}\n"
        
        # Fetch News
        news = get_market_news(f"{c['ticker']} stock crypto news", max_results=2)
        news_context += f"**{c['ticker']} News:**\n{news}\n\n"

    # Agent Mode: Return JSON and Exit
    if args.json:
        import json
        print(json.dumps({"status": "ok", "candidates": candidates, "report_summary": data_summary}))
        return

    # 4. LLM Analysis (Human Mode)
    print("🧠 Generating Intelligence Report...")
    try:
        lang = os.getenv("REPORT_LANG", "EN").upper()
        lang_prompt = "English" if lang == "EN" else "Traditional Chinese (繁體中文)"
        
        # Load Prompt
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "SOUL.md")
        with open(prompt_path, "r") as f:
            system_prompt = f.read()
            
        system_prompt += f"\n\nIMPORTANT: You must output the final report in **{lang_prompt}**."
            
        client = GeminiClient()
        report = client.generate_report(data_summary, news_context, system_prompt)
        
        # 5. Delivery
        print("\n📨 Sending Report...")
        send_telegram_report(report)
        
    except Exception as e:
        print(f"Runtime Error: {e}")

if __name__ == "__main__":
    main()
