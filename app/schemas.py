from datetime import datetime

from pydantic import BaseModel


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class DialogOut(BaseModel):
    id: int
    channel: str
    started_at: datetime
    ended_at: datetime | None
    summary: str | None
    messages: list[MessageOut] = []

    class Config:
        from_attributes = True


class LeadRequestOut(BaseModel):
    id: int
    description: str | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ClientOut(BaseModel):
    id: int
    name: str | None
    phone: str | None
    telegram_id: str | None
    whatsapp_id: str | None
    first_channel: str
    status: str
    notes: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientDetailOut(ClientOut):
    dialogs: list[DialogOut] = []
    requests: list[LeadRequestOut] = []


class ClientUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    status: str | None = None
    notes: str | None = None


class TestMessageIn(BaseModel):
    tenant_slug: str
    channel: str = "test"
    external_id: str
    name: str | None = None
    phone: str | None = None
    text: str
