import httpx

from app.config import settings
from app.models import Tenant
from app.voice import transcribe_voice

API_URL = "https://chatapi.viber.com/pa"


def resolve_token(tenant: Tenant) -> str:
    return tenant.viber_bot_token or settings.viber_bot_token


def send_message(token: str, receiver: str, text: str) -> None:
    httpx.post(
        f"{API_URL}/send_message",
        headers={"X-Viber-Auth-Token": token},
        json={"receiver": receiver, "type": "text", "sender": {"name": "AI-консультант"}, "text": text},
        timeout=10,
    )


def extract_text(message: dict) -> str | None:
    if message.get("type") == "text":
        return message.get("text")

    if message.get("type") in ("audio", "file") and message.get("media"):
        # media отдаётся по прямой ссылке с TTL 1 час, авторизация не нужна
        audio_bytes = httpx.get(message["media"], timeout=30).content
        return transcribe_voice(audio_bytes, mime_type="audio/aac")

    return None
