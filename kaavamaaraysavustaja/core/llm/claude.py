"""Claude adapter (official ``anthropic`` SDK, structured outputs).

Phase 0 spike: one request per regulation unit, JSON output constrained with
``output_config.format`` (code fields are enums), stable context cached with
``cache_control``. Streaming, batches and budget limits follow in phase 2.
"""

from __future__ import annotations

import json
from typing import Any

from kaavamaaraysavustaja.core.llm.base import (
    LLMError,
    LLMRefusal,
    LLMTruncated,
    StructuredRequest,
    StructuredResponse,
    Usage,
)

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeProvider:
    name = "claude"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        api_key: str | None = None,
        client: Any | None = None,
        refusal_fallback: bool = True,
        http_client: Any | None = None,
    ):
        """``client`` can be injected for tests; otherwise ``anthropic.Anthropic`` is created.

        ``api_key=None`` lets the SDK resolve credentials (``ANTHROPIC_API_KEY`` etc.).
        ``http_client`` can carry proxy settings read from QGIS (``anthropic.DefaultHttpxClient``).
        ``refusal_fallback`` enables the server-side refusal fallback (beta) so that a
        declined request is re-run on a fallback model chosen by the API.
        """
        self.model = model
        self.refusal_fallback = refusal_fallback
        if client is None:
            import anthropic  # optional dependency, imported only when the adapter is used

            kwargs: dict[str, Any] = {}
            if api_key:
                kwargs["api_key"] = api_key
            if http_client is not None:
                kwargs["http_client"] = http_client
            client = anthropic.Anthropic(**kwargs)
        self.client = client

    def build_params(self, request: StructuredRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "system": [
                {"type": "text", "text": request.system},
                # Stable context last in the prefix -> cached across regulation units.
                {"type": "text", "text": request.static_context, "cache_control": {"type": "ephemeral"}},
            ],
            "messages": [{"role": "user", "content": request.task_input}],
            "output_config": {
                "effort": request.quality,
                "format": {"type": "json_schema", "schema": request.json_schema},
            },
        }

    def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        params = self.build_params(request)
        if self.refusal_fallback:
            response = self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
        else:
            response = self.client.messages.create(**params)

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMRefusal(f"Kielimalli kieltäytyi (kategoria: {category}).")
        if response.stop_reason == "max_tokens":
            raise LLMTruncated("Vastaus katkesi tulostetokenien rajaan.")
        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            raise LLMError(f"Vastauksessa ei ollut tekstiä (stop_reason={response.stop_reason}).")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Vastaus ei ollut kelvollista JSONia: {exc}") from exc

        usage = response.usage
        warnings = []
        if response.model != self.model:
            warnings.append(f"Vastauksen tuotti varamalli {response.model}.")
        return StructuredResponse(
            data=data,
            model_id=response.model,
            stop_reason=response.stop_reason,
            usage=Usage(
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ),
            warnings=warnings,
        )
