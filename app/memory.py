from sqlalchemy.orm import Session

from app.claude_client import ask_claude
from app.models import Client, Dialog, Message

SUMMARY_PROMPT = (
    "Сделай краткое резюме диалога с клиентом для CRM: что обсудили, "
    "какая у клиента задача/боль, что решили, что делать дальше. "
    "2-4 предложения, без приветствий и вежливых фраз."
)


def summarize_dialog(db: Session, dialog: Dialog) -> str:
    messages = (
        db.query(Message)
        .filter(Message.dialog_id == dialog.id)
        .order_by(Message.created_at)
        .all()
    )
    if not messages:
        return ""

    # Собираем переписку в один текстовый блок и шлём одним user-сообщением.
    # Нельзя передавать историю как есть: Claude отклоняет диалог, который
    # заканчивается сообщением ассистента ("must end with a user message").
    role_names = {"user": "Клиент", "assistant": "Бот"}
    transcript = "\n".join(
        f"{role_names.get(m.role, m.role)}: {m.content}" for m in messages
    )
    summary = ask_claude(SUMMARY_PROMPT, [{"role": "user", "content": transcript}])
    dialog.summary = summary

    client: Client = dialog.client
    client.summary = summary

    db.commit()
    return summary
