import httpx

from app.config import settings


def notify_owner(text: str, chat_id: str | None = None) -> None:
    """Шлёт уведомление в Telegram владельцу (о новой заявке и т.п.)."""
    target_chat_id = chat_id or settings.telegram_notify_chat_id
    if not settings.telegram_bot_token or not target_chat_id:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    httpx.post(url, json={"chat_id": target_chat_id, "text": text}, timeout=10)
