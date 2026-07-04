import httpx

from app.config import settings
from app.models import Tenant
from app.voice import transcribe_voice

GRAPH_API = "https://graph.facebook.com/v21.0"


def resolve_credentials(tenant: Tenant) -> tuple[str, str]:
    access_token = tenant.messenger_page_access_token or settings.messenger_page_access_token
    verify_token = tenant.messenger_verify_token or settings.messenger_verify_token
    return access_token, verify_token


def send_message(access_token: str, recipient_id: str, text: str) -> None:
    httpx.post(
        f"{GRAPH_API}/me/messages",
        params={"access_token": access_token},
        json={"recipient": {"id": recipient_id}, "message": {"text": text}},
        timeout=10,
    )


def extract_text(message: dict) -> str | None:
    if "text" in message:
        return message["text"]

    for attachment in message.get("attachments", []):
        if attachment.get("type") == "audio":
            audio_bytes = httpx.get(attachment["payload"]["url"], timeout=30).content
            return transcribe_voice(audio_bytes, mime_type="audio/mp4")

    return None


def iter_incoming_messages(payload: dict):
    """Отдаёт (sender_id, message) для каждого сообщения в вебхуке Messenger."""
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message")
            if message:
                yield event["sender"]["id"], message
