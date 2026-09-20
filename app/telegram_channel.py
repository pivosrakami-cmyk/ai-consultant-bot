import httpx

from app.config import settings
from app.voice import transcribe_voice


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_message(token: str, chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
    # Проверяем ответ Telegram: без этого ошибка отправки (битый токен, пустой текст)
    # молча терялась бы, а вебхук всё равно возвращал бы 200.
    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    response = httpx.post(
        _api_url(token, "sendMessage"),
        json=payload,
        timeout=10,
    )
    response.raise_for_status()


# Кнопка «поделиться номером» — показываем, пока телефон клиента неизвестен
SHARE_PHONE_KEYBOARD = {
    "keyboard": [[{"text": "📱 Share number · Partilhar número", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}


def forward_message(token: str, to_chat_id: int | str, from_chat_id: int | str, message_id: int) -> None:
    """Пересылает сообщение клиента (фото, файл) владельцу бизнеса."""
    httpx.post(
        _api_url(token, "forwardMessage"),
        json={"chat_id": to_chat_id, "from_chat_id": from_chat_id, "message_id": message_id},
        timeout=10,
    ).raise_for_status()


def _download_file(token: str, file_id: str) -> bytes:
    file_info = httpx.get(_api_url(token, "getFile"), params={"file_id": file_id}, timeout=10).json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    return httpx.get(file_url, timeout=30).content


def extract_text(token: str, message: dict) -> str | None:
    """Достаёт текст из сообщения Telegram: обычный текст или расшифрованное голосовое."""
    if "text" in message:
        return message["text"]

    if "voice" in message:
        audio_bytes = _download_file(token, message["voice"]["file_id"])
        return transcribe_voice(audio_bytes, mime_type="audio/ogg")

    return None


def resolve_bot_token(tenant_token: str | None) -> str:
    return tenant_token or settings.telegram_bot_token
