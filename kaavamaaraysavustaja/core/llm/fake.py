"""Test adapter: returns recorded responses without network access (deterministic CI)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kaavamaaraysavustaja.core.llm.base import StructuredRequest, StructuredResponse, Usage


class FakeProvider:
    name = "fake"

    def __init__(self, responder: dict[str, Any] | Callable[[StructuredRequest], dict[str, Any]]):
        self._responder = responder
        self.requests: list[StructuredRequest] = []

    @classmethod
    def from_file(cls, path: Path) -> FakeProvider:
        with path.open(encoding="utf-8") as handle:
            return cls(json.load(handle))

    def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        self.requests.append(request)
        data = self._responder(request) if callable(self._responder) else self._responder
        return StructuredResponse(data=data, model_id="fake", stop_reason="end_turn", usage=Usage())
