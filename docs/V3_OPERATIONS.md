# SKILL.md - OpenClaw Financial Intelligence (V3)

## Overview
OpenClaw V3 is a modular financial intelligence system with three pillars: Scan, Simulate, and Track.
The goal is to systematically find, verify, and execute trades using technical strategies (Trinity, Panic, 2B).

## Core Modules

### 1. Market Scanner (`src/scan.py`)
**Purpose**: Discovery. Finds potential trade setups.
**Agent Usage**: Always use `--json` for structured output.
**Commands**:
- Scan all crypto: `python src/scan.py --mode CRYPTO --json`
- Scan specific ticker: `python src/scan.py --ticker BTC-USD --json`

### 2. Strategy Simulator (`src/simulate.py`)
**Purpose**: Validation. Verifies if a strategy works on a specific asset historically.
**Agent Usage**: Run a regression test before recommending any trade.
**Commands**:
- Verify signal: `python src/simulate.py --ticker BTC-USD --period 3y`
- Output: Returns Win Rate, ROI, and Max Drawdown. **Require > 50% Win Rate.**

### 3. Trade Tracker (`src/track.py`)
**Purpose**: Execution & Management. Manages position sizing and dynamic exits.
**Agent Usage**:
- **Step 1 (Size)**: `python src/track.py size [Ticker] [Entry] [SL] --winrate [VR]`
  - Calculates Kelly Criterion sizing.
- **Step 2 (Record)**: `python src/track.py add [Ticker] [Entry] [Qty] --side [LONG/SHORT]`
  - Records the trade.
- **Step 3 (Monitor)**: `python src/track.py monitor`
  - Updates status of active trades.

## The Golden Workflow (Mandatory)
When asked to "Find and Execute a Trade":
1. **SCAN**: `python src/scan.py --mode ALL --json` -> Find candidate.
2. **VERIFY**: `python src/simulate.py --ticker [TICKER] --period 3y` -> Check WR > 50%.
3. **SIZE**: `python src/track.py size [TICKER] [PRICE] [SL] --winrate [WR]` -> Get Qty.
4. **EXECUTE**: `python src/track.py add [TICKER] [PRICE] [QTY] --side LONG` -> Confirm.

## Configuration
- Strategies: `src/config.py`
- State: `data/positions.json`
- Cache: `data/cache/`
