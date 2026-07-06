import base64

import httpx

from app.config import settings

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)


def transcribe_voice(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """Расшифровывает голосовое через Gemini. Возвращает None при сбое
    (лимит 429, ошибка сети и т.п.) — чтобы сбой не ронял обработчик вебхука."""
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Расшифруй это голосовое сообщение в текст на русском языке. Верни только текст, без комментариев."},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(audio_bytes).decode(),
                        }
                    },
                ]
            }
        ]
    }

    try:
        response = httpx.post(
            GEMINI_URL,
            params={"key": settings.gemini_api_key},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (httpx.HTTPError, KeyError, IndexError):
        return None
