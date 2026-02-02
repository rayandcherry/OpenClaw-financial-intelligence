class CapitalAllocator:
    """
    Manages Portfolio Risk and Position Sizing.
    Implements Kelly Criterion and VaR limits.
    """
    def __init__(self, account_balance, max_risk_per_trade_pct=0.02):
        self.balance = float(account_balance)
        self.max_risk_pct = max_risk_per_trade_pct

    def calculate_position_size(self, ticker, entry_price, stop_loss, win_rate_pct=50.0, reward_ratio=2.0):
        """
        Calculates optimal position size (Qty) based on Kelly & Risk Limits.
        """
        if entry_price <= 0: return 0
        
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0: return 0
        
        # 1. Hard Risk Limit (VaR)
        # Maximum dollar amount we are willing to lose
        max_loss_allowed = self.balance * self.max_risk_pct
        
        # Max Quantity based on Risk Limit
        qty_risk_limit = max_loss_allowed / risk_per_share
        
        # 2. Kelly Criterion
        # f = (bp - q) / b
        # b = odds (reward ratio), p = win probability, q = loss probability (1-p)
        b = reward_ratio
        p = win_rate_pct / 100.0
        q = 1.0 - p
        
        if b <= 0: b = 1.0 # Safety
        
        kelly_fraction = (b * p - q) / b
        
        # Half-Kelly is safer for real markets
        safe_kelly = kelly_fraction * 0.5
        
        if safe_kelly <= 0:
            return 0 # Edge is negative, don't trade
            
        # Dollar amount allowed by Kelly
        kelly_capital = self.balance * safe_kelly
        qty_kelly = kelly_capital / entry_price
        
        # 3. Final Decision: Min of Risk Limit and Kelly
        final_qty = min(qty_risk_limit, qty_kelly)
        
        return {
            "qty": round(final_qty, 4),
            "max_loss": round(final_qty * risk_per_share, 2),
            "kelly_suggestion_pct": round(safe_kelly * 100, 1),
            "constraint": "Risk Limit" if qty_risk_limit < qty_kelly else "Kelly Criterion"
        }

    def can_pyramid(self, existing_position):
        """
        Checks if safe to add to position.
        Rule: Only if existing position is 'Risk Free' (SL >= Entry for Long).
        """
        if not existing_position.is_breakeven_active:
            return False, "Position not yet Risk-Free (Breakeven not active)"
            
        return True, "Safe to Pyramid"
