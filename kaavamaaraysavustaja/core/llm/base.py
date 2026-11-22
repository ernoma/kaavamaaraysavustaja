"""Provider-independent adapter interface (plan chapter 6.8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Quality = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class StructuredRequest:
    system: str  # instructions (stable, cacheable)
    static_context: str  # code lists, annex 4, rule summary (stable, cacheable)
    task_input: str  # the regulation unit to convert (varies per request)
    json_schema: dict[str, Any]  # output schema; code fields are enums
    quality: Quality = "medium"
    max_output_tokens: int = 16000
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(frozen=True)
class StructuredResponse:
    data: dict[str, Any]
    model_id: str
    stop_reason: str
    usage: Usage = Usage()
    warnings: list[str] = field(default_factory=list)


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    """The provider declined the request (e.g. ``stop_reason == "refusal"``)."""


class LLMTruncated(LLMError):
    """The response hit the output token limit; the JSON may be incomplete."""


class LLMProvider(Protocol):
    name: str

    def generate_structured(self, request: StructuredRequest) -> StructuredResponse: ...
