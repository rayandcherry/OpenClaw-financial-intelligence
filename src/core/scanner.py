import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.core.data_fetcher import fetch_data
from src.core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup, check_2b_setup, check_donchian_setup

# Configure Logger
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

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
        last_date = str(latest.name)
        
        # Run all four strategy checks, then return the highest-confidence
        # trigger. Confidence is per-strategy (not strictly comparable across
        # strategies), but it's the best ranking signal available and avoids
        # silencing a strong PANIC behind a decay-penalized TRINITY.
        candidates = []
        log_map = {
            "trinity": "✅ FOUND TRINITY",
            "panic": "🚨 FOUND PANIC",
            "2b_reversal": "🔄 FOUND 2B REVERSAL",
            "donchian": "🚀 FOUND DONCHIAN",
        }
        for fn in (check_trinity_setup, check_panic_setup, check_2b_setup, check_donchian_setup):
            try:
                res = fn(latest, df)
            except Exception as e:
                logger.error(f"{fn.__name__} failed for {ticker}: {e}")
                continue
            if res:
                candidates.append(res)

        if not candidates:
            return None

        winner = max(candidates, key=lambda x: x.get('confidence', 0))
        logger.info(f"{log_map.get(winner['strategy'], '? FOUND')}: {ticker} (conf {winner.get('confidence')})")
        return {
            "ticker": ticker,
            "date": last_date,
            **winner,
        }

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None

def scan_market(tickers, max_workers=10):
    """
    Scans a list of tickers for strategy matches concurrently.
    """
    candidates = []
    
    logger.info(f"🔍 Scanning {len(tickers)} assets...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(process_ticker, t): t for t in tickers}
        
        for future in as_completed(future_to_ticker):
            # ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    candidates.append(result)
            except Exception as exc:
                logger.error(f"Generated exception: {exc}")

    return candidates
