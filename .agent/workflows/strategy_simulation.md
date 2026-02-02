---
description: How to use the Strategy Simulation logic
---

# Strategy Simulation Workflow

The **Simulation** engine acts as a "Time Machine" to verify if a strategy would have worked in the past.

## 1. Quick Verification (Regression Test)
Before taking a trade, check how the strategy performed on this specific asset over the last 3 years.
```bash
python src/simulate.py --ticker BTC-USD --period 3y
```
**Key Metrics to Watch:**
*   **Win Rate**: Should be > 50% generally, or > 40% for high R:R strategies.
*   **Max Drawdown**: Can you stomach the drop?
*   **Profit Factor**: Should be > 1.5.

## 2. Strategy Optimization
(Advanced) To find the best parameters for a specific asset.
```bash
python src/simulate.py --ticker ETH-USD --optimize
```
*Note: Optimization logic is currently in beta and performs a simple grid search.*

## 3. Interpreting Results
The simulator outputs a detailed transaction log.
*   **Panic Strategy**: Look for "Catching Falling Knife" type trades.
*   **Trinity Strategy**: Look for "Trend Following" trades.

Use this data to feed into the **Trade Tracker** for sizing.
```bash
# Example: Sim shows 60% Win Rate.
python src/track.py size BTC-USD [Entry] [SL] --winrate 60
```
