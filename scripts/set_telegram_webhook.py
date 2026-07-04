"""Регистрирует вебхук бота в Telegram после деплоя.

Запуск: python -m scripts.set_telegram_webhook <tenant_slug>
Требует в .env: TELEGRAM_BOT_TOKEN, PUBLIC_BASE_URL (https-адрес сервера в Coolify)
"""

import sys

import httpx

from app.config import settings


def run(tenant_slug: str) -> None:
    if not settings.telegram_bot_token or not settings.public_base_url:
        print("Заполни TELEGRAM_BOT_TOKEN и PUBLIC_BASE_URL в .env")
        return

    webhook_url = f"{settings.public_base_url}/webhook/telegram/{tenant_slug}"
    response = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
        json={"url": webhook_url},
        timeout=10,
    )
    print(response.json())


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "demo"
    run(slug)
