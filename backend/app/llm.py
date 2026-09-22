from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.settings import ModelSettings, load_settings

PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "openai_compat",
        "label": "OpenAI Compatible",
        "hint": "DeepSeek / Qwen / Groq / Moonshot / 任何 /v1 Chat Completions 接口",
        "needs_base_url": True,
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "hint": "官方 OpenAI API",
        "needs_base_url": False,
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
    },
    {
        "id": "anthropic",
        "label": "Anthropic",
        "hint": "Claude 系列",
        "needs_base_url": False,
        "default_base_url": "",
        "default_model": "claude-sonnet-4-5",
    },
    {
        "id": "ollama",
        "label": "Ollama (本地)",
        "hint": "走 OpenAI 兼容层，默认 http://127.0.0.1:11434/v1",
        "needs_base_url": True,
        "default_base_url": "http://127.0.0.1:11434/v1",
        "default_model": "qwen2.5",
    },
]


def build_chat_model(settings: ModelSettings | None = None) -> BaseChatModel:
    settings = settings or load_settings()
    provider = settings.provider
    temperature = settings.temperature
    model = settings.model
    api_key = settings.api_key or "sk-placeholder"
    base_url = settings.base_url.rstrip("/") if settings.base_url else ""

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.api_key or None,
            temperature=temperature,
        )

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key if provider != "ollama" else "ollama",
        "temperature": temperature,
    }
    if provider in {"openai_compat", "ollama"} and base_url:
        kwargs["base_url"] = base_url
    elif provider == "openai" and base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "••••"
    return key[:4] + "••••" + key[-4:]
