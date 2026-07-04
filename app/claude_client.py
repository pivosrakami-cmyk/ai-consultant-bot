from anthropic import Anthropic

from app.config import settings

_client = Anthropic(api_key=settings.claude_api_key)


def ask_claude(system_prompt: str, history: list[dict]) -> str:
    """Отправляет системный промпт и историю сообщений, возвращает текст ответа."""
    response = _client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=system_prompt,
        messages=history,
    )
    return response.content[0].text
