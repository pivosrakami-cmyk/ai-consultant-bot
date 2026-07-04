"""Регистрирует вебхук бота в Viber после деплоя.

Запуск: python -m scripts.set_viber_webhook <tenant_slug>
Требует в .env: VIBER_BOT_TOKEN, PUBLIC_BASE_URL (https-адрес сервера в Coolify)
"""

import sys

import httpx

from app.config import settings


def run(tenant_slug: str) -> None:
    if not settings.viber_bot_token or not settings.public_base_url:
        print("Заполни VIBER_BOT_TOKEN и PUBLIC_BASE_URL в .env")
        return

    webhook_url = f"{settings.public_base_url}/webhook/viber/{tenant_slug}"
    response = httpx.post(
        "https://chatapi.viber.com/pa/set_webhook",
        headers={"X-Viber-Auth-Token": settings.viber_bot_token},
        json={"url": webhook_url, "event_types": ["message", "conversation_started"]},
        timeout=10,
    )
    print(response.json())


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "demo"
    run(slug)
