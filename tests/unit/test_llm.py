import json
from types import SimpleNamespace

import pytest

from kaavamaaraysavustaja.core.llm import LLMRefusal, LLMTruncated, StructuredRequest
from kaavamaaraysavustaja.core.llm.claude import ClaudeProvider
from kaavamaaraysavustaja.core.llm.fake import FakeProvider
from kaavamaaraysavustaja.core.llm.schema import code_enums, conversion_schema


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def test_enums_only_contain_usable_codes(index):
    enums = code_enums(index, "yleiskaava")
    assert "keskustatoimintojenAlue" in enums["regulation_types"]
    assert "muuArkeologinenKohde" not in enums["regulation_types"]  # retired
    assert "alueJotaKoskeeKehittamisperiaate" not in enums["regulation_types"]  # header level
    assert "tie" not in enums["regulation_types"]  # not in the yleiskaava extension
    assert "paakayttotarkoitus" in enums["additional_info_types"]
    assert "maarayksenTyyppi" not in enums["verbal_types"]


def test_schema_satisfies_structured_output_rules(index):
    schema = conversion_schema(index, "yleiskaava")
    for node in walk(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
    with pytest.raises(ValueError):
        conversion_schema(index, "kuntakaava")


def request(index):
    return StructuredRequest(
        system="ohje",
        static_context="konteksti",
        task_input="teksti",
        json_schema=conversion_schema(index, "yleiskaava"),
    )


def test_fake_provider_records_requests(index):
    provider = FakeProvider({"ryhmat": []})
    response = provider.generate_structured(request(index))
    assert response.data == {"ryhmat": []}
    assert provider.requests[0].task_input == "teksti"


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_client(stop_reason="end_turn", text='{"ryhmat": []}', model="claude-opus-5-5"):
    response = SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
        usage=SimpleNamespace(
            input_tokens=10, output_tokens=5, cache_read_input_tokens=3, cache_creation_input_tokens=0
        ),
    )
    messages = FakeMessages(response)
    return SimpleNamespace(messages=messages, beta=SimpleNamespace(messages=messages)), messages


def test_claude_request_parameters(index):
    client, messages = fake_client()
    provider = ClaudeProvider(client=client)
    response = provider.generate_structured(request(index))
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "medium"
    assert call["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in call and "temperature" not in call
    assert response.data == {"ryhmat": []}
    assert response.usage.cache_read_input_tokens == 3
    json.dumps(call["output_config"])  # serialisable


def test_claude_without_fallback_uses_plain_endpoint(index):
    client, messages = fake_client()
    ClaudeProvider(client=client, refusal_fallback=False).generate_structured(request(index))
    assert "fallbacks" not in messages.calls[0]


def test_claude_fallback_model_warning(index):
    client, _ = fake_client(model="claude-opus-4-8")
    response = ClaudeProvider(client=client).generate_structured(request(index))
    assert response.warnings


@pytest.mark.parametrize(("stop_reason", "error"), [("refusal", LLMRefusal), ("max_tokens", LLMTruncated)])
def test_claude_stop_reasons(index, stop_reason, error):
    client, _ = fake_client(stop_reason=stop_reason)
    with pytest.raises(error):
        ClaudeProvider(client=client).generate_structured(request(index))
