"""DeepSeek LLM service – wraps OpenAI-compatible API.

Supports two model tiers:
- ``ModelTier.PRO`` → deepseek-v4-pro (powerful, expensive)
- ``ModelTier.FLASH`` → deepseek-v4-flash (fast, cheap)

Usage::

    from app.services.llm_service import chat, ModelTier
    result = await chat(prompt, model=ModelTier.FLASH.to_model())
"""

from enum import Enum
from openai import AsyncOpenAI
from app.core.config import get_settings

settings = get_settings()

_client: AsyncOpenAI | None = None


class ModelTier(str, Enum):
    """Model tier selector. Use ``.to_model()`` to get the model name string."""
    PRO = "pro"
    FLASH = "flash"

    def to_model(self) -> str:
        """Map tier to the actual model name configured in settings."""
        if self == ModelTier.PRO:
            return settings.deepseek_model
        return settings.deepseek_model_flash


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


def _resolve_model(model: str | ModelTier | None) -> str:
    """Resolve a model specifier to an actual model name string."""
    if model is None:
        return settings.deepseek_model
    if isinstance(model, ModelTier):
        return model.to_model()
    return model


async def chat(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
    model: str | ModelTier | None = None,
) -> str:
    """Single-turn chat completion.

    Args:
        model: Model name or tier. Defaults to ``deepseek-v4-pro`` if omitted.
    """
    client = get_client()
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(
        model=_resolve_model(model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


async def chat_stream(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    model: str | ModelTier | None = None,
):
    """Streaming chat completion. Yields content chunks as they arrive."""
    client = get_client()
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    stream = await client.chat.completions.create(
        model=_resolve_model(model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def chat_with_history(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    model: str | ModelTier | None = None,
) -> str:
    """Multi-turn chat with conversation history."""
    client = get_client()
    response = await client.chat.completions.create(
        model=_resolve_model(model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    tool_choice: str = "auto",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    model: str | ModelTier | None = None,
) -> dict:
    """Multi-turn chat with native Function Calling (tools) support.

    Compatible with DeepSeek and OpenAI APIs.

    Returns:
        dict with:
        - ``content``: str or None — text content from the assistant
        - ``tool_calls``: list[dict] or None — structured tool calls,
          each with ``id``, ``type``, ``function`` (name + arguments JSON string)
    """
    client = get_client()
    response = await client.chat.completions.create(
        model=_resolve_model(model),
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    msg = response.choices[0].message
    result: dict = {"content": msg.content, "tool_calls": None}
    if msg.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return result
