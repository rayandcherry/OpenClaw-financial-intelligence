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

    if not token or not chat_id or token == "test_dummy_token":
        print("⚠️ Telegram credentials missing or invalid (Dry Run). Printing report to stdout instead.")
        print("-" * 40)
        print(report_text)
        print("-" * 40)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # 1. Try sending full Markdown
    payload = {
        "chat_id": chat_id,
        "text": report_text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        print("✅ Report sent to Telegram.")
    except Exception:
        # 2. Markdown Failed? Try plain text
        print("⚠️ Markdown failed. Retrying as plain text...")
        payload["parse_mode"] = None
        
        # If text is too long, truncate it
        if len(report_text) > 4000:
             print("⚠️ Text too long. Truncating...")
             payload["text"] = report_text[:4000] + "\n\n[Report Truncated]"
             
        try:
            requests.post(url, json=payload, timeout=15).raise_for_status()
            print("✅ Report sent (Plain Text fallback).")
        except Exception as e2:
            print(f"❌ Failed to send Telegram message: {e2}")
            # Ensure user sees it in console if delivery completely fails
            print("\n*** UNDELIVERED REPORT ***\n")
            print(report_text)
