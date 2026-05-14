class CapitalAllocator:
    """
    Manages Portfolio Risk and Position Sizing.
    Implements Kelly Criterion, VaR limits, and per-ticker tier cost caps.
    """
    def __init__(self, account_balance, max_risk_per_trade_pct=0.02):
        self.balance = float(account_balance)
        self.max_risk_pct = max_risk_per_trade_pct

    def calculate_position_size(self, ticker, entry_price, stop_loss,
                                 win_rate_pct=50.0, reward_ratio=2.0,
                                 tier_cost_cap=None):
        """
        Calculates optimal position size (Qty) under three constraints:
          1. VaR cap — max dollar loss per trade (account_balance * max_risk_pct)
          2. Kelly  — half-Kelly fraction of capital
          3. Tier   — overnight-gap concentration cap (None disables)
        Returns the binding constraint plus the final qty.
        """
        if entry_price <= 0: return 0

        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0: return 0

        # 1. Hard Risk Limit (VaR)
        max_loss_allowed = self.balance * self.max_risk_pct
        qty_risk_limit = max_loss_allowed / risk_per_share

        # 2. Kelly Criterion (half-Kelly for real markets)
        b = reward_ratio if reward_ratio > 0 else 1.0
        p = win_rate_pct / 100.0
        q = 1.0 - p
        kelly_fraction = (b * p - q) / b
        safe_kelly = kelly_fraction * 0.5

        if safe_kelly <= 0:
            return 0 # Edge is negative, don't trade

        kelly_capital = self.balance * safe_kelly
        qty_kelly = kelly_capital / entry_price

        # 3. Tier cost cap — gap-down protection (overnight-gap-through-SL exposure)
        qty_tier = float('inf')
        if tier_cost_cap is not None:
            qty_tier = tier_cost_cap / entry_price

        # 4. Final qty = min of the three
        candidates = {
            "Risk Limit": qty_risk_limit,
            "Kelly Criterion": qty_kelly,
            "Tier Cap": qty_tier,
        }
        constraint, final_qty = min(candidates.items(), key=lambda kv: kv[1])

        return {
            "qty": round(final_qty, 4),
            "max_loss": round(final_qty * risk_per_share, 2),
            "kelly_suggestion_pct": round(safe_kelly * 100, 1),
            "constraint": constraint,
        }

    def can_pyramid(self, existing_position):
        """
        Checks if safe to add to position.
        Rule: Only if existing position is 'Risk Free' (SL >= Entry for Long).
        """
        if not existing_position.is_breakeven_active:
            return False, "Position not yet Risk-Free (Breakeven not active)"
            
        return True, "Safe to Pyramid"
