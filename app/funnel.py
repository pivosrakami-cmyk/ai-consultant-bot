import re

from sqlalchemy.orm import Session

from app.claude_client import ask_claude
from app.memory import summarize_dialog
from app.models import Client, Dialog, LeadRequest, Message, Tenant
from app.telegram_notify import notify_owner

LEAD_MARKER = re.compile(r"<<LEAD:(.*?)>>", re.DOTALL)
HISTORY_LIMIT = 20


def find_or_create_client(
    db: Session,
    tenant: Tenant,
    channel: str,
    external_id: str,
    name: str | None = None,
    phone: str | None = None,
) -> Client:
    client = None

    if phone:
        client = (
            db.query(Client)
            .filter(Client.tenant_id == tenant.id, Client.phone == phone)
            .first()
        )

    if not client:
        id_field = {
            "telegram": Client.telegram_id,
            "whatsapp": Client.whatsapp_id,
            "viber": Client.viber_id,
            "messenger": Client.messenger_id,
        }.get(channel)
        if id_field is not None:
            client = (
                db.query(Client)
                .filter(Client.tenant_id == tenant.id, id_field == external_id)
                .first()
            )

    if client:
        if phone and not client.phone:
            client.phone = phone
        if name and not client.name:
            client.name = name
        db.commit()
        return client

    client = Client(
        tenant_id=tenant.id,
        name=name,
        phone=phone,
        telegram_id=external_id if channel == "telegram" else None,
        whatsapp_id=external_id if channel == "whatsapp" else None,
        viber_id=external_id if channel == "viber" else None,
        messenger_id=external_id if channel == "messenger" else None,
        first_channel=channel,
    )
    db.add(client)
    db.commit()
    return client


def get_active_dialog(db: Session, client: Client, channel: str) -> Dialog:
    dialog = (
        db.query(Dialog)
        .filter(Dialog.client_id == client.id, Dialog.ended_at.is_(None))
        .order_by(Dialog.started_at.desc())
        .first()
    )
    if dialog:
        return dialog

    dialog = Dialog(client_id=client.id, channel=channel)
    db.add(dialog)
    db.commit()
    return dialog


def handle_incoming_message(
    db: Session, tenant: Tenant, client: Client, dialog: Dialog, text: str
) -> str:
    db.add(Message(dialog_id=dialog.id, role="user", content=text))
    db.commit()

    history_rows = (
        db.query(Message)
        .filter(Message.dialog_id == dialog.id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT)
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

    system_prompt = tenant.system_prompt
    if client.summary:
        system_prompt += f"\n\nКонтекст о клиенте (из прошлых обращений): {client.summary}"

    reply = ask_claude(system_prompt, history)

    lead_match = LEAD_MARKER.search(reply)
    visible_reply = LEAD_MARKER.sub("", reply).strip()

    db.add(Message(dialog_id=dialog.id, role="assistant", content=visible_reply))
    db.commit()

    # Обновляем резюме диалога после каждого обмена: раньше для текстовых каналов
    # оно не считалось вообще (только на голосовом звонке) — в CRM было пусто,
    # и память между обращениями не работала.
    summarize_dialog(db, dialog)

    if lead_match:
        description = lead_match.group(1).strip()
        db.add(LeadRequest(client_id=client.id, dialog_id=dialog.id, description=description))
        client.status = "lead"
        db.commit()

        notify_owner(
            f"Новая заявка от {client.name or 'клиента'} ({dialog.channel}):\n{description}",
            chat_id=tenant.telegram_notify_chat_id,
        )

    return visible_reply
