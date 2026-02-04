import pandas as pd
try:
    from config import RISK_PARAMS
except ImportError:
    from src.config import RISK_PARAMS

class PositionManager:
    """
    Manages the lifecycle of a SINGLE active trade.
    Responsible for Dynamic Exits (Trailing Stop) and Ladder Profit Taking.
    """
    def __init__(self, ticker, entry_price, qty, side='LONG', atr_at_entry=None, tp1=None, risk_params=None):
        self.ticker = ticker
        self.entry_price = float(entry_price)
        self.qty = float(qty)
        self.side = side.upper()
        self.atr_at_entry = float(atr_at_entry) if atr_at_entry else (entry_price * 0.05) # Fallback
        
        # Load Risk Params (Injection overrides Config)
        config = risk_params if risk_params else RISK_PARAMS
        self.sl_atr_mult = config.get('initial_sl_atr', 2.0)
        self.tp1_atr_mult = config.get('tp1_atr', 2.0)
        self.breakeven_atr = config.get('breakeven_trigger_atr', 1.5)
        self.trail_atr = config.get('trailing_stop_atr', 2.0)
        
        # State
        self.current_price = self.entry_price
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price # For shorts
        
        # Dynamic Exit State
        sl_dist = self.sl_atr_mult * self.atr_at_entry
        self.initial_sl = self.entry_price - sl_dist if self.side == 'LONG' else self.entry_price + sl_dist
        self.current_sl = self.initial_sl
        self.is_breakeven_active = False
        
        # Ladder Exit State
        if tp1:
             self.tp1 = float(tp1)
        else:
             tp_dist = self.tp1_atr_mult * self.atr_at_entry
             self.tp1 = self.entry_price + tp_dist if self.side == 'LONG' else self.entry_price - tp_dist
             
        self.tp1_hit = False
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
            
        # 1. Breakeven Trigger
        if not self.is_breakeven_active:
            threshold = self.entry_price + (self.breakeven_atr * self.atr_at_entry)
            if self.highest_price >= threshold:
                self.current_sl = max(self.current_sl, self.entry_price * 1.001) # Small buffer
                self.is_breakeven_active = True
        
        # 2. Trailing Stop Logic 
        if self.is_breakeven_active:
            potential_new_sl = self.highest_price - (self.trail_atr * atr)
            # Never move SL down
            if potential_new_sl > self.current_sl:
                self.current_sl = potential_new_sl

    def _update_short(self, price, atr):
        # Update Low Watermark
        if price < self.lowest_price:
            self.lowest_price = price
            
        # 1. Breakeven Trigger
        if not self.is_breakeven_active:
            threshold = self.entry_price - (self.breakeven_atr * self.atr_at_entry)
            if self.lowest_price <= threshold:
                self.current_sl = min(self.current_sl, self.entry_price * 0.999)
                self.is_breakeven_active = True
                
        # 2. Trailing Stop
        if self.is_breakeven_active:
            potential_new_sl = self.lowest_price + (self.trail_atr * atr)
            # Never move SL up (for shorts)
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
