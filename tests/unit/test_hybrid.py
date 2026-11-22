"""Hybrid pipeline with the test adapter (no network, no SDK)."""

import json
from pathlib import Path

import pytest

from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.hybrid import (
    HybridSettings,
    estimate_run,
    needs_model,
    quote_found,
    reuse_from_project,
    run_hybrid,
    unit_key,
)
from kaavamaaraysavustaja.core.ingest import parse
from kaavamaaraysavustaja.core.llm.budget import Budget
from kaavamaaraysavustaja.core.llm.fake import FakeProvider, RecordingProvider, ReplayProvider
from kaavamaaraysavustaja.core.llm.prompts import PromptSet
from kaavamaaraysavustaja.core.model import ConversionProject

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "kartta1_otos.txt"


def model_structure(items):
    """``laji(a,b=c)`` strings → model regulations."""
    out = []
    for item in items:
        code, _, rest = item.partition("(")
        infos = []
        for info in filter(None, rest.rstrip(")").split(",")):
            name, _, value = info.partition("=")
            infos.append({"laji": name, "arvo": value or None})
        out.append(
            {"laji": code, "arvo": None, "lisatiedot": infos, "sanallisen_lajit": [], "tekstiviitteet": []}
        )
    return out


def echo(
    request, *, text=None, verbal=("kehittamisperiaate",), quote=None, questions=(), solve=(), geometry=None
):
    """A model that agrees with the phase 1 structure."""
    task = json.loads(request.task_input)
    unit, phase1 = task["yksikko"], task["vaihe1"]
    regulations = model_structure(phase1["rakenne"])
    if unit["teksti"]:
        regulations.append(
            {
                "laji": "sanallinenMaarays",
                "arvo": text if text is not None else unit["teksti"],
                "lisatiedot": [],
                "sanallisen_lajit": list(verbal),
                "tekstiviitteet": [],
            }
        )
    return {
        "ryhmat": [
            {
                "otsikko": phase1["otsikko"],
                "kirjaintunnus": phase1["kirjaintunnus"],
                "ryhmatyyppi": "yleismaarays" if unit["tyyppi"] == "yleismaarays" else "kaavakohde",
                "geometria": geometry if geometry is not None else phase1["geometria"],
                "maaraykset": regulations,
                "suositukset": [],
            }
        ],
        "perustelut": [
            {
                "vaite": "Rakenne",
                "lainaus": quote if quote is not None else (unit["otsikko"] or ""),
                "tietopohjaviite": "testi",
                "varmuus": "korkea",
            }
        ],
        "vaihtoehdot": [],
        "tulkintakysymykset": list(questions),
        "ratkaistut_kysymykset": list(solve),
        "kokonaisvarmuus": "korkea",
    }


@pytest.fixture()
def project(kb, policies):
    units = parse(GOLDEN.read_text(encoding="utf-8")).units
    return convert_units(kb, units, policies.resolve(), name="testi")


def run(kb, project, responder, budget=None, **kwargs):
    provider = FakeProvider(responder)
    settings = HybridSettings(provider, "claude-opus-5-5", Budget(budget), **kwargs)
    return provider, run_hybrid(kb, project, settings)


def test_only_uncertain_units_go_to_the_model(kb, project):
    selected = [u for u in project.units if needs_model(u)]
    assert selected and len(selected) < len(project.units)
    assert all(u.proposal.confidence != "korkea" and u.proposal.kind != "ei_maarays" for u in selected)
    provider, report = run(kb, project, echo)
    assert len(provider.requests) == len(selected)
    assert report.totals()["kutsuja"] == len(selected)


def test_request_content(kb, project):
    provider, _ = run(kb, project, echo)
    request = provider.requests[0]
    assert "Katja-asetuksen liitteen 4 vakiomääräykset" in request.static_context
    assert "K2 Sekoittunut käyttötarkoitus" in request.static_context
    assert "L-15" in request.static_context
    assert "eheytettavaTaiTiivistettava" in request.static_context  # the policy on additional infos
    task = json.loads(request.task_input)
    assert {"yksikko", "vaihe1", "avoimet_kysymykset", "ratkaistut", "esimerkit"} <= set(task)
    assert request.metadata["kehote"] == "prompts/v1 v1"
    assert len({r.static_context for r in provider.requests}) == 1  # identical prefix -> cache hits
    assert "%PDF" not in request.task_input


def test_verbal_text_always_comes_from_the_source(kb, project):
    run(kb, project, lambda r: echo(r, text="Muutettu teksti."))
    for unit in project.units:
        assert not [r for r in unit.proposal.rule_results if r.rule_id == "R-19" and r.severity == "virhe"]
        if unit.normalized_text and unit.proposal.kind != "ei_maarays":
            verbal = [
                r for r in unit.proposal.regulations if r.value and r.value.data_type == "LocalizedText"
            ]
            assert "\n\n".join(r.value.text["fin"] for r in verbal) == unit.normalized_text


def test_agreement_without_open_questions_is_high(kb, project):
    run(kb, project, lambda r: echo(r, solve=[]))
    sent = [u for u in project.units if u.proposal.model_check]
    assert sent
    for unit in sent:
        p = unit.proposal
        if (
            p.model_check["yhtapitava"]
            and not p.open_questions()
            and not p.results("virhe")
            and not p.results("varoitus")
        ):
            assert p.confidence == "korkea", unit.id
        if p.open_questions():
            assert p.confidence == "matala"


def test_quote_not_in_source_rejects_rationale_and_lowers_confidence(kb, project):
    run(kb, project, lambda r: echo(r, quote="tätä lausetta ei ole lähteessä"))
    sent = [u for u in project.units if u.proposal.model_check]
    for unit in sent:
        assert unit.proposal.confidence == "matala"
        assert any(r.claim.startswith("Hylätty perustelu") for r in unit.proposal.rationale)


def test_quote_check():
    from kaavamaaraysavustaja.core.model import SourceUnit

    unit = SourceUnit(
        "u1", "merkinta", "a", "Alue varataan  palveluille.", heading="TESTI ALUE", letter_code="T"
    )
    assert quote_found("Alue varataan palveluille", unit)
    assert quote_found('"Alue varataan palveluille."', unit)
    assert quote_found("T TESTI ALUE", unit)
    assert quote_found("", unit)
    assert not quote_found("Alue varataan asunnoille", unit)


def test_model_questions_are_merged_without_duplicates(kb, project):
    k1 = next(u for u in project.units if any(q.kind == "K1" for q in u.proposal.questions))
    question = {
        "tyyppi": "K1",
        "kysymys": "Aluevaraus vai osa-alue?",
        "vaihtoehdot": [{"kuvaus": "osa-alue", "seuraus": ""}, {"kuvaus": "aluevaraus", "seuraus": ""}],
        "suositus": "osa-alue",
        "peruste": "pienaakkonen tunnus",
    }
    run(kb, project, lambda r: echo(r, questions=[question]))
    kinds = [q.kind for q in k1.proposal.questions]
    assert kinds.count("K1") == 1
    assert "Kielimalli:" in next(q for q in k1.proposal.questions if q.kind == "K1").basis


def test_model_can_settle_geometry_but_not_k1(kb, project):
    k8 = [u for u in project.units if any(q.kind == "K8" and q.is_open for q in u.proposal.questions)]
    k1 = [u for u in project.units if any(q.kind == "K1" and q.is_open for q in u.proposal.questions)]
    assert k8 and k1
    run(kb, project, lambda r: echo(r, geometry=["viiva"]))
    for unit in k8:
        q = next(q for q in unit.proposal.questions if q.kind == "K8")
        assert q.answer == "viiva" and q.resolved_by == "kielimalli"
    for unit in k1:
        assert next(q for q in unit.proposal.questions if q.kind == "K1").is_open


def test_budget_limit_stops_calls(kb, project):
    before = {u.id: u.proposal for u in project.units}
    provider, report = run(kb, project, echo, budget=0.0)
    assert provider.requests == []
    assert report.totals()["budjetin_takia_ohitettuja"] > 0
    assert all(project.unit(i).proposal is p for i, p in before.items())


def test_estimate(kb, project):
    est = estimate_run(kb, project, "claude-opus-5-5", cached=True)
    assert est.units > 0 and est.static_tokens > 10000
    assert 0 < est.usd < 0.2 * est.units
    uncached = estimate_run(kb, project, "mistral-large-latest", cached=False)
    assert uncached.static_tokens == est.static_tokens


def test_record_replay_and_reuse(kb, policies, tmp_path):
    def fresh():
        units = parse(GOLDEN.read_text(encoding="utf-8")).units
        return convert_units(kb, units, policies.resolve(), name="testi")

    first = fresh()
    recorder = RecordingProvider(FakeProvider(echo))
    run_hybrid(kb, first, HybridSettings(recorder, "claude-opus-5-5", Budget(None)))
    path = tmp_path / "rec.json"
    recorder.save(path, kehote="prompts/v1 v1")
    replayed = fresh()
    run_hybrid(kb, replayed, HybridSettings(ReplayProvider.from_file(path), "claude-opus-5-5", Budget(None)))
    assert [u.proposal.confidence for u in first.units] == [u.proposal.confidence for u in replayed.units]

    loaded = ConversionProject.from_json(first.to_json())
    reuse = reuse_from_project(loaded, PromptSet.load(kb).label)
    assert set(reuse) == {unit_key(u) for u in first.units if u.proposal.model_check}
    again = fresh()
    provider = FakeProvider(echo)
    report = run_hybrid(kb, again, HybridSettings(provider, "claude-opus-5-5", Budget(0.0), reuse=reuse))
    assert provider.requests == [] and report.totals()["uudelleenkaytettyja"] > 0


def test_project_round_trip_with_model_check(kb, project):
    run(kb, project, echo)
    assert ConversionProject.from_json(project.to_json()) == project
