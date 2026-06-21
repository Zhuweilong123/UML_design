"""DeepSeek LLM service – wraps OpenAI-compatible API."""

from openai import AsyncOpenAI
from app.core.config import get_settings

settings = get_settings()

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


async def chat(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> str:
    """Single-turn chat completion."""
    client = get_client()
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(
        model=settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


async def chat_with_history(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Multi-turn chat with conversation history."""
    client = get_client()
    response = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
