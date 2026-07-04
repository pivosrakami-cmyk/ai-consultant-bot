from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'bot.db').as_posix()}"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    telegram_bot_token: str = ""
    telegram_notify_chat_id: str = ""
    gemini_api_key: str = ""
    crm_api_key: str = "change-me"
    public_base_url: str = ""

    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = ""

    messenger_page_access_token: str = ""
    messenger_verify_token: str = ""

    viber_bot_token: str = ""

    class Config:
        env_file = str(BASE_DIR / ".env")


settings = Settings()
