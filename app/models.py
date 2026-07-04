from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """Клиент нашего сервиса (компания, которой мы поставили бота)."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=False)
    telegram_notify_chat_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    clients = relationship("Client", back_populates="tenant")


class Client(Base):
    """Конечный клиент тенанта — человек, который пишет боту."""

    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_client_tenant_phone"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True, index=True)
    telegram_id = Column(String, nullable=True, index=True)
    whatsapp_id = Column(String, nullable=True, index=True)
    first_channel = Column(String, nullable=False)
    status = Column(String, default="new")  # new / in_progress / lead / client
    notes = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)  # краткое резюме истории для памяти
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="clients")
    dialogs = relationship("Dialog", back_populates="client")
    requests = relationship("LeadRequest", back_populates="client")


class Dialog(Base):
    """Один сеанс общения клиента с ботом на конкретном канале."""

    __tablename__ = "dialogs"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    channel = Column(String, nullable=False)  # telegram / whatsapp / viber / voice_web / ...
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)

    client = relationship("Client", back_populates="dialogs")
    messages = relationship("Message", back_populates="dialog")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=False)
    role = Column(String, nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    dialog = relationship("Dialog", back_populates="messages")


class LeadRequest(Base):
    """Заявка — момент, когда клиент готов оставить контакт/заказ."""

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="new")  # new / done / cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="requests")
