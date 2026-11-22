"""Mistral adapter with an injected client (no SDK, no network)."""

import json
from types import SimpleNamespace

import pytest

from kaavamaaraysavustaja.core.llm import LLMError, LLMTruncated, StructuredRequest
from kaavamaaraysavustaja.core.llm.mistral import MistralProvider
from kaavamaaraysavustaja.core.llm.providers import ProviderUnavailable, create_provider

SCHEMA = {
    "type": "object",
    "properties": {"ryhmat": {"type": "array"}},
    "required": ["ryhmat"],
    "additionalProperties": False,
}


def request():
    return StructuredRequest(
        system="ohje", static_context="konteksti", task_input="tehtävä", json_schema=SCHEMA
    )


class Chat:
    def __init__(self, texts, finish="stop"):
        self.texts = list(texts)
        self.finish = finish
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        text = self.texts.pop(0)
        return SimpleNamespace(
            model="mistral-large-2511",
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
            choices=[SimpleNamespace(finish_reason=self.finish, message=SimpleNamespace(content=text))],
        )


def provider(*texts, finish="stop"):
    chat = Chat(texts, finish)
    return MistralProvider(client=SimpleNamespace(chat=chat)), chat


def test_request_parameters():
    p, chat = provider('{"ryhmat": []}')
    response = p.generate_structured(request())
    call = chat.calls[0]
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["messages"][0]["role"] == "system" and "konteksti" in call["messages"][0]["content"]
    assert call["temperature"] == 0
    assert response.data == {"ryhmat": []}
    assert response.usage.input_tokens == 100 and response.usage.output_tokens == 20
    assert response.model_id == "mistral-large-2511"
    json.dumps(call["response_format"])


def test_one_repair_round_for_invalid_json():
    p, chat = provider("ei jsonia", '{"ryhmat": []}')
    response = p.generate_structured(request())
    assert len(chat.calls) == 2 and response.warnings
    assert chat.calls[1]["messages"][-1]["role"] == "user"
    assert response.usage.input_tokens == 200


def test_schema_violation_is_repaired_or_fails():
    pytest.importorskip("jsonschema")
    p, chat = provider('{"muu": 1}', '{"ryhmat": []}')
    assert p.generate_structured(request()).data == {"ryhmat": []}
    p, chat = provider('{"muu": 1}', '{"muu": 2}')
    with pytest.raises(LLMError):
        p.generate_structured(request())


def test_truncated():
    p, _ = provider('{"ryh', finish="length")
    with pytest.raises(LLMTruncated):
        p.generate_structured(request())


def test_missing_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    try:
        import mistralai.client  # noqa: F401
    except ImportError:
        with pytest.raises(ProviderUnavailable):
            create_provider("mistral")
    else:
        with pytest.raises(LLMError, match="MISTRAL_API_KEY"):
            create_provider("mistral")


@pytest.mark.live
def test_live_mistral_minimal():
    import os

    if not os.environ.get("MISTRAL_API_KEY"):
        pytest.skip("MISTRAL_API_KEY puuttuu")
    p = create_provider("mistral")
    assert "ryhmat" in p.generate_structured(request()).data
