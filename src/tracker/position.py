try:
    from config import RISK_PARAMS
except ImportError:
    from src.config import RISK_PARAMS

# Exit modes:
#   'atr'      — initial SL (Nx ATR) → breakeven trigger → trailing (high - 2×ATR)
#                + TP1 half-sell at entry + 2×ATR. Used by Trinity / Panic / 2B.
#   'donchian' — classic Turtle System 2 exit: SL ratchets to the rolling N-day
#                low (default 20). No breakeven step, no TP1 — ride the full
#                trend until the channel breaks. Used by Donchian entries.
EXIT_MODE_ATR = 'atr'
EXIT_MODE_DONCHIAN = 'donchian'


class PositionManager:
    """Manages the lifecycle of a SINGLE active trade.

    Two exit modes — see module docstring.
    """

    def __init__(self, ticker, entry_price, qty, side='LONG', atr_at_entry=None,
                 tp1=None, initial_sl=None, risk_params=None,
                 exit_mode=EXIT_MODE_ATR, donchian_exit_window=20):
        self.ticker = ticker
        self.entry_price = float(entry_price)
        self.qty = float(qty)
        self.side = side.upper()
        self.atr_at_entry = float(atr_at_entry) if atr_at_entry else (entry_price * 0.05) # Fallback
        self.exit_mode = exit_mode if exit_mode in (EXIT_MODE_ATR, EXIT_MODE_DONCHIAN) else EXIT_MODE_ATR
        self.donchian_exit_window = int(donchian_exit_window)

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

        # Initial Stop Loss.
        # If `initial_sl` is supplied (strategy designed the SL), use it directly
        # so the position honors the same stop that sizing was based on.
        # Otherwise fall back to the generic sl_atr_mult * ATR rule.
        # NOTE: the strategy-supplied SL was historically dropped on the floor —
        # PositionManager re-computed using RISK_PARAMS['initial_sl_atr']=3.0,
        # making actual stops 1.5-3x wider than the report told the user (PANIC
        # affected worst). The override fixes that mismatch.
        if initial_sl is not None:
            self.initial_sl = float(initial_sl)
        else:
            sl_dist = self.sl_atr_mult * self.atr_at_entry
            self.initial_sl = self.entry_price - sl_dist if self.side == 'LONG' else self.entry_price + sl_dist
        self.current_sl = self.initial_sl
        self.is_breakeven_active = False

        # Ladder Exit State — ATR mode only. Donchian mode rides the full trend.
        if tp1:
             self.tp1 = float(tp1)
        else:
             tp_dist = self.tp1_atr_mult * self.atr_at_entry
             self.tp1 = self.entry_price + tp_dist if self.side == 'LONG' else self.entry_price - tp_dist

        self.tp1_hit = False

        self.unrealized_pnl = 0.0

    def update(self, current_price, current_atr=None, donchian_low=None):
        """Update trade state with latest market data.

        `donchian_low` is the rolling N-day low ending YESTERDAY (excludes the
        current bar so the channel doesn't chase itself intraday). Only consumed
        in Donchian exit mode; ignored in ATR mode.

        Returns a dict with current snapshot + any triggered action.
        """
        self.current_price = float(current_price)
        current_atr = float(current_atr) if current_atr else self.atr_at_entry

        action_signal = None

        if self.exit_mode == EXIT_MODE_DONCHIAN:
            self._update_donchian(current_price, donchian_low)
        elif self.side == 'LONG':
            self._update_long(current_price, current_atr)
        else:
            self._update_short(current_price, current_atr)

        # Check Health
        health = self._get_health_status()

        # TP1 ladder — ATR mode only. Donchian rides until the channel breaks.
        if self.exit_mode == EXIT_MODE_ATR and not self.tp1_hit:
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

    def _update_donchian(self, price, donchian_low):
        """Turtle System 2 exit: SL ratchets to the rolling N-day low.

        Donchian is LONG-only (mirrors check_donchian_setup). No breakeven, no
        ATR trail, no TP1 — the channel low IS the trailing stop. Initial SL
        (typically entry - 2×ATR per DONCHIAN config) remains the floor until
        the channel rises above it.
        """
        if price > self.highest_price:
            self.highest_price = price
        if donchian_low is not None:
            # Ratchet only — never widen.
            self.current_sl = max(self.current_sl, float(donchian_low))

    def _calculate_pnl(self):
        if self.side == 'LONG':
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.qty
        else:
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.qty

    def _get_health_status(self):
        risk_dist = abs(self.current_price - self.current_sl)

        if self.exit_mode == EXIT_MODE_DONCHIAN:
            if self.current_price <= self.current_sl:
                return "EXIT"
            # Channel exit doesn't have a "breakeven" milestone — health is
            # binary: above SL = NORMAL, breached = EXIT.
            if risk_dist < (0.5 * self.atr_at_entry):
                return "WARNING (Near Channel)"
            return "NORMAL"

        if self.side == 'LONG':
            if self.current_price <= self.current_sl: return "EXIT"
            if risk_dist < (0.5 * self.atr_at_entry): return "WARNING (Near SL)"
            if self.is_breakeven_active: return "SAFE (Risk Free)"
        else:
            if self.current_price >= self.current_sl: return "EXIT"
            if risk_dist < (0.5 * self.atr_at_entry): return "WARNING (Near SL)"
            if self.is_breakeven_active: return "SAFE (Risk Free)"

        return "NORMAL"
