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
    except Exception as e:
        print(f"⚠️ Markdown send failed ({e}). Retrying as split plain text...")
        
        # Split into chunks of 3000 chars to be safe
        chunk_size = 3000
        chunks = [report_text[i:i+chunk_size] for i in range(0, len(report_text), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            payload["parse_mode"] = None
            payload["text"] = f"[{i+1}/{len(chunks)}] {chunk}" if len(chunks) > 1 else chunk
            
            try:
                requests.post(url, json=payload, timeout=15).raise_for_status()
                print(f"✅ Report chunk {i+1}/{len(chunks)} sent.")
            except Exception as e2:
                print(f"❌ Failed to send chunk {i+1}: {e2}")
                # Ensure user sees it in console if delivery completely fails
                if i == 0:
                    print("\n*** UNDELIVERED REPORT ***\n")
                    print(report_text)
