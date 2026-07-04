from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/bot.db"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    telegram_bot_token: str = ""
    telegram_notify_chat_id: str = ""
    crm_api_key: str = "change-me"

    class Config:
        env_file = ".env"


settings = Settings()
