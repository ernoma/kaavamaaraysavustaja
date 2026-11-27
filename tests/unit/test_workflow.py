"""QGIS-free workflow behind the QGIS dock (ADR-0017): input → conversion → decisions → export."""

import json

import pytest

from kaavamaaraysavustaja.core import workflow
from kaavamaaraysavustaja.core.llm.fake import FakeProvider
from kaavamaaraysavustaja.core.model import ConversionProject

LEGEND = """\
@kartta Kartta 1 - Yhdyskuntarakenne
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille.
c-1 TÄYDENTYVÄ KESKUSTA
Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
"""


def single(**kwargs):
    base = dict(
        text="Alueelle saa rakentaa enintään 6 000 k-m² pientaloja.\n\nPihoille suositellaan hulevesien viivytystä.",
        heading="Pientalovaltainen asuntoalue",
        mode="laadinta",
    )
    return workflow.ConversionRequest(**{**base, **kwargs})


def test_single_regulation_drafting(kb):
    project = workflow.rule_based(kb, single())
    assert project.meta.mode == "laadinta" and project.meta.plan_level == "yleiskaava"
    assert len(project.units) == 1
    p = project.units[0].proposal
    assert {r.type.value for r in p.regulations} >= {"asuinpientaloalue", "sallittuKerrosala"}
    assert project.sources[0].sha256 and project.sources[0].title == "Telakan syöte"


def test_legend_input_vooka(kb):
    project = workflow.rule_based(kb, workflow.ConversionRequest(text=LEGEND, heading=None, legend=True))
    assert [u.heading for u in project.units] == ["KESKUSTATOIMINTOJEN ALUE", "TÄYDENTYVÄ KESKUSTA"]
    assert project.meta.mode == "vooka"


def test_empty_input_is_an_error(kb):
    with pytest.raises(workflow.InputError):
        workflow.rule_based(kb, workflow.ConversionRequest(text="  ", heading=""))


def test_policy_choices_and_defaults(kb):
    options = workflow.policy_options(kb)
    l03 = next(o for o in options if o.id == "L-03")
    assert l03.default == "ei_pilkota" and "kappaleittain" in l03.options and not l03.locked
    assert "aiheittain" not in l03.options  # not implemented in the rule-based conversion
    project = workflow.rule_based(kb, single(overrides={"L-03": "kappaleittain"}))
    assert project.policy("L-03") == "kappaleittain"


def test_status_icons(kb):
    project = workflow.rule_based(kb, single())
    unit = project.units[0]
    assert workflow.unit_status(unit) in workflow.STATUS_ICONS
    if unit.proposal.results("virhe"):
        assert workflow.unit_status(unit) == "virhe"  # errors first
    unit.proposal.rule_results = []
    assert workflow.unit_status(unit) == "kysymys"  # K13 open
    assert workflow.unit_label(unit).startswith("? ")


def test_decision_and_rerun_keep_answers(kb):
    request = single()
    project = workflow.rule_based(kb, request)
    unit = project.units[0]
    k13 = next(q for q in unit.proposal.questions if q.kind == "K13")
    decision = workflow.decision_for(unit, k13, "suositus", scope="merkinta", basis="testi")
    assert decision.heading == unit.heading and decision.by == "paikkatietoasiantuntija"
    request.decisions = workflow.add_decision(request.decisions, decision)
    again = workflow.rule_based(kb, request)
    p = again.units[0].proposal
    assert next(q for q in p.questions if q.kind == "K13").resolved_by == "kayttaja"
    assert len(p.recommendations) == 1
    assert [d.kind for d in again.decisions] == ["K13"]
    # A newer decision for the same question replaces the older one.
    request.decisions = workflow.add_decision(
        request.decisions, workflow.decision_for(unit, k13, "maarays", scope="merkinta")
    )
    assert [d.option for d in request.decisions] == ["maarays"]


def test_scope_similar_is_project(kb):
    project = workflow.rule_based(kb, workflow.ConversionRequest(text=LEGEND, legend=True))
    unit = project.units[1]
    q = unit.proposal.questions[0]
    assert (
        workflow.decision_for(unit, q, q.options[0].id if q.options else "x", scope="projekti").scope
        == "projekti"
    )


def test_estimate_and_preview(kb):
    project = workflow.rule_based(kb, single())
    plan = workflow.llm_plan(kb, project, "claude")
    assert plan.estimate.units == 1 and plan.estimate.usd > 0
    assert plan.model == "claude-opus-5-5"
    preview = workflow.request_preview(kb, project)
    assert "Pientalovaltainen asuntoalue" in preview and "## Järjestelmäohje" in preview
    assert "Laadintatila" in preview


def test_llm_run_with_fake_provider_and_reuse(kb):
    request = single()
    project = workflow.rule_based(kb, request)

    def respond(req):
        task = json.loads(req.task_input)
        return {
            "ryhmat": [
                {
                    "otsikko": "Pientalovaltainen asuntoalue",
                    "kirjaintunnus": "AP",
                    "ryhmatyyppi": "kaavakohde",
                    "geometria": ["alue"],
                    "maaraykset": [
                        {
                            "laji": "asuinpientaloalue",
                            "arvo": None,
                            "lisatiedot": [{"laji": "paakayttotarkoitus", "arvo": None}],
                            "sanallisen_lajit": [],
                            "tekstiviitteet": [],
                        },
                        {
                            "laji": "sanallinenMaarays",
                            "arvo": task["yksikko"]["teksti"],
                            "lisatiedot": [],
                            "sanallisen_lajit": ["rakennusoikeus"],
                            "tekstiviitteet": [],
                        },
                    ],
                    "suositukset": [],
                }
            ],
            "perustelut": [],
            "vaihtoehdot": [],
            "tulkintakysymykset": [],
            "ratkaistut_kysymykset": [],
            "kokonaisvarmuus": "keskitaso",
        }

    provider = FakeProvider(respond)
    report = workflow.run_llm(
        kb, project, provider, "claude-opus-5-5", budget=1.0, decisions=request.decisions
    )
    assert report.totals()["kutsuja"] == 1
    # Re-run: the earlier answer is reused without a call.
    again = workflow.rule_based(kb, request)
    plan = workflow.llm_plan(kb, again, "claude", previous=project)
    assert plan.reuse and plan.estimate.units == 0
    workflow.run_llm(kb, again, provider, plan.model, budget=1.0, reuse=plan.reuse)
    assert len(provider.requests) == 1


def test_llm_availability_without_sdk_or_key(monkeypatch):
    monkeypatch.setattr(workflow, "sdk_available", lambda name: False)
    assert "SDK" in workflow.llm_unavailable_reason("claude", key="x")
    monkeypatch.setattr(workflow, "sdk_available", lambda name: True)
    assert "avain" in workflow.llm_unavailable_reason("claude", key=None)
    assert workflow.llm_unavailable_reason("claude", key="x") is None


def test_export_all_formats(kb, tmp_path):
    project = workflow.rule_based(kb, single())
    paths = workflow.export(
        kb, project, tmp_path, "uusi", ["projekti", "markdown", "html", "ryhti", "arho"]
    ).paths
    assert set(paths) == {"projekti", "markdown", "html", "ryhti", "arho"}
    assert ConversionProject.load(paths["projekti"]).units[0].heading == "Pientalovaltainen asuntoalue"
    ryhti = json.loads(paths["ryhti"].read_text(encoding="utf-8"))
    assert ryhti["planRegulationGroups"]
    assert "Muunnosraportti" in paths["markdown"].read_text(encoding="utf-8")
    assert "<html" in paths["html"].read_text(encoding="utf-8").lower()
    assert workflow.schema_problems(kb, project) == {}


def test_detail_html_shows_structure_rationale_and_technical(kb):
    project = workflow.rule_based(kb, single())
    html = workflow.detail_html(kb, project.units[0])
    assert "Pääkäyttötarkoitus" in html or "Asuinpientaloalue" in html
    assert "http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji/code/asuinpientaloalue" in html
    assert "Perustelut" in html and "Sääntötarkistus" in html and "Varmuus" in html
