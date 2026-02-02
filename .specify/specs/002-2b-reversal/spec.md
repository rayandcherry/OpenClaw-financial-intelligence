# Feature Specification: 2B Reversal Strategy

**Feature Branch**: `002-2b-reversal`
**Created**: 2026-02-01
**Status**: Draft
**Input**: User request: "Add 2B Reversal Strategy (Daily Chart) to identify potential reversals with false breakouts/breakdowns."

## User Scenarios & Testing

### User Story 1 - 2B Pattern Identification (Priority: P1)

The system needs to scan for "2B" patterns where price breaks a significant high/low (20-60 days) but fails to sustain it (false breakout).

**Why this priority**: Core logic of the new strategy.

**Independent Test**:
- Create a synthetic DataFrame with a clear 2B pattern (e.g., Price goes 100 -> 110 -> 105, where 100 was prev high).
- Run `check_2b_setup` and verify it returns a signal.

**Acceptance Scenarios**:
1. **Given** a Bearish 2B setup (New High > Prev High, Close < Prev High), **When** scanned, **Then** it identifies as "Bearish 2B".
2. **Given** a Bullish 2B setup (New Low < Prev Low, Close > Prev Low), **When** scanned, **Then** it identifies as "Bullish 2B".

### User Story 2 - Momentum Filtration (Priority: P1)

Signals must be filtered by momentum to reduce false positives.

**Why this priority**: 2B patterns are prone to failure in strong trends without confirmation.

**Independent Test**:
- Mock data with 2B pattern but Strong Momentum (RSI making new highs with price). Verify Signal is REJECTED.
- Mock data with 2B pattern + Divergence (Price High, RSI Lower). Verify Signal is ACCEPTED.

**Acceptance Scenarios**:
1. **Given** a potential 2B, **When** RSI shows divergence OR MACD histogram is shrinking, **Then** the signal is valid.
2. **Given** a potential 2B, **When** ADX or Momentum is still accelerating in direction of break, **Then** the signal is discarded ("Strong Breakout").

### User Story 3 - Risk Management Calculation (Priority: P2)

Calculate precise Entry, Stop Loss, and Take Profit targets (1:3 RR).

**Why this priority**: Constitution "Safety First" principle.

**Acceptance Scenarios**:
1. **Given** a valid signal, **Then** SL is set just beyond the swing high/low.
2. **Given** SL distance > 5%, **Then** signal is flagged or position size reduced (Warning in output).
3. **Then** Take Profit is set at 3x the risk distance.

## Requirements

### Functional Requirements

- **FR-001**: System MUST look back 20-60 days to find significant Support/Resistance levels.
- **FR-002**: System MUST detect "False Breakout" (Intraday break, Closing rejection).
- **FR-003**: System MUST calculate RSI (14) and MACD (12,26,9) for filtering.
- **FR-004**: System MUST output specific format: Name, Type, Key Levels, Momentum State, Rating.
- **FR-005**: Strategy MUST be integrated into `main.py` alongside TRINITY and PANIC.

## Success Criteria

- **SC-001**: Successfully identifies historical 2B examples (backtest verification).
- **SC-002**: Risk/Reward ratio in generated plan is always >= 1:3.
