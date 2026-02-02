# Implementation Plan: 2B Reversal Strategy

## Architecture

We will implement this as a new function `check_2b_setup` within `src/core/indicators.py`. This keeps the "functional" approach.

## Components

1.  **Configuration (`src/config.py`)**
    *   Add `STRATEGY_PARAMS["2B"]`:
        *   `lookback_min`: 20
        *   `lookback_max`: 60
        *   `max_sl_pct`: 0.05 (5%)

2.  **Logic Core (`src/core/indicators.py`)**
    *   **Step 1**: Identify recent swing High/Low in the window `[t-60 : t-1]`.
    *   **Step 2**: Check today's candle:
        *   *Bearish*: `High > SwingHigh` AND `Close < SwingHigh`.
        *   *Bullish*: `Low < SwingLow` AND `Close > SwingLow`.
    *   **Step 3**: Momentum Check.
        *   *Divergence*: Is `RSI[today] < RSI[at_swing_high]` (for Bearish)?
        *   *MACD*: Is `Hist[today] < Hist[yesterday]`?
    *   **Step 4**: Risk Calc.
        *   `SL_dist = abs(Entry - Stop)`
        *   `TP_dist = SL_dist * 3`

3.  **Integration (`src/main.py`)**
    *   Add `check_2b_setup` to the scanning loop.
    *   Update report formatting to handle the new fields (Rating, Momentum State).

## Refactoring Note
The `check_trinity_setup` and `check_panic_setup` currently return a dict or None. `check_2b_setup` will follow the same contract.

## Verification Plan
We will use a dry-run scan on the current market (which has high volatility) to see if it picks up any candidates.
