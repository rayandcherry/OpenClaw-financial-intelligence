---
description: How to use the Market Scanner logic
---

# Market Scanner Workflow

The **Scanner** is the discovery engine of OpenClaw. It finds trading opportunities using technical analysis.

## 1. Standard Scan (Human Mode)
Run the scanner to discover opportunities and send a Telegram report.
```bash
python src/scan.py
```
*   **Default**: Scans both US Stocks and Crypto.
*   **Output**: Console logs + Telegram Message.

## 2. Sector Specific Scan
Focus on a specific asset class:
```bash
python src/scan.py --mode CRYPTO
python src/scan.py --mode US
```

## 3. Targeted Diagnosis
Analyze a single ticker specifically (useful for verifying a hunch):
```bash
python src/scan.py --ticker NVDA
```

## 4. Agent Mode (JSON Output)
For integration with other AI agents or scripts, use the `--json` flag to get structured data without sending a Telegram report.
```bash
python src/scan.py --mode CRYPTO --json
```
**Output Example:**
```json
{
  "status": "ok",
  "candidates": [
    {
      "ticker": "BTC-USD",
      "strategy": "panic",
      "price": 60500.0,
      "confidence": 85
    }
  ]
}
```
