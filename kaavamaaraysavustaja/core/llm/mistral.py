"""Mistral adapter (official ``mistralai`` SDK, ADR-0005, ADR-0013).

Same interface as the Claude adapter. The output is constrained with a JSON schema
(``response_format`` ``json_schema``, strict). Prompt caching is not assumed, so the cost
estimate counts the static context for every request. If the response is not valid JSON or
does not satisfy the schema, one repair round is made (plan 6.8). The SDK is imported only
when the adapter is created; the key comes from ``MISTRAL_API_KEY`` unless given.
"""

from __future__ import annotations

import json
import os
from typing import Any

from kaavamaaraysavustaja.core.llm.base import (
    LLMError,
    LLMTruncated,
    StructuredRequest,
    StructuredResponse,
    Usage,
)

DEFAULT_MODEL = "mistral-large-latest"


def _schema_errors(data: Any, schema: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # optional (development dependency)
    except ImportError:
        return []
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(juuri)'}: {e.message}"
        for e in validator.iter_errors(data)
    ][:5]


class MistralProvider:
    name = "mistral"
    supports_prompt_caching = False

    def __init__(self, model: str = DEFAULT_MODEL, *, api_key: str | None = None, client: Any | None = None):
        self.model = model
        if client is None:
            from mistralai.client import Mistral  # optional dependency, imported only when used

            key = api_key or os.environ.get("MISTRAL_API_KEY")
            if not key:
                raise LLMError("Mistral-avain puuttuu (ympäristömuuttuja MISTRAL_API_KEY).")
            client = Mistral(api_key=key)
        self.client = client

    def build_params(self, request: StructuredRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": f"{request.system}\n\n{request.static_context}"},
                {"role": "user", "content": request.task_input},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "kaavamaaraysryhma", "schema": request.json_schema, "strict": True},
            },
        }

    def _call(self, params: dict[str, Any]) -> tuple[str, str, Usage, str]:
        response = self.client.chat.complete(**params)
        choice = response.choices[0]
        finish = str(getattr(choice, "finish_reason", "") or "")
        if finish == "length":
            raise LLMTruncated("Vastaus katkesi tulostetokenien rajaan.")
        content = choice.message.content
        if isinstance(content, list):  # content chunks
            content = "".join(getattr(part, "text", "") or "" for part in content)
        usage = getattr(response, "usage", None)
        return (
            content or "",
            finish,
            Usage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            getattr(response, "model", self.model) or self.model,
        )

    def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        params = self.build_params(request)
        text, finish, usage, model = self._call(params)
        warnings: list[str] = []
        problem = None
        data: Any = None
        try:
            data = json.loads(text)
            errors = _schema_errors(data, request.json_schema)
            if errors:
                problem = "Vastaus ei vastannut skeemaa: " + "; ".join(errors)
        except json.JSONDecodeError as exc:
            problem = f"Vastaus ei ollut kelvollista JSONia: {exc}"
        if problem:
            # One repair round (plan 6.8).
            repair = dict(params)
            repair["messages"] = [
                *params["messages"],
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": f"{problem}. Palauta korjattu vastaus skeeman mukaisena JSONina.",
                },
            ]
            text, finish, extra, model = self._call(repair)
            usage = Usage(usage.input_tokens + extra.input_tokens, usage.output_tokens + extra.output_tokens)
            warnings.append(f"Korjauskierros: {problem}")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LLMError(
                    f"Vastaus ei ollut kelvollista JSONia korjauskierroksen jälkeen: {exc}"
                ) from exc
            errors = _schema_errors(data, request.json_schema)
            if errors:
                raise LLMError("Vastaus ei vastannut skeemaa korjauskierroksen jälkeen: " + "; ".join(errors))
        return StructuredResponse(
            data=data, model_id=model, stop_reason=finish or "stop", usage=usage, warnings=warnings
        )
