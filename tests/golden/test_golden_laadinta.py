"""Drafting-mode test set (new regulations, synthetic, ADR-0017): quality gates.

The expected results are developer drafts (``tila: vahvistamaton``) and the texts are
synthetic; the user's real examples (docs/kayttajan_tehtavat.md T-02) replace or complement
them. The hybrid gate replays ``tests/recorded_llm/laadinta_claude.json`` (no network, no SDK).
"""

import sys
from pathlib import Path

import pytest
import yaml

from kaavamaaraysavustaja.core.evaluation import combine
from kaavamaaraysavustaja.exporters import ryhti_json
from kaavamaaraysavustaja.validation.schema import validate_fragments

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import evaluate as ev  # noqa: E402

RECORDED = ev.recorded_path("claude", drafting=True)
EXPECTED = ev.DRAFTING_SETS[0][2]


def test_drafting_set_size_and_status():
    data = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))
    assert data["tila"] == "vahvistamaton" and data["muunnostila"] == "laadinta"
    assert 10 <= len(data["yksikot"]) <= 20


def _texts_are_the_users(projects):
    """No rewording: every verbal regulation and recommendation is a span of the user's text."""
    for project in projects:
        for unit in project.units:
            p = unit.proposal
            parts = [r for r in p.regulations if r.value and r.value.data_type == "LocalizedText"]
            for reg in parts:
                start, end = reg.text_span
                assert unit.normalized_text[start:end] == reg.value.text["fin"], unit.id
            for rec in p.recommendations:
                start, end = rec.text_span
                assert unit.normalized_text[start:end] == rec.text["fin"], unit.id
            pieces = sorted([*(r.text_span for r in parts), *(r.text_span for r in p.recommendations)])
            assert "\n\n".join(unit.normalized_text[a:b] for a, b in pieces) == unit.normalized_text


@pytest.fixture(scope="module")
def rule_based(kb):
    return ev.rule_based(kb, ev.DRAFTING_SETS)


def test_rule_based_drafting_gate(kb, rule_based):
    projects, evaluations = rule_based
    e = combine(evaluations)
    assert e.unmatched == []
    m = e.metrics()
    assert m["ryhmätyyppi oikein"] == (16, 16)
    assert m["rakenteen osuvuus"] == (13, 13)
    assert m["kirjaintunnuksen osuvuus"] == (13, 13)
    assert m["tunnetuista kysymyksistä tunnistettu"][0] >= 23
    hit, total = m["sellaisenaan hyväksyttävistä oikein"]
    assert hit == total
    lines = "\n".join(ev.drafting_lines(projects))
    assert "K13: suositus oikein (maarays / suositus) | 3/3" in lines
    assert "suure tunnistettu arvoineen | 3/3" in lines
    _texts_are_the_users(projects)
    for project in projects:
        assert project.meta.mode == "laadinta"
        assert not [r for u in project.units for r in u.proposal.rule_results if r.rule_id == "R-19"]
        assert validate_fragments(ryhti_json.project_fragments(project), kb.load_schema()) == {}


@pytest.fixture(scope="module")
def hybrid(kb):
    if not RECORDED.exists():
        pytest.fail(
            f"{RECORDED.relative_to(ROOT)} puuttuu: aja tools/evaluate.py --laadinta --hybridi claude --live"
        )
    from kaavamaaraysavustaja.core.llm.budget import Budget

    provider, model = ev.replay_provider("claude", drafting=True)
    return ev.hybrid(kb, provider, model, Budget(None), ev.DRAFTING_SETS)


def test_hybrid_drafting_gate(kb, hybrid, rule_based):
    projects, evaluations = hybrid
    e, r = combine(evaluations), combine(rule_based[1])
    m = e.metrics()
    assert e.unmatched == []
    assert m["rakenteen osuvuus"] == (13, 13)
    # Phase 3a results (docs/vaihe3a_raportti.md): 15/16 accepted as such, all high ones correct.
    assert m["hyväksytään sellaisenaan (ehdokas ja oikein)"][0] >= 15
    hit, total = m["korkean varmuuden ehdotuksista oikein"]
    assert hit == total and total >= 15
    assert e.f1_scores()["sanallisen määräyksen lajit"][2] >= r.f1_scores()["sanallisen määräyksen lajit"][2]
    lines = "\n".join(ev.drafting_lines(projects))
    assert "K13: suositus oikein (maarays / suositus) | 3/3" in lines
    assert "suure tunnistettu arvoineen | 3/3" in lines
    _texts_are_the_users(projects)
    for project in projects:
        step = next(s for s in project.provenance if s.step == "kielimalli")
        assert step.details["virheita"] == 0 and step.details["kehote"] == "prompts/v3 v3"
        assert validate_fragments(ryhti_json.project_fragments(project), kb.load_schema()) == {}
