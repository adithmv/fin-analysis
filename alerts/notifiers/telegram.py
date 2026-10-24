import os
import re
import httpx


def send(message, client=None):
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?\d+", chat):
        raise ValueError("Telegram credentials are missing or invalid")
    # Do not log URL/errors: Telegram embeds its secret in the path.
    try:
        with httpx.Client(timeout=15, follow_redirects=False) if client is None else client as session:
            response = session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": message[:3900], "link_preview_options": {"is_disabled": True},
                      "protect_content": True, "allow_paid_broadcast": False})
            if response.status_code != 200 or response.json().get("ok") is not True:
                raise RuntimeError("Notification rejected; check bot permissions and rate limits")
    except Exception:
        raise RuntimeError("Telegram delivery failed; inspect local credentials and connectivity") from None
