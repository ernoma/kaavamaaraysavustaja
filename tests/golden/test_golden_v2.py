"""Golden test data v2 (107 units): quality gates for the rule-based and the hybrid conversion.

The hybrid gate replays the responses recorded from a live Claude run
(``tests/recorded_llm/golden_v2_claude.json``), so CI needs no network and no SDK. The
expected results are drafts (``tila: vahvistamaton``); the thresholds are the phase 2 results,
and a change that lowers them must be justified (plan 10.4).
"""

import sys
from pathlib import Path

import pytest
import yaml

from kaavamaaraysavustaja.core.evaluation import combine
from kaavamaaraysavustaja.core.ingest import normalization_preserves_content, parse
from kaavamaaraysavustaja.exporters import ryhti_json
from kaavamaaraysavustaja.validation.schema import validate_fragments

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import evaluate as ev  # noqa: E402

RECORDED = ev.recorded_path("claude")


def test_golden_sets_size_and_status():
    total = 0
    for _, text, expected in ev.GOLDEN_SETS:
        data = yaml.safe_load(expected.read_text(encoding="utf-8"))
        assert data["tila"] == "vahvistamaton"
        result = parse(text.read_text(encoding="utf-8"))
        assert result.warnings == [], text.name
        assert len(result.units) == len(data["yksikot"]), text.name
        total += len(data["yksikot"])
    assert 80 <= total <= 120


def test_expected_codes_exist(kb):
    for _, _, expected in ev.GOLDEN_SETS:
        for item in yaml.safe_load(expected.read_text(encoding="utf-8"))["yksikot"]:
            for option in [item.get("rakenne", []), *item.get("hyvaksyttavat", [])]:
                for structure in option:
                    code, _, rest = structure.partition("(")
                    assert kb.index.get("RY_Kaavamaarayslaji", code), structure
                    for info in filter(None, rest.rstrip(")").split(",")):
                        name, _, value = info.partition("=")
                        assert kb.index.get("RY_Kaavamaarayksen_Lisatiedonlaji", name), structure
                        if value:
                            assert kb.index.get("RY_Kaavamaarayslaji", value), structure
            for verbal in item.get("sanallisen_lajit", []) + item.get("sanallisen_lajit_muut", []):
                assert kb.index.get("RY_Sanallisen_Kaavamaarayksen_Laji", verbal), verbal


@pytest.fixture(scope="module")
def rule_based(kb):
    return ev.rule_based(kb)


def test_rule_based_quality_gate(rule_based):
    _, evaluations = rule_based
    e = combine(evaluations)
    assert e.unmatched == []
    m = e.metrics()
    assert m["ryhmätyyppi oikein"] == (107, 107)
    assert m["pääkoodin osuvuus"][0] >= 50
    assert m["rakenteen osuvuus"][0] >= 47
    assert m["tunnetuista kysymyksistä tunnistettu"][0] >= 75
    hit, total = m["sellaisenaan hyväksyttävistä oikein"]
    assert hit == total and total >= 35
    hit, total = m["korkean varmuuden ehdotuksista oikein"]
    assert hit == total
    assert e.text_changes == 0


@pytest.fixture(scope="module")
def hybrid(kb):
    if not RECORDED.exists():
        pytest.fail(f"{RECORDED.relative_to(ROOT)} puuttuu: aja tools/evaluate.py --hybridi claude --live")
    from kaavamaaraysavustaja.core.llm.budget import Budget

    provider, model = ev.replay_provider("claude")
    return ev.hybrid(kb, provider, model, Budget(None))


def test_hybrid_text_is_source_text_character_by_character(hybrid):
    """R-19 is absolute: 0 changes to the text of the plan in force, also with the model."""
    projects, _ = hybrid
    for project in projects:
        for unit in project.units:
            assert normalization_preserves_content(unit.raw_text, unit.normalized_text, unit.normalization_diff)
            verbal = [r for r in unit.proposal.regulations if r.value and r.value.data_type == "LocalizedText"]
            if unit.normalized_text and unit.proposal.kind != "ei_maarays":
                assert "\n\n".join(r.value.text["fin"] for r in verbal) == unit.normalized_text, unit.id
            assert not [r for r in unit.proposal.rule_results if r.rule_id == "R-19" and r.severity == "virhe"]


def test_hybrid_fragments_pass_schema(kb, hybrid):
    projects, _ = hybrid
    for project in projects:
        assert validate_fragments(ryhti_json.project_fragments(project), kb.load_schema()) == {}


def test_hybrid_uses_recorded_responses_for_every_unit(hybrid):
    projects, _ = hybrid
    for project in projects:
        step = next(s for s in project.provenance if s.step == "kielimalli")
        assert step.details["virheita"] == 0
        assert step.details["kehote"] == "prompts/v2 v2"


HYBRID_GATE = {
    # Phase 2 results with the recorded responses (see docs/vaihe2_raportti.md).
    "hyväksytään sellaisenaan (ehdokas ja oikein)": None,
    "korkean varmuuden ehdotuksista oikein": None,
}


def test_hybrid_quality_gate(hybrid, rule_based):
    _, evaluations = hybrid
    e = combine(evaluations)
    r = combine(rule_based[1])
    m, rm = e.metrics(), r.metrics()
    assert e.unmatched == []
    assert e.text_changes == 0
    assert m["ryhmätyyppi oikein"] == (107, 107)
    # The hybrid must not be worse than the rule-based conversion.
    assert m["rakenteen osuvuus"][0] >= rm["rakenteen osuvuus"][0]
    assert m["hyväksytään sellaisenaan (ehdokas ja oikein)"][0] > rm["hyväksytään sellaisenaan (ehdokas ja oikein)"][0]
    assert e.f1_scores()["sanallisen määräyksen lajit"][2] >= r.f1_scores()["sanallisen määräyksen lajit"][2]
    assert m["tunnetuista kysymyksistä tunnistettu"][0] >= rm["tunnetuista kysymyksistä tunnistettu"][0]
