import httpx

from app.config import settings
from app.models import Tenant
from app.voice import transcribe_voice

GRAPH_API = "https://graph.facebook.com/v21.0"


def resolve_credentials(tenant: Tenant) -> tuple[str, str, str]:
    phone_number_id = tenant.whatsapp_phone_number_id or settings.whatsapp_phone_number_id
    access_token = tenant.whatsapp_access_token or settings.whatsapp_access_token
    verify_token = tenant.whatsapp_verify_token or settings.whatsapp_verify_token
    return phone_number_id, access_token, verify_token


def send_message(access_token: str, phone_number_id: str, to: str, text: str) -> None:
    httpx.post(
        f"{GRAPH_API}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}},
        timeout=10,
    )


def _download_media(access_token: str, media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {access_token}"}
    meta = httpx.get(f"{GRAPH_API}/{media_id}", headers=headers, timeout=10).json()
    return httpx.get(meta["url"], headers=headers, timeout=30).content


def extract_text(access_token: str, message: dict) -> str | None:
    if message.get("type") == "text":
        return message["text"]["body"]

    if message.get("type") == "audio":
        audio_bytes = _download_media(access_token, message["audio"]["id"])
        mime_type = message["audio"].get("mime_type", "audio/ogg").split(";")[0]
        return transcribe_voice(audio_bytes, mime_type=mime_type)

    return None


def iter_incoming_messages(payload: dict):
    """Отдаёт (message, sender_name) для каждого сообщения в вебхуке WhatsApp."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages")
            if not messages:
                continue

            contacts = {c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for message in messages:
                yield message, contacts.get(message.get("from"))
