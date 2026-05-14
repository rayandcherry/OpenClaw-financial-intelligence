import json
import os
from datetime import datetime
from src.tracker.position import PositionManager
from src.tracker.risk import CapitalAllocator
from src.core.data_fetcher import fetch_data
from src.core.indicators import calculate_indicators
from src.config import ACCOUNT_BALANCE

class TrackerService:
    def __init__(self, initial_balance=None):
        if initial_balance is None:
            initial_balance = ACCOUNT_BALANCE
        self.positions = {} # {ticker: PositionManager}
        self.risk_manager = CapitalAllocator(initial_balance)
        self.balance = initial_balance
        self.positions_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "positions.json")

    def add_position(self, ticker, entry_price, qty, side='LONG', tp1=None):
        from src.config import tier_for

        # Fetch latest ATR up front — used either for a fresh PositionManager
        # or to recompute SL on a Tier A add-on.
        df = fetch_data(ticker, period="1mo")
        atr = 0
        if df is not None:
            df = calculate_indicators(df)
            atr = df['ATR_14'].iloc[-1]

        if ticker in self.positions:
            existing = self.positions[ticker]
            tier = tier_for(ticker)
            # Tier A only: average-up onto the existing position if it is
            # already breakeven-locked (no downside on the original stack).
            # Tier B/C add-on is rejected — they don't earn the second bullet.
            if tier == 'A' and existing.is_breakeven_active and existing.side == side.upper():
                total_qty = existing.qty + float(qty)
                avg_entry = (existing.entry_price * existing.qty +
                             float(entry_price) * float(qty)) / total_qty
                # Recompute initial SL from the NEW ATR (a fresh stop on the
                # combined block), but never below the existing trailing SL —
                # we never give back locked profit by averaging up.
                new_sl_dist = existing.sl_atr_mult * float(atr) if atr else None
                fresh_sl = (avg_entry - new_sl_dist) if (side.upper() == 'LONG' and new_sl_dist) else None
                merged_sl = max(existing.current_sl, fresh_sl) if fresh_sl else existing.current_sl

                merged = PositionManager(ticker, avg_entry, total_qty, side,
                                         atr_at_entry=atr, tp1=tp1,
                                         initial_sl=merged_sl)
                merged.is_breakeven_active = True  # preserved from existing
                self.positions[ticker] = merged
                print(f"📈 Tier A add-on for {ticker}: avg ${avg_entry:.2f} × {total_qty}, "
                      f"SL ${merged_sl:.2f} (was ${existing.current_sl:.2f}), ATR {atr:.2f}")
                return
            else:
                reason = (
                    "tier is not A" if tier != 'A'
                    else "existing position not yet breakeven-locked"
                    if not existing.is_breakeven_active
                    else "side mismatch"
                )
                print(f"⚠️  {ticker} already tracked and add-on blocked ({reason}). "
                      f"Tier={tier}, breakeven={existing.is_breakeven_active}.")
                return

        pos = PositionManager(ticker, entry_price, qty, side, atr_at_entry=atr, tp1=tp1)
        self.positions[ticker] = pos
        print(f"Started tracking {ticker} | Entry: {entry_price} | TP1: {pos.tp1} | ATR: {atr:.2f}")

    def update_market(self):
        """
        Polls market data and updates all positions.
        Returns a list of alerts.
        """
        alerts = []
        status_report = []
        
        for ticker, pos in list(self.positions.items()):
            # Fetch Real-time data (Mocked by latest daily close for now)
            # In real system, this would be live tick data or 1h candle
            df = fetch_data(ticker, period="1mo")
            if df is None: continue
            
            df = calculate_indicators(df)
            current_price = df['Close'].iloc[-1]
            current_atr = df['ATR_14'].iloc[-1]
            
            # Update Position
            state = pos.update(current_price, current_atr)
            
            # Formulate Report
            status_line = (
                f"**{ticker}**: ${state['price']:.2f} | "
                f"PnL: ${state['pnl']} | "
                f"Health: {state['health']} | "
                f"SL: ${state['sl']}"
            )
            status_report.append(status_line)
            
            # Check Actions
            if state['action']:
                alerts.append(f"🚨 **ACTION REQUIRED ({ticker})**: {state['action']}")
                if "EXIT" in state['action']:
                    # Auto Close (simulation)
                    # del self.positions[ticker] 
                    pass
        
        return status_report, alerts

    def get_sizing_recommendation(self, ticker, price, sl, win_rate):
        from src.config import tier_cost_cap, tier_for
        cap = tier_cost_cap(ticker, self.balance)
        result = self.risk_manager.calculate_position_size(
            ticker, price, sl, win_rate, tier_cost_cap=cap
        )
        if isinstance(result, dict):
            result["tier"] = tier_for(ticker)
            result["tier_cap"] = round(cap, 2)
        return result

    def generate_tax_preview(self):
        tax_report = []
        total_tax = 0
        for ticker, pos in self.positions.items():
            if pos.unrealized_pnl > 0:
                est_tax = pos.unrealized_pnl * 0.45
                total_tax += est_tax
                tax_report.append(f"{ticker}: Profit ${pos.unrealized_pnl:.2f} -> Tax Reserve ${est_tax:.2f}")

        return "\n".join(tax_report), total_tax

    def save_positions(self):
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
        data = []
        for ticker, pm in self.positions.items():
            data.append({
                "ticker": ticker,
                "entry_price": pm.entry_price,
                "qty": pm.qty,
                "side": pm.side,
                "tp1": pm.tp1,
                "sl": pm.current_sl,
                "breakeven": pm.is_breakeven_active,
                "tp1_hit": pm.tp1_hit,
            })
        with open(self.positions_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_positions(self):
        if not os.path.exists(self.positions_file):
            return
        try:
            with open(self.positions_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        for item in data:
            self.add_position(
                ticker=item["ticker"],
                entry_price=item["entry_price"],
                qty=item["qty"],
                side=item.get("side", "LONG"),
                tp1=item.get("tp1"),
            )
            pm = self.positions.get(item["ticker"])
            if pm:
                if item.get("sl"):
                    pm.current_sl = item["sl"]
                if item.get("breakeven"):
                    pm.is_breakeven_active = True
                if item.get("tp1_hit"):
                    pm.tp1_hit = True

    def remove_position(self, ticker: str) -> dict:
        ticker = ticker.upper()
        if ticker not in self.positions:
            return {"error": f"No open position for {ticker}"}
        pm = self.positions[ticker]
        pnl = pm.unrealized_pnl if hasattr(pm, 'unrealized_pnl') else 0.0
        del self.positions[ticker]
        self.save_positions()
        return {"status": "removed", "ticker": ticker, "final_pnl": round(pnl, 2)}
