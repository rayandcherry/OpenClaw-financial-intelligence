<!-- Sync Impact Report
Version change: 0.0.0 → 1.0.0
List of modified principles:
- Defined I. Data-Driven Decisions
- Defined II. Safety First (Risk Management)
- Defined III. Modular Intelligence
- Defined IV. Auditability
- Defined V. Clean Code & Simplicity
Added sections: Technology Standards, Development Workflow
Templates requiring updates: (None - initial setup)
-->

# OpenClaw Financial Intelligence Constitution

## Core Principles

### I. Data-Driven Decisions
All trading strategies and market intelligence must be grounded in quantitative data and historical backtesting. We do not rely on "gut feelings" or unverified rumors. Every signal generated must carry a confidence score and, where applicable, backtest statistics (Win Rate, Drawdown) for the specific asset and timeframe.

### II. Safety First (Risk Management)
Capital preservation is the primary directive. Every trade signal generated must include explicit Risk Management parameters:
- **Stop Loss (SL)**: Mandatory for every setup.
- **Take Profit (TP)**: Defined targets based on technical levels.
- **Position Sizing**: Suggestions based on volatility (ATR) or account risk %.
Signals without risk parameters are considered invalid and must not be distributed.

### III. Modular Intelligence
The system is composed of loosely coupled modules:
- **Data Ingestion**: Fetching raw market data (yfinance, APIs).
- **Strategy Engine**: Pure functions that take data and output signals.
- **Intelligence Layer**: LLM-based analysis and context enhancement.
- **Notifier**: Delivery mechanisms (Telegram, Discord, etc.).
Modules should interact via clear interfaces/contracts to allow easy swapping of components (e.g., changing data providers or LLM models).

### IV. Auditability
Every execution of the system must be traceable.
- **Logs**: Comprehensive logging of scans, raw signals, and decisions.
- **Reports**: Generated intelligence reports are artifacts that must be archived or reproducible.
- **Errors**: Failures in data fetching or API calls must be handled gracefully and logged without crashing the entire pipeline.

### V. Clean Code & Simplicity
We value readability and maintainability over clever hacks.
- **Pythonic**: Use standard Python idioms and PEP 8 style.
- **Type Hints**: Critical functions must be type-hinted.
- **Documentation**: Docstrings for all public modules and functions.
- **Dependencies**: Keep the dependency tree minimal and manageable.

## Technology Standards

- **Language**: Python 3.10+
- **Data Analysis**: Pandas, NumPy
- **AI/LLM**: Google Gemini (primary), OpenAI (fallback)
- **Environment**: Managed via `venv` and `requirements.txt`. Secrets in `.env`.

## Development Workflow

1. **Spec-Driven**: Changes start with a specification (what & why) before code.
2. **Backtest Verification**: Strategy changes must be verified against historical data before deployment.
3. **Dry Run**: New features should be tested in `DRY_RUN` mode (no actual API sends or trades) first.

## Governance

This Constitution serves as the primary source of truth for architectural and design decisions within the OpenClaw Financial Intelligence project.
- **Supremacy**: In conflicts between code and constitution, the constitution guides the refactor.
- **Amendments**: Changes to principles require a rationale and version bump.
- **Compliance**: All Pull Requests must verify compliance with these principles.

**Version**: 1.0.0 | **Ratified**: 2026-02-01 | **Last Amended**: 2026-02-01
