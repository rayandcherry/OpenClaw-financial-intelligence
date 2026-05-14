"""Bot-side report formatter — thin delegate to core.report_builder so the
Telegram bot and the CLI scan path produce identical output.
"""
from __future__ import annotations

from src.core.report_builder import build_report, build_report_messages


class ReportFormatter:

    def format_report(self, signals: list[dict], total_scanned: int) -> str:
        return build_report(signals, total_scanned)

    def format_report_messages(self, signals: list[dict], total_scanned: int) -> list[str]:
        return build_report_messages(signals, total_scanned)
