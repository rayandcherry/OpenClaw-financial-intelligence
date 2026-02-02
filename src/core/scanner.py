import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.data_fetcher import fetch_data
from core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup, check_2b_setup

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
        
        # Check Strategies
        trinity_result = check_trinity_setup(latest, df)
        panic_result = check_panic_setup(latest, df)
        reversal_result = check_2b_setup(latest, df)
        
        if trinity_result:
            logger.info(f"✅ FOUND TRINITY: {ticker}")
            return {
                "ticker": ticker,
                **trinity_result
            }
            
        elif panic_result:
            logger.info(f"🚨 FOUND PANIC: {ticker}")
            return {
                "ticker": ticker,
                **panic_result
            }

        elif reversal_result:
            logger.info(f"🔄 FOUND 2B REVERSAL: {ticker}")
            return {
                "ticker": ticker,
                **reversal_result
            }
            
        return None

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
