import httpx

from app.config import settings


def notify_owner(text: str, chat_id: str | None = None, token: str | None = None) -> None:
    """Шлёт уведомление в Telegram владельцу (о новой заявке и т.п.).

    token — бот тенанта: тогда заявка приходит от того же бота, что общается
    с клиентами; без него — общий бот из настроек.
    """
    target_chat_id = chat_id or settings.telegram_notify_chat_id
    bot_token = token or settings.telegram_bot_token
    if not bot_token or not target_chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    httpx.post(url, json={"chat_id": target_chat_id, "text": text}, timeout=10)
