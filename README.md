# AI-консультант — воркер

## Запуск локально

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Заполнить `.env` (ключ Claude API, токен Telegram-бота).

```bash
python -m scripts.seed_tenant
uvicorn app.main:app --reload
```

## Проверка

Тестовое сообщение без внешних каналов:

```bash
curl -X POST http://localhost:8000/test/message \
  -H "Content-Type: application/json" \
  -d "{\"tenant_slug\": \"demo\", \"external_id\": \"tester1\", \"text\": \"Здравствуйте, хочу сайт\"}"
```

CRM API (нужен заголовок `X-API-Key`, значение — `CRM_API_KEY` из `.env`):

```bash
curl http://localhost:8000/api/clients -H "X-API-Key: change-me"
```

## Деплой

Docker Compose (`docker-compose.yml`) — используется Coolify при деплое из GitHub.
