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

## Telegram-канал

После деплоя на Coolify (нужен публичный https-адрес) впиши в `.env` сервера
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_NOTIFY_CHAT_ID`, `GEMINI_API_KEY` (расшифровка голосовых),
`PUBLIC_BASE_URL` (адрес сервера), затем один раз зарегистрируй вебхук:

```bash
python -m scripts.set_telegram_webhook demo
```

После этого бот в Telegram отвечает клиентам через `/webhook/telegram/{tenant_slug}` —
принимает текст и голосовые (расшифровка через Gemini), ведёт по воронке, заявки уходят
уведомлением в `TELEGRAM_NOTIFY_CHAT_ID`.

## Голосовой агент на сайте

Голос собираем не сами — берём готовый сервис (Retell AI или ElevenLabs Agents),
настраиваем в его дашборде системный промпт и сценарий из `Chat bot.md`, а после
завершения звонка сервис шлёт вебхук с транскриптом сюда:

```
POST /webhook/voice/{tenant_slug}
```

Воркер сам прогоняет транскрипт через Claude: пишет резюме в карточку клиента и
определяет, оставил ли клиент контакт (если да — заявка + уведомление в Telegram).
Не зависим от настроек post-call analysis конкретного провайдера — анализ делаем
своим промптом, поэтому эндпоинт одинаково примет вебхук и от Retell, и от ElevenLabs.

В дашборде сервиса нужно указать webhook URL: `https://<PUBLIC_BASE_URL>/webhook/voice/demo`.

## WhatsApp

Meta Business + WhatsApp Cloud API. В `.env` (или в полях тенанта для тиража):
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN` (свой придуманный
секрет — вписываешь тот же в Meta Developer Console).

В настройках вебхука Meta укажи: `https://<PUBLIC_BASE_URL>/webhook/whatsapp/demo` и тот же
verify token — Meta сама дёрнет GET для проверки, эндпоинт уже это умеет.

## Facebook Messenger

Meta Developer Console → Messenger Platform. Нужны `MESSENGER_PAGE_ACCESS_TOKEN` и
`MESSENGER_VERIFY_TOKEN`. Webhook URL: `https://<PUBLIC_BASE_URL>/webhook/messenger/demo`.

## Viber

`VIBER_BOT_TOKEN` (Auth Token бота из Viber admin panel), затем регистрация вебхука:

```bash
python -m scripts.set_viber_webhook demo
```

## Деплой

Docker Compose (`docker-compose.yml`) — используется Coolify при деплое из GitHub.
