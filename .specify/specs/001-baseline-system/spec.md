# Feature Specification: Baseline Financial Intelligence System

**Feature Branch**: `001-baseline-system`
**Created**: 2026-02-01
**Status**: Approved
**Input**: User description: "Current functionality of OpenClaw-financial-intelligence (Market Scan, LLM Analysis, Telegram Reporting)."

## User Scenarios & Testing

### User Story 1 - Multi-Asset Market Scanner (Priority: P1)

The system needs to scan a predefined list of assets (US Stocks and Crypto) to identify potential trading opportunities based on technical strategies.

**Why this priority**: Core functionality. Without signals, there is no intelligence to report.

**Independent Test**: Can run the scanner script independently and verify it outputs a list of "candidates" (signals) to the console or logs, without needing to send them anywhere.

**Acceptance Scenarios**:

1. **Given** a list of US Stocks and Crypto assets in config, **When** the scanner runs in "ALL" mode, **Then** it fetches 1-year daily data for each asset.
2. **Given** market data, **When** calculated against "TRINITY" (Trend) and "PANIC" (Reversion) strategies, **Then** valid signals are identified and stored as candidates.
3. **Given** a signal is found, **When** strategy rules are applied, **Then** risk management levels (Stop Loss, Take Profit) are calculated and attached to the candidate.

---

### User Story 2 - AI Intelligence Report Generation (Priority: P2)

Once candidates are found, the system uses an LLM to generate a human-readable, professional "Intelligence Report" that synthesizes technical data with recent news.

**Why this priority**: Converts raw data into actionable intelligence.

**Independent Test**: Feed a mock list of candidates to the LLM module and verify it produces a Markdown formatted report in the correct language (EN/ZH).

**Acceptance Scenarios**:

1. **Given** a list of candidates, **When** passed to the Intelligence Engine, **Then** relevant news is fetched for each asset (max 2 articles).
2. **Given** candidates and news, **When** sent to the LLM (Gemini), **Then** a structured report is generated summarizing the rationale, risk parameters, and confidence score.
3. **Given** the `REPORT_LANG` env var is "ZH", **Then** the report is generated in Traditional Chinese.

---

### User Story 3 - Telegram Notification (Priority: P3)

The final report is delivered to a specified Telegram channel.

**Why this priority**: Delivery mechanism for the user to consume the intel.

**Independent Test**: Call the notifier function with a text string and verify a message appears in the Telegram channel.

**Acceptance Scenarios**:

1. **Given** a generated report, **When** the notifier is triggered, **Then** the report is sent to the configured Telegram Chat ID.
2. **Given** a report longer than Telegram's limit (4096 chars), **When** sending, **Then** the system splits the message into chunks to ensure full delivery (Auto-Splitting).
3. **Given** an API failure (400/500), **When** sending, **Then** the system logs the error and prints the report to stdout as a fallback (no crash).

## Requirements

### Functional Requirements

- **FR-001**: System MUST support configurable asset lists for US Equities and Cryptocurrencies.
- **FR-002**: System MUST implement "TRINITY" strategy (Trend Following: SMA200, EMA50 pullbacks, RSI 40-60).
- **FR-003**: System MUST implement "PANIC" strategy (Mean Reversion: Bollinger Bands deviation, RSI < 30).
- **FR-004**: System MUST use DuckDuckGo Search to fetch recent news for signal candidates.
- **FR-005**: System MUST use Google Gemini API for report generation.
- **FR-006**: System MUST support environment-based configuration (`.env` for keys and settings).
- **FR-007**: System MUST handle Telegram message splitting for long reports.

### Key Entities

- **Candidate**: Represents a generated signal. Attributes: Ticker, Price, Strategy (Trinity/Panic), Stop Loss, Take Profit, Confidence Score, Technical Metrics (RSI, etc.).
- **Report**: The final markdown document containing the executive summary, detailed signal analysis, and risk warnings.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Scanner completes a full list scan (approx 40 assets) in under 60 seconds (excluding API rate limits).
- **SC-002**: 100% of generated signals include specific SL/TP prices.
- **SC-003**: Reports over 4000 characters are successfully delivered to Telegram as multiple messages 100% of the time.
