import argparse
import json
import os

from dotenv import load_dotenv

from config import US_STOCKS, AI_LIST, SPACE_LIST
from core.scanner import scan_market
from core.news import get_market_news, news_query_for_ticker
from core.notifier import send_telegram_report
from core.report_builder import build_report
from backtest import Backtester
from core.cache_manager import BacktestCache

load_dotenv()


def _resolve_tickers(args):
    mode = args.mode if args.mode else os.getenv("SCAN_MODE", "US").upper()

    # Crypto scanning is paused — CRYPTO/ALL fall back to US-only.
    if mode in ("CRYPTO", "ALL"):
        print(f"⚠️  Crypto scanning is paused. Running US-only (requested mode: {mode}).")
        mode = "US"

    if args.ticker:
        return mode, [args.ticker]
    if mode == "AI":
        return mode, list(AI_LIST)
    if mode == "SPACE":
        return mode, list(SPACE_LIST)
    return mode, list(US_STOCKS)


def _enrich_signals(candidates):
    """Attach 3y portfolio sim stats + a news snippet to each signal.

    Mutates candidates in place: adds 'sim_stats' and 'news' fields.
    """
    cache = BacktestCache()
    for c in candidates:
        sim_stats = cache.get(c["ticker"], "3y")
        if sim_stats is None:
            print(f"🔄 Running 3y sim for {c['ticker']}...")
            bt = Backtester([c["ticker"]], period="3y")
            bt.load_data()
            bt.run(min_confidence=60)
            sim_stats = bt.get_summary_metrics()
            cache.set(c["ticker"], "3y", sim_stats)
        c["sim_stats"] = sim_stats

        try:
            c["news"] = get_market_news(news_query_for_ticker(c["ticker"]), max_results=2)
        except Exception as e:
            print(f"⚠️ News fetch failed for {c['ticker']}: {e}")
            c["news"] = None


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Real-Time Scanner")
    parser.add_argument('--ticker', type=str, help='Specific ticker to scan (overrides mode)')
    parser.add_argument('--mode', type=str, choices=['US', 'AI', 'SPACE', 'CRYPTO', 'ALL'], help='Asset class to scan')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format (Agent Mode)')
    args = parser.parse_args()

    mode, target_tickers = _resolve_tickers(args)
    candidates = scan_market(target_tickers)

    if args.json:
        print(json.dumps({"status": "ok", "candidates": candidates}))
        return

    if not candidates:
        print("No candidates found matching strategies.")
        report = build_report([], total_scanned=len(target_tickers), mode=mode)
        send_telegram_report(report)
        return

    print("\n📰 Enriching signals (3y sim + news)...")
    _enrich_signals(candidates)

    report = build_report(candidates, total_scanned=len(target_tickers), mode=mode)
    print("\n📨 Sending Report...")
    print("-" * 40)
    print(report)
    print("-" * 40)
    send_telegram_report(report)


if __name__ == "__main__":
    main()
