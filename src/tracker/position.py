import pandas as pd

class PositionManager:
    """
    Manages the lifecycle of a SINGLE active trade.
    Responsible for Dynamic Exits (Trailing Stop) and Ladder Profit Taking.
    """
    def __init__(self, ticker, entry_price, qty, side='LONG', atr_at_entry=None, tp1=None):
        self.ticker = ticker
        self.entry_price = float(entry_price)
        self.qty = float(qty)
        self.side = side.upper()
        self.atr_at_entry = float(atr_at_entry) if atr_at_entry else (entry_price * 0.05) # Fallback
        
        # State
        self.current_price = self.entry_price
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price # For shorts
        
        # Dynamic Exit State
        self.initial_sl = self.entry_price - (2.0 * self.atr_at_entry) if self.side == 'LONG' else self.entry_price + (2.0 * self.atr_at_entry)
        self.current_sl = self.initial_sl
        self.is_breakeven_active = False
        
        # Ladder Exit State
        self.tp1 = float(tp1) if tp1 else (self.entry_price + (2.0 * self.atr_at_entry) if self.side == 'LONG' else self.entry_price - (2.0 * self.atr_at_entry))
        self.tp1_hit = False
        
        # Taxes (Simple estimation)
        self.unrealized_pnl = 0.0

    def update(self, current_price, current_atr=None):
        """
        Updates trade state with latest market data.
        Returns a dict actions if triggers are hit.
        """
        self.current_price = float(current_price)
        current_atr = float(current_atr) if current_atr else self.atr_at_entry
        
        action_signal = None
        
        if self.side == 'LONG':
            self._update_long(current_price, current_atr)
        else:
            self._update_short(current_price, current_atr)
            
        # Check Health
        health = self._get_health_status()
        
        # Check TP1 Ladder
        if not self.tp1_hit:
            if (self.side == 'LONG' and self.current_price >= self.tp1) or \
               (self.side == 'SHORT' and self.current_price <= self.tp1):
                self.tp1_hit = True
                action_signal = "SELL_HALF_TP1"
        
        # Check Stop Loss
        if (self.side == 'LONG' and self.current_price <= self.current_sl) or \
           (self.side == 'SHORT' and self.current_price >= self.current_sl):
             action_signal = "EXIT_STOP_LOSS" # Could be profit if trailing stop
        
        self._calculate_pnl()
        
        return {
            "ticker": self.ticker,
            "price": self.current_price,
            "sl": round(self.current_sl, 2),
            "pnl": round(self.unrealized_pnl, 2),
            "health": health,
            "action": action_signal,
            "tp1_hit": self.tp1_hit
        }

    def _update_long(self, price, atr):
        # Update High Watermark
        if price > self.highest_price:
            self.highest_price = price
            
        # 1. Breakeven Trigger: If Price > Entry + 1.5 ATR
        if not self.is_breakeven_active:
            threshold = self.entry_price + (1.5 * self.atr_at_entry)
            if self.highest_price >= threshold:
                self.current_sl = max(self.current_sl, self.entry_price * 1.001) # Small buffer
                self.is_breakeven_active = True
        
        # 2. Trailing Stop Logic (Only active after Breakeven or deep profit)
        # If we are well in profit, trail by 2 ATR from High
        if self.is_breakeven_active:
            potential_new_sl = self.highest_price - (2.0 * atr)
            # Never move SL down
            if potential_new_sl > self.current_sl:
                self.current_sl = potential_new_sl

    def _update_short(self, price, atr):
        # Update Low Watermark
        if price < self.lowest_price:
            self.lowest_price = price
            
        # 1. Breakeven Trigger: If Price < Entry - 1.5 ATR
        if not self.is_breakeven_active:
            threshold = self.entry_price - (1.5 * self.atr_at_entry)
            if self.lowest_price <= threshold:
                self.current_sl = min(self.current_sl, self.entry_price * 0.999)
                self.is_breakeven_active = True
                
        # 2. Trailing Stop
        if self.is_breakeven_active:
            potential_new_sl = self.lowest_price + (2.0 * atr)
            # Never move SL up (for shorts) - wait, SL is above price. We want to lower it.
            if potential_new_sl < self.current_sl:
                self.current_sl = potential_new_sl

    def _calculate_pnl(self):
        if self.side == 'LONG':
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.qty
        else:
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.qty

    def _get_health_status(self):
        risk_dist = abs(self.current_price - self.current_sl)
        
        if self.side == 'LONG':
            if self.current_price <= self.current_sl: return "EXIT"
            if risk_dist < (0.5 * self.atr_at_entry): return "WARNING (Near SL)"
            if self.is_breakeven_active: return "SAFE (Risk Free)"
        else:
            if self.current_price >= self.current_sl: return "EXIT"
            if risk_dist < (0.5 * self.atr_at_entry): return "WARNING (Near SL)"
            if self.is_breakeven_active: return "SAFE (Risk Free)"
            
        return "NORMAL"
