import json

from sqlalchemy.orm import Session

from app.claude_client import ask_claude
from app.memory import summarize_dialog
from app.funnel import LEAD_MARKER, extract_phone, find_or_create_client
from app.models import Dialog, LeadRequest, Message, Tenant
from app.telegram_notify import notify_owner

LEAD_EXTRACT_PROMPT = (
    "Ниже — транскрипт голосового звонка с сайта. Если клиент согласился оставить "
    "контакт или явно попросил связаться с ним, ответь одной строкой "
    "<<LEAD: имя, контакт если есть, суть запроса>>. Если контакт не оставлен и "
    "явного согласия не было — ответь пустой строкой."
)

CONTACT_PROMPT = (
    "Из транскрипта звонка извлеки имя клиента и его телефон, если они названы. "
    "Ответь строго в формате JSON, без пояснений и markdown: "
    '{"name": "имя или пусто", "phone": "телефон или пусто"}'
)


def _extract_contact(transcript_text: str) -> tuple[str | None, str | None]:
    """Достаёт имя и телефон из транскрипта. Телефон надёжнее берём регуляркой."""
    name = None
    raw = ask_claude(CONTACT_PROMPT, [{"role": "user", "content": transcript_text}])
    try:
        data = json.loads(raw.strip().strip("`"))
        name = (data.get("name") or "").strip() or None
    except (json.JSONDecodeError, AttributeError):
        pass

    phone = extract_phone(transcript_text)
    return name, phone

# Разные провайдеры (Retell/ElevenLabs) по-разному называют поля реплик в транскрипте,
# поэтому пробуем несколько вариантов ключей вместо жёсткой привязки к одному формату.
_ROLE_KEYS = ("role", "speaker", "sender")
_TEXT_KEYS = ("content", "text", "utterance", "message")
_AGENT_ROLES = {"agent", "assistant", "bot"}


def normalize_call(payload: dict) -> dict | None:
    """Приводит вебхук голосового провайдера к единому виду `call`.

    Возвращает None, если событие не про завершённый звонок (его игнорируем).
    Поддержаны ElevenLabs (post-call) и Retell — форматы у них разные.
    """
    # ElevenLabs: post-call webhook — данные лежат в `data`, реплики в `transcript`
    if payload.get("type") == "post_call_transcription":
        data = payload.get("data", {})
        return {
            "call_id": data.get("conversation_id", ""),
            "transcript_object": data.get("transcript", []),
        }

    # Retell: обрабатываем только завершённый звонок
    if payload.get("event") == "call_ended":
        return payload.get("call", {})

    return None


def _parse_transcript(call: dict) -> list[dict]:
    turns = call.get("transcript_object") or []
    messages = []
    for turn in turns:
        role_raw = next((turn[k] for k in _ROLE_KEYS if k in turn), None)
        text = next((turn[k] for k in _TEXT_KEYS if k in turn), None)
        if not text:
            continue
        role = "assistant" if str(role_raw).lower() in _AGENT_ROLES else "user"
        messages.append({"role": role, "content": text})

    if messages:
        return messages

    transcript = call.get("transcript")
    return [{"role": "user", "content": transcript}] if transcript else []


def process_voice_call(db: Session, tenant: Tenant, call: dict) -> None:
    call_id = call.get("call_id", "")
    phone = call.get("from_number") or call.get("to_number")

    client = find_or_create_client(db, tenant, "voice_web", call_id, phone=phone)

    dialog = Dialog(client_id=client.id, channel="voice_web")
    db.add(dialog)
    db.commit()

    messages = _parse_transcript(call)
    for msg in messages:
        db.add(Message(dialog_id=dialog.id, role=msg["role"], content=msg["content"]))
    db.commit()

    # Имя и телефон из разговора — в поля карточки (раньше оставались пустыми,
    # данные жили только в резюме и тексте заявки).
    transcript_text = "\n".join(m["content"] for m in messages)
    name, extracted_phone = _extract_contact(transcript_text)
    if name and not client.name:
        client.name = name
    if extracted_phone and not client.phone:
        client.phone = extracted_phone
    db.commit()

    summarize_dialog(db, dialog)

    lead_reply = ask_claude(LEAD_EXTRACT_PROMPT, [{"role": "user", "content": dialog.summary or ""}])
    lead_match = LEAD_MARKER.search(lead_reply)
    if lead_match:
        description = lead_match.group(1).strip()
        db.add(LeadRequest(client_id=client.id, dialog_id=dialog.id, description=description))
        client.status = "lead"
        db.commit()

        notify_owner(
            f"Новая заявка с голосового агента на сайте:\n{description}",
            chat_id=tenant.telegram_notify_chat_id,
        )
