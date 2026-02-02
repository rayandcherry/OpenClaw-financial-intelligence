import argparse
import json
import os
import sys
from datetime import datetime

import sys
import os

# Add Project Root and Src to Path to handle mixed imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
sys.path.append(current_dir)

from src.tracker.service import TrackerService
from src.tracker.position import PositionManager

POSITIONS_FILE = "data/positions.json"

def load_positions(service):
    if not os.path.exists(POSITIONS_FILE):
        return
    try:
        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)
            for p in data:
                service.add_position(p['ticker'], p['entry_price'], p['qty'], p['side'], p.get('tp1'))
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
            "tp1_hit": pos.tp1_hit
        })
    
    os.makedirs("data", exist_ok=True)
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Trade Tracker")
    subparsers = parser.add_subparsers(dest="command")
    
    # ADD
    add_parser = subparsers.add_parser("add", help="Add a new position")
    add_parser.add_argument("ticker", type=str)
    add_parser.add_argument("price", type=float, help="Entry Price")
    add_parser.add_argument("qty", type=float, help="Quantity")
    add_parser.add_argument("--side", type=str, default="LONG", choices=["LONG", "SHORT"])
    add_parser.add_argument("--tp1", type=float, help="Target Profit 1 (Ladder Exit)")
    
    # LIST/UPDATE
    subparsers.add_parser("monitor", help="Update market data and show status")
    
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
        service.add_position(args.ticker, args.price, args.qty, args.side, args.tp1)
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
        
    elif args.command == "size":
        rec = service.get_sizing_recommendation(args.ticker, args.price, args.sl, args.winrate)
        if rec == 0:
            print("❌ Do not take this trade (Negative Edge or Zero Risk).")
        else:
            print(f"\n📊 Sizing Recommendation for {args.ticker}:")
            print(f"   Qty: {rec['qty']}")
            print(f"   Max Risk: ${rec['max_loss']}")
            print(f"   Constraint: {rec['constraint']}")
            print(f"   Kelly %: {rec['kelly_suggestion_pct']}%")

    elif args.command == "remove":
        if args.ticker in service.positions:
            del service.positions[args.ticker]
            save_positions(service)
            print(f"🗑️ Removed {args.ticker}")
        else:
            print("Ticker not found.")

if __name__ == "__main__":
    main()
