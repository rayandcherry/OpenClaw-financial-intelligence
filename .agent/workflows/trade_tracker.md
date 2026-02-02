---
description: How to use the Trade Tracking System logic
---

# Trade Tracking Workflow

This system helps you manage active positions with dynamic risk management.

## 1. Calculate Position Size (Before Entry)
Use the Kelly Criterion & VaR calculator to determine safe sizing:
```bash
python3 src/track.py size [TICKER] [ENTRY_PRICE] [STOP_LOSS] --winrate [WR%]
# Example
python3 src/track.py size BTC-USD 65000 63000 --winrate 60
```

## 2. Add Active Position
Once filled, calculate your TP1 (e.g., 2R) and add to tracker:
```bash
python3 src/track.py add [TICKER] [PRICE] [QTY] --side [LONG/SHORT] --tp1 [TP_PRICE]
# Example
python3 src/track.py add BTC-USD 65000 0.5 --side LONG --tp1 69000
```

## 3. Monitor & Update
Run this daily or hourly to sync with market data (Prices/ATR):
```bash
python3 src/track.py monitor
```
**Output:**
- **Health**: SAFE (Risk Free), WARNING, or EXIT signal.
- **Alerts**: Specific actions like "SELL_HALF_TP1" or "EXIT_STOP_LOSS".
- **Tax Reserve**: Estimated tax set aside for profitable trades.

## 4. Remove Position
When closed:
```bash
python3 src/track.py remove [TICKER]
```
