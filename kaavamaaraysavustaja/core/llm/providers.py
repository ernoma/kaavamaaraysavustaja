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


def create_provider(name: str, model: str | None = None) -> Any:
    model = model or DEFAULT_MODELS[name]
    try:
        if name == "claude":
            from kaavamaaraysavustaja.core.llm.claude import ClaudeProvider

            return ClaudeProvider(model=model)
        if name == "mistral":
            from kaavamaaraysavustaja.core.llm.mistral import MistralProvider

            return MistralProvider(model=model)
    except ImportError as error:
        raise ProviderUnavailable(
            f'Kielimallin {name} SDK ({SDK[name]}) puuttuu: asenna pip install -e ".[llm]" ({error}).'
        ) from error
    raise ProviderUnavailable(f"Tuntematon kielimalli {name!r}; vaihtoehdot: {', '.join(PROVIDERS)}")
