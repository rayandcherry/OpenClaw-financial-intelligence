import pandas as pd
import numpy as np
from datetime import datetime
from core.data_fetcher import fetch_data
from core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup, check_2b_setup

class Portfolio:
    def __init__(self, initial_balance=100000):
        self.initial_balance = initial_balance
        self.cash = initial_balance
        self.positions = {} # {ticker: {'qty': 0, 'entry_price': 0, 'sl': 0, 'tp': 0}}
        self.history = []
        self.equity_curve = []

    def current_equity(self, current_prices):
        equity = self.cash
        for ticker, pos in self.positions.items():
            current_price = current_prices.get(ticker, pos['entry_price'])
            equity += pos['qty'] * current_price
        return equity

    def calculate_size(self, price, stop_loss, confidence, current_equity):
        if price <= 0: return 0
        
        # 1. Risk Management: Risk 2% of Current Equity per trade
        risk_per_trade = current_equity * 0.02
        
        # Risk per share
        risk_per_share = abs(price - stop_loss)
        if risk_per_share == 0: return 0
        
        base_qty = risk_per_trade / risk_per_share
        
        # 2. Confidence Multiplier (Confidence / 50)
        # e.g., 80 conf -> 1.6x
        # e.g., 20 conf -> 0.4x
        multiplier = confidence / 50.0
        final_qty = base_qty * multiplier
        
        # 3. Max Allocation Rule (Max 10% of equity per position)
        max_cost = current_equity * 0.10
        if (final_qty * price) > max_cost:
            final_qty = max_cost / price
            
        return max(0.0, final_qty)

    def open_position(self, ticker, price, qty, sl, tp, strategy, date, side="LONG"):
        cost = price * qty
        if self.cash < cost:
            return False # Insufficient funds
            
        self.cash -= cost
        self.positions[ticker] = {
            'qty': qty,
            'entry_price': price,
            'sl': sl,
            'tp': tp,
            'tp': tp,
            'strategy': strategy,
            'entry_date': date,
            'side': side
        }
        return True

    def close_position(self, ticker, price, date, reason="signal"):
        if ticker not in self.positions:
            return
        
        pos = self.positions[ticker]
        side = pos.get('side', 'LONG')
        
        revenue = price * pos['qty']
        
        if side == 'LONG':
             profit = revenue - (pos['entry_price'] * pos['qty'])
             pct_gain = (price - pos['entry_price']) / pos['entry_price']
             self.cash += revenue
        else: # SHORT
             # Revenue logic: we sold entry, buy back exit. 
             # Profit = (Entry - Exit) * Qty
             entry_val = pos['entry_price'] * pos['qty']
             exit_val = price * pos['qty']
             profit = entry_val - exit_val
             pct_gain = (pos['entry_price'] - price) / pos['entry_price']
             
             # Cash effect: We received cash at entry (theoretically), paid at exit.
             # Simplified Spot Sim: We reserved cash as collateral. Return collateral + profit.
             cost = pos['entry_price'] * pos['qty']
             self.cash += cost + profit
        
        # Calculate Duration
        duration = (date - pos['entry_date']).days
        
        self.history.append({
            'ticker': ticker,
            'strategy': pos['strategy'],
            'side': side,
            'entry_date': pos['entry_date'],
            'exit_date': date,
            'duration_days': duration,
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'qty': pos['qty'],
            'profit': profit,
            'pct_gain': pct_gain,
            'reason': reason
        })
        
        del self.positions[ticker]

class Backtester:
    def __init__(self, tickers, period="3y"):
        self.tickers = tickers
        self.period = period
        self.portfolio = Portfolio()
        self.data_store = {} # {ticker: df}

    def load_data(self):
        print(f"Helper: Downloading data for {len(self.tickers)} tickers ({self.period})...")
        for t in self.tickers:
            df = fetch_data(t, period=self.period)
            if df is not None and not df.empty:
                df = calculate_indicators(df)
                self.data_store[t] = df
            else:
                print(f"Warning: No data for {t}")

    def run(self, min_confidence=70):
        # 1. Align Dates (Find common date range or just union)
        # We need to iterate day by day to simulate realistic portfolio state
        all_dates = set()
        for df in self.data_store.values():
            all_dates.update(df.index)
        
        sorted_dates = sorted(list(all_dates))
        print(f"Simulation Range: {sorted_dates[0].date()} to {sorted_dates[-1].date()} ({len(sorted_dates)} trading days)")

        # 2. Daily Loop
        for current_date in sorted_dates:
            # Capture current prices for equity calc
            current_prices = {}
            
            # --- A. Check Exits (Stop Loss / Take Profit) ---
            # We use 'Low' for SL and 'High' for TP triggers on the current day bar
            # Assumption: Order executes if price passes through level.
            # Conservative: Hit SL first, then TP (pessimistic).
            
            # Create a list to modify dict while iterating
            active_tickers = list(self.portfolio.positions.keys())
            
            for ticker in active_tickers:
                df = self.data_store.get(ticker)
                if df is None or current_date not in df.index:
                    continue
                
                row = df.loc[current_date]
                pos = self.portfolio.positions[ticker]
                
                current_prices[ticker] = row['Close']
                
                side = pos.get('side', 'LONG')
                
                # --- CHECK EXITS ---
                # LONG Logic
                if side == 'LONG':
                    # Check SL (Low touches SL)
                    if row['Low'] <= pos['sl']:
                        exit_price = pos['sl']
                        # Gap Down
                        if row['Open'] < pos['sl']: exit_price = row['Open']
                        self.portfolio.close_position(ticker, exit_price, current_date, reason="Stop Loss")
                        continue
                        
                    # Check TP (High touches TP)
                    if row['High'] >= pos['tp']:
                        exit_price = pos['tp']
                        # Gap Up
                        if row['Open'] > pos['tp']: exit_price = row['Open']
                        self.portfolio.close_position(ticker, exit_price, current_date, reason="Take Profit")
                        continue
                        
                # SHORT Logic
                else:
                    # Check SL (High touches SL - Price went UP)
                    if row['High'] >= pos['sl']:
                        exit_price = pos['sl']
                        # Gap Up
                        if row['Open'] > pos['sl']: exit_price = row['Open']
                        self.portfolio.close_position(ticker, exit_price, current_date, reason="Stop Loss")
                        continue
                        
                    # Check TP (Low touches TP - Price went DOWN)
                    if row['Low'] <= pos['tp']:
                        exit_price = pos['tp']
                        # Gap Down
                        if row['Open'] < pos['tp']: exit_price = row['Open']
                        self.portfolio.close_position(ticker, exit_price, current_date, reason="Take Profit")
                        continue
            
            # --- B. Check Entries (Signals) ---
            for ticker in self.tickers:
                if ticker in self.portfolio.positions:
                    continue # Already holding
                
                df = self.data_store.get(ticker)
                if df is None or current_date not in df.index:
                    continue
                    
                # PREVENT LOOKAHEAD BIAS:
                # pass only data UP TO current_date
                # Assuming df is sorted index.
                # However, df.loc[:current_date] usually includes current_date.
                # Strategies typically assume we are making decision at Close of candle,
                # or based on indicators final value of that day.
                # If we trade "Next Open", we gen signal today, trade tomorrow.
                # If we trade "Close", we gen signal now.
                # Let's assume we can execute at 'Close' price if signal matches.
                
                # Context Slicing (Optimization: Don't slice full DF every time if not needed by all strats)
                # But our strats checks need 'df_context'.
                # To be fast, we might just pass full DF and ensure strats don't peek?
                # The strategies I wrote earlier use `df_context` for `backtest_regime_performance` 
                # which uses .iloc[idx+1:idx+21]. THIS IS BAD if passed full DF.
                
                # For this MVP simulation, we must strictly pass history.
                # Slicing df.loc[:current_date] is safest.
                
                df_context = df.loc[:current_date]
                row = df.loc[current_date]
                
                # Basic Filters to save time
                if row['Close'] < 5: continue # Skip penny stocks
                
                # Check Strategies
                scan_res = None
                
                # 1. Trinity
                trinity = check_trinity_setup(row, df_context)
                if trinity: scan_res = trinity
                
                # 2. Panic
                if not scan_res:
                    panic = check_panic_setup(row, df_context)
                    if panic: scan_res = panic
                
                # 3. 2B
                if not scan_res:
                    _2b = check_2b_setup(row, df_context)
                    if _2b: scan_res = _2b
                    
                # Execute Entry
                if scan_res:
                    if scan_res['confidence'] < min_confidence:
                        continue
                        
                    confidence = scan_res['confidence']
                    plan = scan_res['plan']
                    sl = plan['stop_loss']
                    tp = plan['take_profit']
                    price = row['Close']
                    
                    # Updates current equity for sizing
                    curr_eq = self.portfolio.current_equity(current_prices)
                    
                    qty = self.portfolio.calculate_size(price, sl, confidence, curr_eq)
                    
                    if qty > 0:
                        success = self.portfolio.open_position(
                            ticker, price, qty, sl, tp, 
                            scan_res['strategy'], current_date,
                            side=scan_res.get('side', 'LONG')
                        )
                        if success:
                            # print(f"[{current_date.date()}] Bought {ticker} ({scan_res['strategy']}) @ {price} | Qty: {qty}")
                            pass

            # End of Day Tracking
            self.portfolio.equity_curve.append({
                'date': current_date,
                'equity': self.portfolio.current_equity(current_prices),
                'cash': self.portfolio.cash
            })

    def generate_report(self):
        hist = pd.DataFrame(self.portfolio.history)
        if hist.empty:
            return "No trades executed."
            
        total_trades = len(hist)
        wins = len(hist[hist['profit'] > 0])
        wr = (wins / total_trades) * 100
        total_pnl = hist['profit'].sum()
        
        final_equity = self.portfolio.equity_curve[-1]['equity']
        roi = ((final_equity - self.portfolio.initial_balance) / self.portfolio.initial_balance) * 100
        
        # Calculate Win Rate per Strategy
        strat_stats = hist.groupby('strategy').agg(
            Count=('profit', 'count'),
            Wins=('profit', lambda x: (x > 0).sum()),
            Total_PnL=('profit', 'sum'),
            Avg_PnL=('profit', 'mean')
        )
        strat_stats['Win_Rate'] = (strat_stats['Wins'] / strat_stats['Count']) * 100
        strat_stats = strat_stats.drop(columns=['Wins']) # cleanup
        
        report = f"""
=== Backtest Report ===
Period: {self.period}
Initial Balance: ${self.portfolio.initial_balance:,.2f}
Final Equity:    ${final_equity:,.2f}
ROI:             {roi:.2f}%
-----------------------
Total Trades:    {total_trades}
Win Rate:        {wr:.1f}%
Total PnL:       ${total_pnl:,.2f}

Strategy Performance:
{strat_stats.to_string(float_format="%.2f")}

Trade History (Last 50):
{hist[['entry_date', 'exit_date', 'ticker', 'side', 'strategy', 'qty', 'entry_price', 'exit_price', 'duration_days', 'profit', 'pct_gain', 'reason']].tail(50).to_string(index=False)}
        """
        return report

    def get_summary_metrics(self):
        """Returns concise metrics for programmatic use."""
        hist = pd.DataFrame(self.portfolio.history)
        if hist.empty:
            return {"roi": 0.0, "wr": 0.0, "trades": 0, "pnl": 0.0}
            
        total_trades = len(hist)
        wins = len(hist[hist['profit'] > 0])
        wr = (wins / total_trades) * 100
        total_pnl = hist['profit'].sum()
        
        final_equity = self.portfolio.equity_curve[-1]['equity']
        roi = ((final_equity - self.portfolio.initial_balance) / self.portfolio.initial_balance) * 100
        
        return {
            "roi": round(roi, 2),
            "wr": round(wr, 1),
            "trades": total_trades,
            "pnl": round(total_pnl, 2)
        }
