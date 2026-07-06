from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import BASE_DIR, settings
from app.db import get_db, init_db
from app.funnel import find_or_create_client, get_active_dialog, handle_incoming_message
from app.models import Client, LeadRequest, Tenant
from app.schemas import (
    ClientCreate,
    ClientDetailOut,
    ClientOut,
    ClientUpdate,
    LeadRequestOut,
    RequestUpdate,
    TestMessageIn,
)
from app.messenger_channel import iter_incoming_messages as iter_messenger_messages
from app.messenger_channel import resolve_credentials as resolve_messenger_credentials
from app.messenger_channel import send_message as send_messenger_message
from app.messenger_channel import extract_text as extract_messenger_text
from app.telegram_channel import extract_text, resolve_bot_token, send_message
from app.viber_channel import extract_text as extract_viber_text
from app.viber_channel import resolve_token as resolve_viber_token
from app.viber_channel import send_message as send_viber_message
from app.voice_channel import normalize_call, process_voice_call
from app.whatsapp_channel import extract_text as extract_whatsapp_text
from app.whatsapp_channel import iter_incoming_messages as iter_whatsapp_messages
from app.whatsapp_channel import resolve_credentials as resolve_whatsapp_credentials
from app.whatsapp_channel import send_message as send_whatsapp_message

app = FastAPI(title="AI-консультант — воркер")
app.mount("/crm", StaticFiles(directory=str(BASE_DIR / "app" / "static"), html=True), name="crm")


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
        # Голосовое не распозналось (лимит Gemini и т.п.) — просим написать текстом
        if "voice" in message or "audio" in message:
            send_message(token, chat_id, "Не получилось распознать голосовое. Напишите, пожалуйста, текстом.")
        return {"ok": True}

    name = message.get("from", {}).get("first_name")
    client = find_or_create_client(db, tenant, "telegram", str(chat_id), name=name)
    dialog = get_active_dialog(db, client, "telegram")
    reply = handle_incoming_message(db, tenant, client, dialog, text)

    send_message(token, chat_id, reply)
    return {"ok": True}


@app.post("/webhook/voice/{tenant_slug}")
async def voice_webhook(tenant_slug: str, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    payload = await request.json()
    # Обрабатываем только завершённый звонок — анализ делаем сами через Claude,
    # не полагаясь на конфигурацию post-call analysis конкретного провайдера.
    # normalize_call понимает форматы ElevenLabs и Retell, прочее событие → None.
    call = normalize_call(payload)
    if call is None:
        return {"ok": True}

    process_voice_call(db, tenant, call)
    return {"ok": True}


def _get_tenant_or_404(db: Session, tenant_slug: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")
    return tenant


@app.get("/webhook/whatsapp/{tenant_slug}")
def whatsapp_verify(tenant_slug: str, request: Request, db: Session = Depends(get_db)):
    tenant = _get_tenant_or_404(db, tenant_slug)
    _, _, verify_token = resolve_whatsapp_credentials(tenant)

    params = request.query_params
    if params.get("hub.verify_token") == verify_token:
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Неверный verify_token")


@app.post("/webhook/whatsapp/{tenant_slug}")
async def whatsapp_webhook(tenant_slug: str, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = _get_tenant_or_404(db, tenant_slug)
    phone_number_id, access_token, _ = resolve_whatsapp_credentials(tenant)

    payload = await request.json()
    for message, sender_name in iter_whatsapp_messages(payload):
        text = extract_whatsapp_text(access_token, message)
        if not text:
            continue

        external_id = message["from"]
        client = find_or_create_client(db, tenant, "whatsapp", external_id, name=sender_name, phone=external_id)
        dialog = get_active_dialog(db, client, "whatsapp")
        reply = handle_incoming_message(db, tenant, client, dialog, text)

        send_whatsapp_message(access_token, phone_number_id, external_id, reply)

    return {"ok": True}


@app.get("/webhook/messenger/{tenant_slug}")
def messenger_verify(tenant_slug: str, request: Request, db: Session = Depends(get_db)):
    tenant = _get_tenant_or_404(db, tenant_slug)
    _, verify_token = resolve_messenger_credentials(tenant)

    params = request.query_params
    if params.get("hub.verify_token") == verify_token:
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Неверный verify_token")


@app.post("/webhook/messenger/{tenant_slug}")
async def messenger_webhook(tenant_slug: str, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = _get_tenant_or_404(db, tenant_slug)
    access_token, _ = resolve_messenger_credentials(tenant)

    payload = await request.json()
    for sender_id, message in iter_messenger_messages(payload):
        text = extract_messenger_text(message)
        if not text:
            continue

        client = find_or_create_client(db, tenant, "messenger", sender_id)
        dialog = get_active_dialog(db, client, "messenger")
        reply = handle_incoming_message(db, tenant, client, dialog, text)

        send_messenger_message(access_token, sender_id, reply)

    return {"ok": True}


@app.post("/webhook/viber/{tenant_slug}")
async def viber_webhook(tenant_slug: str, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = _get_tenant_or_404(db, tenant_slug)
    token = resolve_viber_token(tenant)

    payload = await request.json()
    if payload.get("event") != "message":
        return {"ok": True}

    sender = payload["sender"]
    text = extract_viber_text(payload["message"])
    if not text:
        return {"ok": True}

    client = find_or_create_client(db, tenant, "viber", sender["id"], name=sender.get("name"))
    dialog = get_active_dialog(db, client, "viber")
    reply = handle_incoming_message(db, tenant, client, dialog, text)

    send_viber_message(token, sender["id"], reply)
    return {"ok": True}


@app.get("/api/clients", response_model=list[ClientOut], dependencies=[Depends(check_api_key)])
def list_clients(
    q: str | None = None,
    status: str | None = None,
    tenant_slug: str | None = None,
    db: Session = Depends(get_db),
) -> list[Client]:
    query = db.query(Client)
    if tenant_slug:
        query = query.join(Tenant).filter(Tenant.slug == tenant_slug)
    if status:
        query = query.filter(Client.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Client.name.ilike(like), Client.phone.ilike(like))
        )
    return query.order_by(Client.updated_at.desc()).all()


@app.get("/api/tenants", dependencies=[Depends(check_api_key)])
def list_tenants(db: Session = Depends(get_db)) -> list[dict]:
    tenants = db.query(Tenant).all()
    return [{"slug": t.slug, "name": t.name} for t in tenants]


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


@app.post(
    "/api/clients",
    response_model=ClientOut,
    dependencies=[Depends(check_api_key)],
)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> Client:
    tenant = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Тенант не найден")

    client = Client(
        tenant_id=tenant.id,
        name=payload.name,
        phone=payload.phone,
        notes=payload.notes,
        first_channel="manual",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@app.delete("/api/clients/{client_id}", dependencies=[Depends(check_api_key)])
def delete_client(client_id: int, db: Session = Depends(get_db)) -> dict:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    db.delete(client)
    db.commit()
    return {"ok": True}


@app.patch(
    "/api/requests/{request_id}",
    response_model=LeadRequestOut,
    dependencies=[Depends(check_api_key)],
)
def update_request(
    request_id: int, payload: RequestUpdate, db: Session = Depends(get_db)
) -> LeadRequest:
    lead_request = db.query(LeadRequest).filter(LeadRequest.id == request_id).first()
    if not lead_request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    lead_request.status = payload.status
    db.commit()
    db.refresh(lead_request)
    return lead_request
