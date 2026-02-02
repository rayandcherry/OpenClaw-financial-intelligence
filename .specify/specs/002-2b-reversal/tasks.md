# Tasks: 2B Reversal Strategy

## Phase 1: Configuration & Core Logic

- [ ] **Config Update**: Add `2B` params to `src/config.py`. <!-- id: 1 -->
- [ ] **Strategy Implementation**: Implement `check_2b_setup` in `src/core/indicators.py`. <!-- id: 2 -->
    - [ ] Logic for finding 20-60d High/Low.
    - [ ] Logic for False Break detection.
    - [ ] Logic for RSI Divergence / MACD Hist check.
    - [ ] Logic for 1:3 RR Risk calc.

## Phase 2: Integration

- [ ] **Main Loop**: Update `src/main.py` to call `check_2b_setup`. <!-- id: 3 -->
- [ ] **Reporting**: Update `src/main.py` output string formatting to include new strategy details. <!-- id: 4 -->

## Phase 3: Verification

- [ ] **Manual Test**: Run `python3 src/main.py` and check for 2B signals. <!-- id: 5 -->
