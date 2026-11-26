"""Hybrid pipeline in drafting mode and cancellation (ADR-0017), test adapter only."""

import json

from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.decisions import parse_decisions
from kaavamaaraysavustaja.core.hybrid import HybridSettings, run_hybrid
from kaavamaaraysavustaja.core.ingest import single_unit
from kaavamaaraysavustaja.core.llm.budget import Budget
from kaavamaaraysavustaja.core.llm.fake import FakeProvider

TEXT = (
    "Alueelle saa rakentaa enintään 12 000 k-m² asuin- ja liiketilaa.\n\n"
    "Pihoille suositellaan hulevesiä viivyttäviä ratkaisuja."
)


def responder(*, quantity_value=None, solve_k13=None, with_quantity=True):
    def respond(request):
        task = json.loads(request.task_input)
        unit = task["yksikko"]
        regs = [
            {
                "laji": "asuinalue",
                "arvo": None,
                "lisatiedot": [{"laji": "paakayttotarkoitus", "arvo": None}],
                "sanallisen_lajit": [],
                "tekstiviitteet": [],
            }
        ]
        if with_quantity:
            regs.append(
                {
                    "laji": "sallittuKerrosala",
                    "arvo": quantity_value,
                    "lisatiedot": [],
                    "sanallisen_lajit": [],
                    "tekstiviitteet": ["12 000 k-m²"],
                }
            )
        regs.append(
            {
                "laji": "sanallinenMaarays",
                "arvo": unit["teksti"],
                "lisatiedot": [],
                "sanallisen_lajit": ["rakentamistapa", "hulevedet"],
                "tekstiviitteet": [],
            }
        )
        solved = []
        if solve_k13:
            solved.append(
                {
                    "tunnus": f"{unit['tunnus']}-K13",
                    "valinta": solve_k13,
                    "peruste": "suositus",
                    "lainaus": "",
                }
            )
        return {
            "ryhmat": [
                {
                    "otsikko": unit["otsikko"],
                    "kirjaintunnus": unit["kirjaintunnus"],
                    "ryhmatyyppi": "kaavakohde",
                    "geometria": ["alue"],
                    "maaraykset": regs,
                    "suositukset": [],
                }
            ],
            "perustelut": [],
            "vaihtoehdot": [],
            "tulkintakysymykset": [],
            "ratkaistut_kysymykset": solved,
            "kokonaisvarmuus": "keskitaso",
        }

    return respond


def drafting_project(kb, policies, text=TEXT, decisions=None, n=1):
    units = [
        single_unit("Asuntoalue", text if n == 1 else f"{text} ({i})", letter_code="A", unit_id=f"u{i:03d}")
        for i in range(1, n + 1)
    ]
    return convert_units(kb, units, policies.resolve(), mode="laadinta", name="laadinta", decisions=decisions)


def run(kb, project, provider, **kwargs):
    return run_hybrid(kb, project, HybridSettings(provider, "claude-opus-5-5", Budget(None), **kwargs))


def test_rule_based_quantity_kept_with_its_value(kb, policies):
    project = drafting_project(kb, policies)
    run(kb, project, FakeProvider(responder()))
    p = project.units[0].proposal
    quantity = next(r for r in p.regulations if r.type.value == "sallittuKerrosala")
    assert quantity.value.number == 12000 and quantity.value.unit == "k-m²"
    assert not [r for r in p.rule_results if r.rule_id == "R-04"]


def test_rule_based_quantity_added_when_model_omits_it(kb, policies):
    project = drafting_project(kb, policies)
    run(kb, project, FakeProvider(responder(with_quantity=False)))
    p = project.units[0].proposal
    assert [r.value.number for r in p.regulations if r.type.value == "sallittuKerrosala"] == [12000]


def test_model_k13_answer_makes_a_recommendation(kb, policies):
    project = drafting_project(kb, policies)
    run(kb, project, FakeProvider(responder(solve_k13="suositus")))
    p = project.units[0].proposal
    k13 = next(q for q in p.questions if q.kind == "K13")
    assert k13.answer == "suositus" and k13.resolved_by == "kielimalli"
    assert [r.text["fin"] for r in p.recommendations] == [
        "Pihoille suositellaan hulevesiä viivyttäviä ratkaisuja."
    ]
    verbal = [r for r in p.regulations if r.value and r.value.data_type == "LocalizedText"]
    assert [r.value.text["fin"] for r in verbal] == [TEXT.split("\n\n")[0]]
    assert {v.value for v in verbal[0].verbal_types} == {"rakentamistapa", "hulevedet"}


def test_user_k13_answer_survives_hybrid(kb, policies):
    decisions = parse_decisions([{"kysymys": "u001-K13", "valinta": "suositus"}])
    project = drafting_project(kb, policies, decisions=decisions)
    run_hybrid(
        kb,
        project,
        HybridSettings(FakeProvider(responder()), "claude-opus-5-5", Budget(None)),
        decisions,
    )
    p = project.units[0].proposal
    assert len(p.recommendations) == 1
    assert next(q for q in p.questions if q.kind == "K13").resolved_by == "kayttaja"


def test_should_stop_skips_the_remaining_units(kb, policies):
    project = drafting_project(kb, policies, text="Alueella tulee säilyttää puusto.", n=3)
    provider = FakeProvider(responder(with_quantity=False))
    calls = {"n": 0}

    def stop():
        calls["n"] += 1
        return len(provider.requests) >= 1

    report = run(kb, project, provider, should_stop=stop)
    assert [o.status for o in report.outcomes] == ["kielimalli", "keskeytetty", "keskeytetty"]
    assert len(provider.requests) == 1
    assert report.totals()["keskeytettyja"] == 2
