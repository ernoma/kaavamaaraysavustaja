"""Test adapters without network access (deterministic CI).

* :class:`FakeProvider` returns a fixed response or the result of a function.
* :class:`ReplayProvider` returns responses recorded from live runs
  (``tests/recorded_llm/*.json``), keyed by the unit key in ``request.metadata["avain"]``.
* :class:`RecordingProvider` wraps a live provider and collects its responses in the same
  format. Recorded files contain the response, usage and model, never API keys.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kaavamaaraysavustaja.core.llm.base import LLMError, StructuredRequest, StructuredResponse, Usage

RECORD_FORMAT = 1


class FakeProvider:
    name = "fake"
    model = "fake"
    supports_prompt_caching = True

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


def _usage(raw: dict[str, Any] | None) -> Usage:
    raw = raw or {}
    return Usage(
        input_tokens=int(raw.get("input_tokens", 0)),
        output_tokens=int(raw.get("output_tokens", 0)),
        cache_read_input_tokens=int(raw.get("cache_read_input_tokens", 0)),
        cache_creation_input_tokens=int(raw.get("cache_creation_input_tokens", 0)),
    )


class ReplayProvider:
    """Replays recorded responses; the recorded usage is reported so costs can be evaluated."""

    name = "tallennettu"
    supports_prompt_caching = True

    def __init__(self, record: dict[str, Any]):
        self.record = record
        self.model = record.get("malli", "tallennettu")
        self.responses: dict[str, dict[str, Any]] = record.get("vastaukset", {})
        self.requests: list[StructuredRequest] = []

    @classmethod
    def from_file(cls, path: Path) -> ReplayProvider:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        self.requests.append(request)
        key = request.metadata.get("avain", "")
        entry = self.responses.get(key)
        if entry is None:
            raise LLMError(f"Yksikölle {request.metadata.get('yksikko', key)} ei ole tallennettua vastausta.")
        return StructuredResponse(
            data=entry["vastaus"],
            model_id=entry.get("malli", self.model),
            stop_reason=entry.get("stop_reason", "end_turn"),
            usage=_usage(entry.get("kaytto")),
            warnings=list(entry.get("varoitukset", [])),
        )

    def duration(self, key: str) -> float:
        return float(self.responses.get(key, {}).get("kesto_s", 0.0))


class RecordingProvider:
    """Wraps a provider and keeps every response for ``save`` (keys are never recorded).

    ``existing`` responses (an earlier, interrupted recording) are returned without a call;
    with ``autosave`` the record is written after every new response.
    """

    def __init__(
        self,
        inner: Any,
        existing: dict[str, dict[str, Any]] | None = None,
        autosave: Path | None = None,
        meta: dict[str, Any] | None = None,
    ):
        self.inner = inner
        self.name = inner.name
        self.model = getattr(inner, "model", inner.name)
        self.supports_prompt_caching = getattr(inner, "supports_prompt_caching", True)
        self.responses: dict[str, dict[str, Any]] = dict(existing or {})
        self.reused: set[str] = set()
        self.autosave = autosave
        self.meta = dict(meta or {})

    def generate_structured(self, request: StructuredRequest) -> StructuredResponse:
        key = request.metadata.get("avain", "")
        if key in self.responses:
            self.reused.add(key)
            entry = self.responses[key]
            return StructuredResponse(
                data=entry["vastaus"],
                model_id=entry.get("malli", self.model),
                stop_reason=entry.get("stop_reason", "end_turn"),
                usage=Usage(),  # already paid in the earlier run; the record keeps the usage
                warnings=list(entry.get("varoitukset", [])),
            )
        started = time.monotonic()
        response = self.inner.generate_structured(request)
        self.responses[request.metadata.get("avain", str(len(self.responses)))] = {
            "yksikko": request.metadata.get("yksikko"),
            "otsikko": request.metadata.get("otsikko"),
            "malli": response.model_id,
            "stop_reason": response.stop_reason,
            "kaytto": response.usage.__dict__,
            "kesto_s": round(time.monotonic() - started, 1),
            "varoitukset": response.warnings,
            "vastaus": response.data,
        }
        if self.autosave:
            self.save(self.autosave, **self.meta)
        return response

    def record(self, **meta: Any) -> dict[str, Any]:
        return {
            "muoto": RECORD_FORMAT,
            "toimittaja": self.name,
            "malli": self.model,
            **meta,
            "vastaukset": self.responses,
        }

    def save(self, path: Path, **meta: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.record(**meta), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
