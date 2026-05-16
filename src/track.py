import argparse
import json
import os
import sys
from datetime import datetime

# Add Project Root and Src to Path to handle mixed imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
sys.path.append(current_dir)

from src.tracker.service import TrackerService

POSITIONS_FILE = "data/positions.json"

def load_positions(service):
    if not os.path.exists(POSITIONS_FILE):
        return
    try:
        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)
            for p in data:
                mode = p.get('exit_mode')
                strategy = 'donchian' if mode == 'donchian' else None
                service.add_position(p['ticker'], p['entry_price'], p['qty'],
                                      p['side'], p.get('tp1'),
                                      strategy=strategy)
                # Restore state (simplified for MVP)
                if 'sl' in p:
                    service.positions[p['ticker']].current_sl = p['sl']
                    service.positions[p['ticker']].is_breakeven_active = p.get('breakeven', False)
                    service.positions[p['ticker']].tp1_hit = p.get('tp1_hit', False)
    except Exception as e:
        print(f"Error loading positions: {e}")

def save_positions(service):
    data = []
    for ticker, pos in service.positions.items():
        data.append({
            "ticker": ticker,
            "entry_price": pos.entry_price,
            "qty": pos.qty,
            "side": pos.side,
            "tp1": pos.tp1,
            "sl": pos.current_sl,
            "breakeven": pos.is_breakeven_active,
            "tp1_hit": pos.tp1_hit,
            "exit_mode": pos.exit_mode,
        })
    
    os.makedirs("data", exist_ok=True)
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def _build_telegram_summary(service, status_report, alerts, total_tax):
    """Format the monitor output as a Telegram-Markdown-V1 message.
    `status_report` and `alerts` come from TrackerService.update_market() —
    we re-derive structured fields off `service.positions` for a clean layout."""
    date_str = datetime.now().strftime("%b %d, %Y")

    parts = [f"*📊 Position Monitor* · {date_str}"]

    positions = list(service.positions.values())
    total_pnl = sum(p.unrealized_pnl for p in positions)
    pnl_sign = "+" if total_pnl >= 0 else "-"
    parts.append(f"{len(positions)} positions · PnL {pnl_sign}${abs(total_pnl):.2f}")

    if alerts:
        alert_lines = ["🚨 *Alerts*"]
        for a in alerts:
            # Existing format: "🚨 **ACTION REQUIRED (NVDA)**: SELL_HALF_TP1"
            # Reduce to: "• NVDA: SELL_HALF_TP1"
            try:
                ticker = a.split("(")[1].split(")")[0]
                action = a.split(": ", 1)[1]
                alert_lines.append(f"• `{ticker}`: {action}")
            except (IndexError, ValueError):
                alert_lines.append(f"• {a}")
        parts.append("\n".join(alert_lines))

    if positions:
        pos_lines = ["📈 *Positions*"]
        for p in positions:
            pnl = p.unrealized_pnl
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            health = p._get_health_status()
            be_mark = " 🔒" if p.is_breakeven_active else ""
            tp_mark = " · TP1✓" if p.tp1_hit else ""
            block = [
                f"`{p.ticker}` ×{int(p.qty) if p.qty == int(p.qty) else p.qty} @ ${p.entry_price:.2f} → "
                f"${p.current_price:.2f} ({pnl_str})",
                f"  SL ${p.current_sl:.2f} · {health}{be_mark}{tp_mark}",
            ]
            # Earnings calendar (set by update_market as a side effect)
            next_earnings = getattr(p, 'next_earnings', None)
            if next_earnings is not None:
                days = getattr(p, 'earnings_days_away', None)
                if days is None:
                    day_label = "?"
                elif days == 0:
                    day_label = "today"
                elif days > 0:
                    day_label = f"T-{days}"
                else:
                    day_label = f"T+{abs(days)}"
                near_mark = " ⚠️" if days is not None and 0 <= days <= 5 else ""
                block.append(f"  📅 {next_earnings.isoformat()} ({day_label}){near_mark}")
            # Per-position news headlines (already prefixed with "  📰 ")
            news_lines = getattr(p, 'news_lines', None) or []
            block.extend(news_lines)
            pos_lines.append("\n".join(block))
        parts.append("\n".join(pos_lines))

    if total_tax > 0:
        parts.append(f"💰 Tax reserve: ${total_tax:.2f}")

    parts.append("_⚠️ Not financial advice._")
    return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Trade Tracker")
    subparsers = parser.add_subparsers(dest="command")
    
    # ADD
    add_parser = subparsers.add_parser("add", help="Add a new position")
    add_parser.add_argument("ticker", type=str)
    add_parser.add_argument("price", type=float, help="Entry Price")
    add_parser.add_argument("qty", type=float, help="Quantity")
    add_parser.add_argument("--side", type=str, default="LONG", choices=["LONG", "SHORT"])
    add_parser.add_argument("--tp1", type=float, help="Target Profit 1 (Ladder Exit, ATR mode only)")
    add_parser.add_argument("--strategy", type=str, default=None,
                             choices=["donchian", "trinity", "panic", "2b"],
                             help="Origin strategy. 'donchian' switches to Turtle channel exit; others use ATR trail.")
    
    # LIST/UPDATE
    monitor_parser = subparsers.add_parser("monitor", help="Update market data and show status")
    monitor_parser.add_argument("--notify", action="store_true",
                                 help="Push the monitor summary to Telegram via TELEGRAM_TOKEN/TELEGRAM_CHAT_ID")
    
    # SIZE
    size_parser = subparsers.add_parser("size", help="Calculate position size (Kelly)")
    size_parser.add_argument("ticker", type=str)
    size_parser.add_argument("price", type=float)
    size_parser.add_argument("sl", type=float)
    size_parser.add_argument("--winrate", type=float, default=50.0)
    
    # REMOVE
    rm_parser = subparsers.add_parser("remove", help="Remove a position")
    rm_parser.add_argument("ticker", type=str)

    args = parser.parse_args()
    
    service = TrackerService()
    load_positions(service)
    
    if args.command == "add":
        service.add_position(args.ticker, args.price, args.qty, args.side, args.tp1,
                              strategy=args.strategy)
        save_positions(service)
        print(f"✅ Added {args.ticker}")
        
    elif args.command == "monitor":
        print("\n🔍 Syncing Market Data...")
        report, alerts = service.update_market()

        print("\n=== Active Positions ===")
        if not report:
            print("No active positions.")
        for line in report:
            print(line)

        print("\n=== Alerts ===")
        if not alerts:
            print("No actionable alerts.")
        for alert in alerts:
            print(alert)

        # Generate Tax View
        tax_str, total_tax = service.generate_tax_preview()
        if total_tax > 0:
            print(f"\n💰 Tax Reserve Needed: ${total_tax:.2f}")

        save_positions(service) # Save state updates (e.g. SL moves)

        if args.notify:
            from src.core.notifier import send_telegram_report
            msg = _build_telegram_summary(service, report, alerts, total_tax)
            send_telegram_report(msg)
        
    elif args.command == "size":
        rec = service.get_sizing_recommendation(args.ticker, args.price, args.sl, args.winrate)
        if rec == 0:
            print("❌ Do not take this trade (Negative Edge or Zero Risk).")
        else:
            print(f"\n📊 Sizing Recommendation for {args.ticker.upper()}:")
            print(f"   Tier:       {rec.get('tier', '?')} (cost cap ${rec.get('tier_cap', '?')})")
            print(f"   Qty:        {rec['qty']}")
            cost = rec['qty'] * args.price
            print(f"   Cost:       ${cost:.2f}")
            print(f"   Max Risk:   ${rec['max_loss']}")
            print(f"   Constraint: {rec['constraint']}")
            print(f"   Kelly %:    {rec['kelly_suggestion_pct']}%")

    elif args.command == "remove":
        if args.ticker in service.positions:
            del service.positions[args.ticker]
            save_positions(service)
            print(f"🗑️ Removed {args.ticker}")
        else:
            print("Ticker not found.")

if __name__ == "__main__":
    main()
