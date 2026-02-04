import pandas as pd
import numpy as np
from datetime import datetime
from core.data_fetcher import fetch_data
from core.indicators import calculate_indicators, check_trinity_setup, check_panic_setup, check_2b_setup
try:
    from tracker.position import PositionManager
except ImportError:
    from src.tracker.position import PositionManager

class Portfolio:
    def __init__(self, initial_balance=100000):
        self.initial_balance = initial_balance
        self.cash = initial_balance
        self.positions = {} # {ticker: PositionManager}
        self.history = []
        self.equity_curve = []

    def current_equity(self, current_prices):
        equity = self.cash
        for ticker, pos in self.positions.items():
            current_price = current_prices.get(ticker, pos.entry_price)
            # Use PositionManager's internal PnL calculation if needed, 
            # but simple MV is fine here:
            if pos.side == 'LONG':
                equity += pos.qty * current_price
            else:
                # SHORT Equity = Cash + (Entry - Current) * Qty + CostBasis
                # Simplified: Equity = Cash + Unrealized PnL + Cost Basis
                # But Cash already has margin reserved logic? 
                # Let's stick to: Equity = Cash + Market Value of Positions
                # For Short: Market Value is effectively specific to how we model margin.
                # Simple PnL approach:
                pnl = (pos.entry_price - current_price) * pos.qty
                # We need to explicitly know cost basis if we want total account value
                # Assuming 'cash' holds everything except the 'margin' used?
                # Let's use the simple PnL add-back:
                # Equity = (Cash + CostOfPos) + PnL
                # But we deducted Cost from Cash in open_position.
                # So Equity = Cash + Cost + PnL
                equity += (pos.entry_price * pos.qty) + pnl
        return equity

    def calculate_size(self, price, stop_loss, confidence, current_equity, risk_params=None):
        if price <= 0: return 0
        
        # 1. Risk Management: Default 2%, or injected
        base_risk_pct = 0.02
        max_alloc_pct = 0.10
        
        if risk_params:
            base_risk_pct = risk_params.get('risk_per_trade', 0.02)
            max_alloc_pct = risk_params.get('max_position_size', 0.10)
            
        risk_per_trade = current_equity * base_risk_pct
        
        # Risk per share
        risk_per_share = abs(price - stop_loss)
        if risk_per_share == 0: return 0
        
        base_qty = risk_per_trade / risk_per_share
        
        # 2. Confidence Multiplier (Confidence / 50)
        # e.g., 80 conf -> 1.6x
        # e.g., 20 conf -> 0.4x
        multiplier = confidence / 50.0
        final_qty = base_qty * multiplier
        
        # 3. Max Allocation Rule
        max_cost = current_equity * max_alloc_pct
        if (final_qty * price) > max_cost:
            final_qty = max_cost / price
            
        return max(0.0, final_qty)

    def open_position(self, ticker, price, qty, sl, tp, strategy, date, side="LONG", atr=None, risk_params=None):
        cost = price * qty
        if self.cash < cost:
            return False # Insufficient funds
            
        self.cash -= cost
        
        # Instantiate PositionManager
        pos = PositionManager(ticker, price, qty, side, atr_at_entry=atr, tp1=tp, risk_params=risk_params)
        # Store metadata that PositionManager doesn't care about but Backtester does
        pos.strategy = strategy
        pos.entry_date = date
        
        self.positions[ticker] = pos
        return True

    def close_position(self, ticker, price, date, reason="signal", qty_to_close=None):
        if ticker not in self.positions:
            return
        
        pos = self.positions[ticker]
        
        # Determine quantity to close (Ladder exit support)
        qty = qty_to_close if qty_to_close else pos.qty
        
        # Revenue logic
        if pos.side == 'LONG':
             revenue = price * qty
             profit = (price - pos.entry_price) * qty
             pct_gain = (price - pos.entry_price) / pos.entry_price
             self.cash += revenue
        else: # SHORT
             # PnL = (Entry - Exit) * Qty
             profit = (pos.entry_price - price) * qty
             pct_gain = (pos.entry_price - price) / pos.entry_price
             
             # Return Collateral (Entry * Qty) + Profit
             cost_basis = pos.entry_price * qty
             self.cash += cost_basis + profit
        
        # Update Position Object
        pos.qty -= qty
        
        # Log History
        duration = (date - pos.entry_date).days
        self.history.append({
            'ticker': ticker,
            'strategy': pos.strategy,
            'side': pos.side,
            'entry_date': pos.entry_date,
            'exit_date': date,
            'duration_days': duration,
            'entry_price': pos.entry_price,
            'exit_price': price,
            'qty': qty,
            'profit': profit,
            'pct_gain': pct_gain,
            'reason': reason
        })
        
        # If fully closed, remove
        if pos.qty <= 0:
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

    def run(self, min_confidence=70, strategies=None, strategy_params=None, risk_params=None):
        # Default to ALL strategies if None
        if strategies is None:
            strategies = ["TRINITY", "PANIC", "2B"]
        else:
            strategies = [s.upper() for s in strategies]
            
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
            # ... (Exit logic remains unchanged)
            active_tickers = list(self.portfolio.positions.keys())
            
            for ticker in active_tickers:
                df = self.data_store.get(ticker)
                if df is None or current_date not in df.index:
                    continue
                
                row = df.loc[current_date]
                pos = self.portfolio.positions[ticker]
                
                current_prices[ticker] = row['Close']
                
                # --- CHECK EXITS (Dynamic via PositionManager) ---
                current_atr = row.get('ATR_14', 0)
                
                sl_hit_price = None
                if pos.side == 'LONG':
                    if row['Low'] <= pos.current_sl:
                        sl_hit_price = pos.current_sl
                        if row['Open'] < pos.current_sl: sl_hit_price = row['Open']
                else:
                    if row['High'] >= pos.current_sl:
                        sl_hit_price = pos.current_sl
                        if row['Open'] > pos.current_sl: sl_hit_price = row['Open']

                if sl_hit_price:
                     self.portfolio.close_position(ticker, sl_hit_price, current_date, reason="Stop Loss (Dynamic)")
                     continue

                trail_price = row['High'] if pos.side == 'LONG' else row['Low']
                res = pos.update(trail_price, current_atr) # PositionManager uses internal injected params if updated
                
                if res['action']:
                    if "SELL_HALF" in res['action']:
                        if not pos.tp1_hit:
                             exit_px = pos.tp1
                             self.portfolio.close_position(ticker, exit_px, current_date, reason="Take Profit 1 (Ladder)", qty_to_close=pos.qty * 0.5)
            
            # --- B. Check Entries (Signals) ---
            for ticker in self.tickers:
                if ticker in self.portfolio.positions:
                    continue # Already holding
                
                df = self.data_store.get(ticker)
                if df is None or current_date not in df.index:
                    continue
                
                df_context = df.loc[:current_date]
                row = df.loc[current_date]
                
                if row['Close'] < 5: continue 
                
                scan_res = None
                
                # 1. Trinity
                if "TRINITY" in strategies:
                    # Pass injected params if available
                    t_params = strategy_params.get('TRINITY') if strategy_params else None
                    trinity = check_trinity_setup(row, df_context, params=t_params)
                    if trinity: scan_res = trinity
                
                # 2. Panic
                if not scan_res and "PANIC" in strategies:
                    p_params = strategy_params.get('PANIC') if strategy_params else None
                    panic = check_panic_setup(row, df_context, params=p_params)
                    if panic: scan_res = panic
                
                # 3. 2B
                if not scan_res and "2B" in strategies:
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
                    
                    qty = self.portfolio.calculate_size(price, sl, confidence, curr_eq, risk_params=risk_params)
                    
                    if qty > 0:
                        atr = row.get('ATR_14', price * 0.05)
                        
                        # INJECT RISK PARAMS into PositionManager init via Portfolio proxy if needed
                        # But Portfolio.open_position instantiates PositionManager.
                        # We need to pass risk_params to Portfolio.open_position
                        
                        success = self.portfolio.open_position(
                            ticker, price, qty, sl, tp, 
                            scan_res['strategy'], current_date,
                            side=scan_res.get('side', 'LONG'),
                            atr=atr,
                            risk_params=risk_params
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
