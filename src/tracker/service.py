import json
import os
from datetime import datetime
from src.tracker.position import PositionManager, EXIT_MODE_ATR, EXIT_MODE_DONCHIAN
from src.tracker.risk import CapitalAllocator
from src.core.data_fetcher import fetch_data
from src.core.indicators import calculate_indicators
from src.core.earnings import get_position_earnings, EARNINGS_NEAR_THRESHOLD_DAYS
from src.core.news import get_market_news, news_query_for_ticker, format_news_lines
from src.config import ACCOUNT_BALANCE, STRATEGY_PARAMS


def _strategy_to_exit_mode(strategy):
    """Map a strategy name (free-form) → exit mode. Donchian gets the Turtle
    channel exit; everything else (Trinity / Panic / 2B / unspecified) keeps
    the ATR trailing stop."""
    if not strategy:
        return EXIT_MODE_ATR
    s = str(strategy).lower().strip()
    if s in ('donchian', 'turtle'):
        return EXIT_MODE_DONCHIAN
    return EXIT_MODE_ATR


def _rolling_n_day_low(df, window):
    """Donchian channel exit floor: the lowest Low over the past `window` fully
    closed sessions, EXCLUDING today's bar (so the channel doesn't chase itself
    intraday). Returns None if there isn't enough history."""
    if df is None or len(df) < window + 1:
        return None
    return float(df['Low'].iloc[-(window + 1):-1].min())


class TrackerService:
    def __init__(self, initial_balance=None):
        if initial_balance is None:
            initial_balance = ACCOUNT_BALANCE
        self.positions = {} # {ticker: PositionManager}
        self.risk_manager = CapitalAllocator(initial_balance)
        self.balance = initial_balance
        self.positions_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "positions.json")

    def add_position(self, ticker, entry_price, qty, side='LONG', tp1=None,
                      strategy=None, initial_sl=None):
        """Open or extend a position.

        `strategy` controls the exit policy: 'donchian' → Turtle channel exit
        (initial SL from DONCHIAN config's 2×ATR), anything else → ATR trail.
        `initial_sl` lets the caller hard-pin the starting stop (matches the
        scan report's planned SL exactly).
        """
        from src.config import tier_for

        exit_mode = _strategy_to_exit_mode(strategy)

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
            # Donchian-exit positions don't have a breakeven concept, so the
            # add-on gate doesn't apply to them either.
            if (tier == 'A'
                    and existing.exit_mode == EXIT_MODE_ATR
                    and existing.is_breakeven_active
                    and existing.side == side.upper()):
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
                if existing.exit_mode == EXIT_MODE_DONCHIAN:
                    reason = "donchian positions don't average up"
                elif tier != 'A':
                    reason = "tier is not A"
                elif not existing.is_breakeven_active:
                    reason = "existing position not yet breakeven-locked"
                else:
                    reason = "side mismatch"
                print(f"⚠️  {ticker} already tracked and add-on blocked ({reason}). "
                      f"Tier={tier}, breakeven={existing.is_breakeven_active}, "
                      f"mode={existing.exit_mode}.")
                return

        # Donchian initial SL = entry - 2×ATR (per DONCHIAN strategy config),
        # tighter than the generic 3×ATR ATR-mode default. Caller can override.
        if exit_mode == EXIT_MODE_DONCHIAN and initial_sl is None and atr:
            donchian_sl_mult = STRATEGY_PARAMS.get('DONCHIAN', {}).get('sl_atr_mult', 2.0)
            initial_sl = float(entry_price) - donchian_sl_mult * float(atr)

        pos = PositionManager(ticker, entry_price, qty, side,
                              atr_at_entry=atr, tp1=tp1, initial_sl=initial_sl,
                              exit_mode=exit_mode)
        self.positions[ticker] = pos
        mode_tag = "Donchian (Turtle exit)" if exit_mode == EXIT_MODE_DONCHIAN else "ATR trail"
        print(f"Started tracking {ticker} | Entry: {entry_price} | "
              f"SL: ${pos.current_sl:.2f} | ATR: {atr:.2f} | Mode: {mode_tag}")

    def update_market(self):
        """Polls market data, updates all positions, attaches per-position
        earnings + news as side effects on each PositionManager.

        Returns (status_report, alerts) where status_report is a list of
        Markdown-ready strings (one per position, with optional 📅/📰 follow-up
        lines). Callers that want structured data can read `pm.next_earnings`,
        `pm.earnings_days_away`, `pm.news_lines` directly off the positions.
        """
        alerts = []
        status_report = []

        for ticker, pos in list(self.positions.items()):
            df = fetch_data(ticker, period="3mo")
            if df is None: continue

            df = calculate_indicators(df)
            current_price = df['Close'].iloc[-1]
            current_atr = df['ATR_14'].iloc[-1]

            # Donchian channel low — only meaningful for donchian-exit positions
            # but cheap to compute either way; we just don't pass it for ATR mode.
            donchian_low = None
            if pos.exit_mode == EXIT_MODE_DONCHIAN:
                donchian_low = _rolling_n_day_low(df, pos.donchian_exit_window)

            state = pos.update(current_price, current_atr,
                                donchian_low=donchian_low)

            # --- Per-position context: earnings + news ---
            try:
                earnings = get_position_earnings(ticker)
            except Exception:
                earnings = None
            pos.next_earnings = earnings.next_date if earnings else None
            pos.earnings_days_away = earnings.days_away if earnings else None

            try:
                news_raw = get_market_news(news_query_for_ticker(ticker), max_results=2)
                pos.news_lines = format_news_lines(news_raw, max_items=2)
            except Exception:
                pos.news_lines = []

            # --- Build status report block ---
            status_line = (
                f"**{ticker}**: ${state['price']:.2f} | "
                f"PnL: ${state['pnl']} | "
                f"Health: {state['health']} | "
                f"SL: ${state['sl']}"
            )
            block = [status_line]
            if pos.next_earnings is not None:
                days = pos.earnings_days_away
                day_label = (
                    "today" if days == 0
                    else f"T-{days}" if days and days > 0
                    else f"T+{abs(days)}" if days and days < 0
                    else "?"
                )
                marker = " ⚠️" if earnings and earnings.is_near else ""
                block.append(f"  📅 Earnings: {pos.next_earnings.isoformat()} ({day_label}){marker}")
            block.extend(pos.news_lines)
            status_report.append("\n".join(block))

            # --- Alerts ---
            if state['action']:
                alerts.append(f"🚨 **ACTION REQUIRED ({ticker})**: {state['action']}")
            if earnings and earnings.is_near:
                alerts.append(
                    f"📅 **EARNINGS_NEAR ({ticker})**: {pos.next_earnings.isoformat()} "
                    f"(T-{pos.earnings_days_away}d) — gap risk through SL"
                )

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
                "exit_mode": pm.exit_mode,
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
            # exit_mode is the source of truth for which exit policy applies;
            # legacy positions without the field default to ATR mode (the
            # behavior they were originally tracked under).
            mode = item.get("exit_mode", EXIT_MODE_ATR)
            strategy = 'donchian' if mode == EXIT_MODE_DONCHIAN else None
            self.add_position(
                ticker=item["ticker"],
                entry_price=item["entry_price"],
                qty=item["qty"],
                side=item.get("side", "LONG"),
                tp1=item.get("tp1"),
                strategy=strategy,
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
