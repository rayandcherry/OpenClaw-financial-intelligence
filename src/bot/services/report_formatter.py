from datetime import datetime, timezone


STRATEGY_EMOJIS = {
    "trinity": "🟢",
    "panic": "🔴",
    "2b_reversal": "🟡",
}

STRATEGY_LABELS = {
    "trinity": "Trinity (Trend Pullback)",
    "panic": "Panic (Mean Reversion)",
    "2b_reversal": "2B Reversal",
}

TELEGRAM_MAX_LENGTH = 4096


class ReportFormatter:

    def _strategy_emoji(self, strategy: str) -> str:
        return STRATEGY_EMOJIS.get(strategy.lower(), "⚪")

    def _strategy_label(self, strategy: str) -> str:
        return STRATEGY_LABELS.get(strategy.lower(), strategy)

    def format_signal_card(self, signal: dict) -> str:
        emoji = self._strategy_emoji(signal["strategy"])
        label = self._strategy_label(signal["strategy"])
        stats = signal.get("stats", {}).get("total", {})
        wr = stats.get("wr", "N/A")
        count = stats.get("count", "N/A")
        plan = signal.get("plan", {})

        lines = [
            f"{emoji} *{signal['ticker']}* — {label}",
            f"Confidence: {signal['confidence']}/100",
            f"Price: ${signal['price']:.2f} | SL: ${plan.get('stop_loss', 0):.2f} | TP: ${plan.get('take_profit', 0):.2f}",
            f"Backtest WR: {wr}% ({count} trades)",
        ]

        news = signal.get("news")
        if news:
            lines.append(f"News: {news}")

        return "\n".join(lines)

    def format_report(self, signals: list[dict], total_scanned: int) -> str:
        messages = self.format_report_messages(signals, total_scanned)
        return messages[0] if messages else ""

    def format_report_messages(self, signals: list[dict], total_scanned: int) -> list[str]:
        now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
        count = len(signals)

        if count == 0:
            header = (
                f"📊 *OpenClaw Scan Report* — {now}\n\n"
                f"All quiet on your watchlist today. "
                f"0 signals from {total_scanned} tickers scanned.\n\n"
                f"/scan to refresh | /watchlist to edit tickers\n\n"
                f"⚠️ Not financial advice. Do your own research."
            )
            return [header]

        header = (
            f"📊 *OpenClaw Scan Report* — {now}\n\n"
            f"*{count} signal{'s' if count != 1 else ''}* found "
            f"from {total_scanned} tickers scanned\n"
        )
        footer = (
            "\n/scan to refresh | /watchlist to edit tickers\n\n"
            "⚠️ Not financial advice. Do your own research."
        )

        cards = [self.format_signal_card(s) for s in signals]
        separator = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        full = header + separator + separator.join(cards) + separator + footer
        if len(full) <= TELEGRAM_MAX_LENGTH:
            return [full]

        messages = [header]
        current = ""
        for card in cards:
            entry = separator + card
            if len(current) + len(entry) + len(footer) > TELEGRAM_MAX_LENGTH:
                if current:
                    messages.append(current)
                current = entry
            else:
                current += entry

        if current:
            messages.append(current + footer)
        else:
            messages[-1] += footer

        return messages
