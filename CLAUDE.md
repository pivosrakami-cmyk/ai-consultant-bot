# AI-консультант — воркер (проект)

Многоканальный AI-бот: голосовой агент на сайте + мессенджеры (Telegram/WhatsApp/Viber/Messenger).
Полный план и архитектура — в Obsidian: `../Chat bot.md`.

## Стек
- Python 3.12, FastAPI, SQLAlchemy, SQLite (→ Postgres при росте)
- Claude API (claude-sonnet-4-6) — диалог и воронка
- Gemini — расшифровка голосовых в мессенджерах
- Мультитенантность: таблица `tenants`, у каждого свой `system_prompt`

## Ключевые модули (`app/`)
- `models.py` — Tenant, Client, Dialog, Message, LeadRequest
- `funnel.py` — приём сообщения → Claude → детект заявки (маркер `<<LEAD:...>>`) → уведомление в Telegram
- `memory.py` — резюмирование диалога в `client.summary` (память между обращениями)
- `main.py` — вебхуки + CRM API (`/api/clients`, поиск/фильтр/редактирование)

## Деплой
Coolify на Hetzner, деплой из GitHub по `git push` (Dockerfile + docker-compose.yml в репозитории).

## Правила кода
- Комментарии — на русском, только там, где неочевидно "почему"
- Без debug-принтов в финальном коде
- Секреты — только через `.env`, никогда не коммитить
