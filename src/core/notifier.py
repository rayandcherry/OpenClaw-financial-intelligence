import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_telegram_report(report_text):
    """
    Sends the generated report to a Telegram channel/chat.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram credentials missing. Printing report to stdout instead.")
        print("-" * 40)
        print(report_text)
        print("-" * 40)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": report_text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Report sent to Telegram.")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")
