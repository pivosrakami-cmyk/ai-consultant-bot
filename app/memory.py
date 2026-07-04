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
    history = [{"role": m.role, "content": m.content} for m in messages]
    if not history:
        return ""

    summary = ask_claude(SUMMARY_PROMPT, history)
    dialog.summary = summary

    client: Client = dialog.client
    client.summary = summary

    db.commit()
    return summary
