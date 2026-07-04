from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.funnel import find_or_create_client, get_active_dialog, handle_incoming_message
from app.models import Client, Tenant
from app.schemas import ClientDetailOut, ClientOut, ClientUpdate, TestMessageIn
from app.telegram_channel import extract_text, resolve_bot_token, send_message

app = FastAPI(title="AI-консультант — воркер")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def check_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != settings.crm_api_key:
        raise HTTPException(status_code=401, detail="Неверный API-ключ")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/test/message")
def test_message(payload: TestMessageIn, db: Session = Depends(get_db)) -> dict:
    tenant = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    client = find_or_create_client(
        db, tenant, payload.channel, payload.external_id, payload.name, payload.phone
    )
    dialog = get_active_dialog(db, client, payload.channel)
    reply = handle_incoming_message(db, tenant, client, dialog, payload.text)
    return {"reply": reply}


@app.post("/webhook/telegram/{tenant_slug}")
async def telegram_webhook(tenant_slug: str, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    update = await request.json()
    message = update.get("message")
    if not message:
        return {"ok": True}

    token = resolve_bot_token(tenant.telegram_bot_token)
    chat_id = message["chat"]["id"]
    text = extract_text(token, message)
    if not text:
        return {"ok": True}

    name = message.get("from", {}).get("first_name")
    client = find_or_create_client(db, tenant, "telegram", str(chat_id), name=name)
    dialog = get_active_dialog(db, client, "telegram")
    reply = handle_incoming_message(db, tenant, client, dialog, text)

    send_message(token, chat_id, reply)
    return {"ok": True}


@app.get("/api/clients", response_model=list[ClientOut], dependencies=[Depends(check_api_key)])
def list_clients(
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[Client]:
    query = db.query(Client)
    if status:
        query = query.filter(Client.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Client.name.ilike(like), Client.phone.ilike(like))
        )
    return query.order_by(Client.updated_at.desc()).all()


@app.get(
    "/api/clients/{client_id}",
    response_model=ClientDetailOut,
    dependencies=[Depends(check_api_key)],
)
def get_client(client_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return client


@app.patch(
    "/api/clients/{client_id}",
    response_model=ClientOut,
    dependencies=[Depends(check_api_key)],
)
def update_client(
    client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)
) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)
    return client
