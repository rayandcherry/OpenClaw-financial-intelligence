# OpenClaw Financial Intelligence 🦞

**OpenClaw** is a comprehensive, AI-driven financial intelligence system designed to **Scan**, **Verify**, and **Track** high-probability trading setups in US Equities and Cryptocurrencies.

It combines technical analysis algorithms, historical backtesting, and LLM-based intelligence to deliver actionable signals, and provides a dedicated tracker to manage risk during execution.

## 🚀 Key Features

### 1. Intelligent Scanning (`src/main.py`)
*   **Multi-Asset:** Covers US Blue Chips and Top 20 Cryptocurrencies.
*   **Strategies:**
    *   🛡️ **Trinity:** Trend following (Pullback to EMA50 in Uptrend).
    *   🔥 **Panic:** Mean reversion (Oversold RSI < 30 + Below Bollinger Bands).
    *   🔄 **2B Reversal:** Swing failure patterns.
*   **AI Context:** Uses **Google Gemini** to synthesize technicals with recent news (DuckDuckGo).
*   **Regression Testing:** Automatically runs a 3-year backtest on every candidate to verify historical win rates before reporting.

### 2. Paper Trading Engine (`src/simulate.py`)
*   **Time Machine:** Simulates strategies over past 3 years.
*   **Optimization:** Configurable parameter tuning.
*   **Realistic:** Accounts for fractional shares, spread, and short selling.

### 3. Trade Tracker (`src/track.py`)
*   **Risk Management:** Calculates position size using **Kelly Criterion** & **VaR** (Value at Risk).
*   **Dynamic Exits:** Implements **ATR Trailing Stops** to lock in profits.
*   **Ladder Logic:** Automatically suggests scaling out (sell 50%) at TP1.
*   **Tax Estimation:** Estimates tax reserves for short-term gains.

## 🛠️ Installation

1.  **Clone & Install**:
    ```bash
    git clone https://github.com/YOUR_USERNAME/OpenClaw.git
    cd OpenClaw
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Copy `.env.example` to `.env` and set your keys:
    ```bash
    GEMINI_API_KEY=...
    TELEGRAM_TOKEN=...
    SCAN_MODE=ALL  # US, CRYPTO, or ALL
    ```

## 🏃 Usage Guide

### Mode A: Market Scanner (Discover)
Run the daily scanner to find opportunities:
```bash
python src/main.py
```
*   *Output:* Telegram report with AI insights + Historical Win Rate.

---

### Mode B: Simulation (Verify)
Want to test a strategy on a specific ticker?
```bash
python src/simulate.py --ticker BTC-USD --period 3y
```
*   *Output:* Detailed backtest report including Max Drawdown and Win Rate.

---

### Mode C: Trade Tracker (Manage)
Manage your active positions with professional risk rules.

1.  **Size Your Trade**:
    ```bash
    # "I want to buy BTC at 65k, SL at 63k. Winrate is 60%."
    python src/track.py size BTC-USD 65000 63000 --winrate 60
    ```
    *   *Result:* "Buy 0.3 BTC (Kelly Criterion)"

2.  **Start Tracking**:
    ```bash
    python src/track.py add BTC-USD 65000 0.3 --side LONG --tp1 68000
    ```

3.  **Monitor (Hourly/Daily)**:
    ```bash
    python src/track.py monitor
    ```
    *   *Result:* Updates Trailing Stop, checks TP1, alerts if Exit needed.

## 🏗️ Architecture

## System Overview
OpenClaw is now a comprehensive financial intelligence system comprising three distinct pillars:
1.  **Scanner & Analyst**: Finds opportunities (Scan -> Enrich -> Report).
2.  **Backtest Engine**: Verifies strategies with historical data (Simulate -> Optimize).
3.  **Trade Tracker**: Manages active risk and execution (Sizing -> Monitor -> Exit).

## Component Diagram

```mermaid
graph TD
    classDef config fill:#f9f,stroke:#333,stroke-width:2px;
    classDef core fill:#bbf,stroke:#333,stroke-width:2px;
    classDef tracker fill:#fbb,stroke:#333,stroke-width:2px;
    classDef ext fill:#dfd,stroke:#333,stroke-width:2px;

    %% Entry Points
    EntryMain["src/main.py\n(Scanner)"]:::core
    EntrySim["src/simulate.py\n(Simulation)"]:::core
    EntryTrack["src/track.py\n(Tracker CLI)"]:::tracker

    %% Configuration
    Config[src/config.py]:::config
    Env[.env]:::config
    
    %% Core Shared Modules
    subgraph Core Shared
        Indicators[core/indicators.py]:::core
        DataFetch[core/data_fetcher.py]:::core
        Cache["core/cache_manager.py\n(Backtest Cache)"]:::core
        News[core/news.py]:::core
        LLM[core/llm_client.py]:::core
        Notifier[core/notifier.py]:::core
    end

    %% New Modules
    subgraph Backtest Engine
        Backtester[src/backtest.py]:::core
        PortfolioSim[Portfolio Class]:::core
    end

    subgraph Trade Tracker
        TrackerService[tracker/service.py]:::tracker
        PosMgr["tracker/position.py\n(Dynamic Exits)"]:::tracker
        RiskMgr["tracker/risk.py\n(Kelly/VaR)"]:::tracker
        StateDB[(data/positions.json)]:::tracker
    end

    %% External APIs
    subgraph External APIs
        YF[Yahoo Finance]:::ext
        DDG[DuckDuckGo]:::ext
        Gemini[Google Gemini]:::ext
        TG[Telegram]:::ext
    end

    %% Relationships
    EntryMain -->|Load| Config
    EntryMain -->|Load| Env
    EntryMain -->|Fetch| DataFetch
    EntryMain -->|Calc| Indicators
    EntryMain -->|Read| Cache

    %% Backtest Integration
    EntryMain -.->|Regression Test| Backtester
    Backtester -->|Fetch| DataFetch
    Backtester -->|Calc| Indicators
    Backtester -->|Simulate| PortfolioSim
    
    %% Tracker Relationships
    EntryTrack -->|Command| TrackerService
    TrackerService -->|Manage| PosMgr
    TrackerService -->|Calc Size| RiskMgr
    TrackerService -->|Fetch| DataFetch
    TrackerService -->|Calc| Indicators
    TrackerService -->|Persist| StateDB
    
    %% Common
    DataFetch --> YF
    News --> DDG
    LLM --> Gemini
    Notifier --> TG
```

## Data Flow: From Signal to Execution

```mermaid
sequenceDiagram
    participant Market
    participant Scanner as main.py
    participant Cache as CacheManager
    participant User
    participant Tracker as track.py

    Note over Scanner: Phase 1: Discovery
    Scanner->>Market: Fetch Data
    Scanner->>Scanner: Technical Analysis (Trinity/Panic)
    
    Scanner->>Cache: Check Historical Performance?
    alt Cache Hit
        Cache-->>Scanner: Returns WR/ROI
    else Cache Miss
        Scanner->>Scanner: Run 3-Year Backtest
        Scanner->>Cache: Save Stats
    end
    
    Scanner->>User: Telegram Report (Signal + Backtest Stats)
    
    Note over User: Phase 2: Decision
    User->>Tracker: Calculate Size (Kelly Criterion)
    Tracker-->>User: Suggest Qty (e.g. 0.5 BTC)
    User->>Market: Execute Trade (Manual)
    
    Note over Tracker: Phase 3: Management
    User->>Tracker: Add Position
    loop Hourly Monitor
        Tracker->>Market: Update Prices/ATR
        Tracker->>Tracker: Check Trailing Stop / Ladder Exit
        opt Action Triggered
            Tracker->>User: ALERT: SELL 50% / EXIT
        end
    end
```

## ⚠️ Disclaimer
**OpenClaw is a research tool.** Not financial advice. Trading involves risk of loss.
