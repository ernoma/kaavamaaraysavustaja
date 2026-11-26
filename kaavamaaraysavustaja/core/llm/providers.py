"""Provider selection by name (``kma convert --kielimalli claude|mistral``).

The adapters import their SDKs only when created, so this module is safe to import without
``anthropic`` or ``mistralai`` installed.
"""

from __future__ import annotations

from typing import Any

from kaavamaaraysavustaja.core.llm.base import LLMError

PROVIDERS = ("claude", "mistral")
DEFAULT_MODELS = {"claude": "claude-opus-5-5", "mistral": "mistral-large-latest"}
SDK = {"claude": "anthropic", "mistral": "mistralai"}


class ProviderUnavailable(LLMError):
    pass


def sdk_available(name: str) -> bool:
    """Is the SDK of the provider importable (without importing it)?"""
    import importlib.util

    module = SDK.get(name)
    return bool(module and importlib.util.find_spec(module.split(".")[0]) is not None)


def create_provider(name: str, model: str | None = None, *, api_key: str | None = None) -> Any:
    """``api_key=None``: the SDK reads the environment variable (development, ADR-0004)."""
    model = model or DEFAULT_MODELS[name]
    try:
        if name == "claude":
            from kaavamaaraysavustaja.core.llm.claude import ClaudeProvider

            return ClaudeProvider(model=model, api_key=api_key)
        if name == "mistral":
            from kaavamaaraysavustaja.core.llm.mistral import MistralProvider

            return MistralProvider(model=model, api_key=api_key)
    except ImportError as error:
        raise ProviderUnavailable(
            f'Kielimallin {name} SDK ({SDK[name]}) puuttuu: asenna pip install -e ".[llm]" ({error}).'
        ) from error
    raise ProviderUnavailable(f"Tuntematon kielimalli {name!r}; vaihtoehdot: {', '.join(PROVIDERS)}")
