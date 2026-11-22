"""Rule engine v1: a passing and a failing case for every rule R-01–R-20 (plan 10.1)."""

import pytest

from kaavamaaraysavustaja.core.model import (
    AdditionalInfo,
    CodeRef,
    GroupProposal,
    Recommendation,
    Regulation,
    SourceUnit,
    Value,
)
from kaavamaaraysavustaja.core.rules import RuleEngine
from kaavamaaraysavustaja.core.rules.checks import CHECKS

U = "http://uri.suomi.fi/codelist/rytj/"
TEXT = "Aluetta kehitetään."


def t(code):
    return CodeRef(U + "RY_Kaavamaarayslaji/code/" + code)


def i(code, value=None):
    return AdditionalInfo(
        CodeRef(U + "RY_Kaavamaarayksen_Lisatiedonlaji/code/" + code),
        Value("Code", code=t(value)) if value else None,
    )


def v(code):
    return CodeRef(U + "RY_Sanallisen_Kaavamaarayksen_Laji/code/" + code)


def verbal(text=TEXT, kinds=("kehittamisperiaate",), type_code="sanallinenMaarays"):
    return Regulation(
        "s",
        t(type_code),
        Value("LocalizedText", text={"fin": text}),
        [],
        [v(k) for k in kinds],
        (0, len(text)),
    )


def reg(code, *infos, value=None):
    return Regulation("r", t(code), value, list(infos))


def unit(
    *regulations,
    kind="kaavakohde",
    geometry=("alue",),
    letter="C",
    title="Keskustatoimintojen alue",
    text=TEXT,
    recommendations=(),
):
    proposal = GroupProposal(
        "g",
        kind,
        {"fin": title},
        letter,
        list(geometry),
        regulations=list(regulations),
        recommendations=list(recommendations),
    )
    return SourceUnit(
        "u1", "merkinta" if kind != "yleismaarays" else "yleismaarays", text, text, proposal=proposal
    )


@pytest.fixture(scope="module")
def engine(kb):
    return RuleEngine(kb)


def results(engine, u, rule_id, mode="vooka"):
    return [r for r in engine.check(u, plan_level="yleiskaava", mode=mode) if r.rule_id == rule_id]


def severities(engine, u, rule_id):
    return [r.severity for r in results(engine, u, rule_id)]


GOOD = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), verbal())


def test_every_rule_has_a_check(kb):
    assert {r["tarkistus"] for r in kb.rules["saannot"]} <= set(CHECKS)
    assert [r["tunnus"] for r in kb.rules["saannot"]] == [f"R-{n:02d}" for n in range(1, 21)]


def test_good_group_has_no_findings(engine):
    found = engine.check(GOOD, plan_level="yleiskaava", mode="vooka")
    assert [(r.rule_id, r.severity) for r in found if r.severity != "huomio"] == []


def test_r01_codes(engine):
    assert severities(engine, unit(reg("eiOlemassa"), verbal()), "R-01") == ["virhe"]
    retired = unit(reg("muuArkeologinenKohde", i("osaAlue")), verbal())
    assert severities(engine, retired, "R-01") == ["virhe"]
    # Syke does not check the plan level extension: a warning, not an error.
    assert severities(engine, unit(reg("asuinpientaloalue", i("paakayttotarkoitus")), verbal()), "R-01") == []
    town_plan_only = unit(reg("rautatienSuojaAlue", i("osaAlue")), verbal(), letter="x")
    assert severities(engine, town_plan_only, "R-01") == ["varoitus"]
    other = unit(
        reg(
            "rakennuspaikka",
            AdditionalInfo(
                CodeRef(U + "RY_Kaavamaarayksen_Lisatiedonlaji/code/rakennusluvanPeruste"),
                Value("Code", code=CodeRef(U + "oikeusvaik_YK/code/12")),
            ),
        )
    )
    assert "huomio" in severities(engine, other, "R-01")
    assert severities(engine, GOOD, "R-01") == []


def test_r02_header_level(engine):
    assert severities(engine, unit(reg("keskustatoimintojenAlue", i("tyyppi")), verbal()), "R-02") == [
        "virhe"
    ]
    assert severities(engine, GOOD, "R-02") == []


def test_r03_verbal_types(engine):
    assert severities(
        engine, unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), verbal(kinds=())), "R-03"
    ) == ["virhe"]
    wrong = reg("keskustatoimintojenAlue", i("paakayttotarkoitus"))
    wrong.verbal_types = [v("liikenne")]
    assert severities(engine, unit(wrong, verbal()), "R-03") == ["virhe"]
    assert severities(engine, GOOD, "R-03") == []


def test_r04_r05_quantity(engine):
    ok = unit(
        reg("keskustatoimintojenAlue", i("paakayttotarkoitus")),
        reg("sallittuKerrosala", value=Value("PositiveNumeric", number=70000, unit="k-m2")),
        verbal(),
    )
    assert severities(engine, ok, "R-04") == []
    missing = unit(
        reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), reg("sallittuKerrosala"), verbal()
    )
    assert severities(engine, missing, "R-04") == ["virhe"]
    extra = unit(
        reg("keskustatoimintojenAlue", i("paakayttotarkoitus")),
        reg("sallittuKerrosala", i("uusi"), value=Value("PositiveNumeric", number=1)),
        verbal(),
    )
    assert severities(engine, extra, "R-05") == ["virhe"]
    assert severities(engine, ok, "R-05") == []


def test_r06_use_class_target(engine):
    bad = unit(reg("kehittamisvyohyke", i("osaAlue"), i("kayttotarkoituskohdistus")), verbal(), letter="c-1")
    assert severities(engine, bad, "R-06") == ["virhe"]
    good = unit(
        reg("kehittamisvyohyke", i("osaAlue"), i("kayttotarkoituskohdistus", "keskustatoimintojenAlue")),
        verbal(),
        letter="c-1",
    )
    assert severities(engine, good, "R-06") == []


def test_r07_main_use(engine):
    assert severities(
        engine, unit(reg("raitiotie", i("paakayttotarkoitus")), geometry=("alue",)), "R-07"
    ) == ["virhe"]
    assert severities(engine, GOOD, "R-07") == []


def test_r08_same_additional_info(engine):
    mixed = unit(
        reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), reg("virkistysalue", i("osaAlue")), verbal()
    )
    assert severities(engine, mixed, "R-08") == ["virhe"]
    point = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), geometry=("piste",))
    assert severities(engine, point, "R-08") == ["virhe"]
    unknown = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), geometry=())
    assert severities(engine, unknown, "R-08") == ["huomio"]
    assert severities(engine, GOOD, "R-08") == []


def test_r09_not_only_verbal(engine):
    assert severities(engine, unit(verbal()), "R-09") == ["virhe"]
    assert severities(engine, GOOD, "R-09") == []


def test_r10_general_group(engine):
    bad = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), kind="yleismaarays", letter=None)
    assert severities(engine, bad, "R-10") == ["virhe"]
    assert severities(engine, unit(kind="yleismaarays", letter=None), "R-10") == ["virhe"]  # empty
    assert severities(engine, unit(verbal(), kind="yleismaarays", letter=None), "R-10") == []


def test_r11_letter_code(engine):
    assert severities(
        engine, unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), verbal(), letter=None), "R-11"
    ) == ["virhe"]
    assert severities(engine, GOOD, "R-11") == []


def test_r12_development_zone(engine):
    no_text = unit(reg("kehittamisvyohyke", i("osaAlue")), letter="k", text="")
    assert severities(engine, no_text, "R-12") == ["virhe"]
    line = unit(
        reg("kehittamisvyohyke", i("osaAlue")), verbal(type_code="suunnittelumaarays"), geometry=("viiva",)
    )
    assert severities(engine, line, "R-12") == ["virhe"]
    upper_code = unit(reg("kehittamisvyohyke", i("osaAlue")), verbal())
    assert severities(engine, upper_code, "R-12") == ["huomio"]  # L-04 sanallinenMaarays
    ok = unit(reg("kehittamisvyohyke", i("osaAlue")), verbal(type_code="suunnittelumaarays"))
    assert severities(engine, ok, "R-12") == []


def test_r13_connection_need(engine):
    area = unit(reg("liikennealue", i("yhteystarve")), geometry=("alue",), letter=None, title="x")
    assert severities(engine, area, "R-13") == ["varoitus"]
    line = unit(reg("liikennealue", i("yhteystarve")), geometry=("viiva",), letter=None, title="x")
    assert severities(engine, line, "R-13") == []


def test_r14_temporary(engine):
    bad = unit(reg("maaraAikainenRakentamisrajoitus", i("osaAlue")), verbal())
    assert severities(engine, bad, "R-14") == ["virhe"]
    good = unit(reg("maaraAikainenRakentamisrajoitus", i("osaAlue"), i("valiaikainenMaarays")), verbal())
    assert severities(engine, good, "R-14") == []


def test_r15_annex_title(engine):
    no_text = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), title="Keskusta", text="")
    assert severities(engine, no_text, "R-15") == ["varoitus"]
    with_text = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), verbal(), title="Keskusta")
    assert severities(engine, with_text, "R-15") == ["huomio"]  # Katja 2 §
    own = unit(
        reg("keskustatoimintojenAlue", i("paakayttotarkoitus"), i("uusi")),
        title="Keskustatoimintojen alue",
        text="",
    )
    assert severities(engine, own, "R-15") == ["varoitus"]
    assert severities(engine, GOOD, "R-15") == []


def test_r16_general_targets(engine):
    text = "Yleiskaavan RA ja R -alueilla yleiskaavaa voidaan käyttää rakentamisen ohjaamiseen."
    general = unit(verbal(text), kind="yleismaarays", letter=None, text=text)
    assert severities(engine, general, "R-16") == ["huomio"]
    assert severities(engine, unit(verbal(), kind="yleismaarays", letter=None), "R-16") == []


def test_r17_recommendation(engine):
    bad = unit(
        *GOOD.proposal.regulations, recommendations=[Recommendation("k", {"fin": "Puusto tulee säilyttää."})]
    )
    assert severities(engine, bad, "R-17") == ["varoitus"]
    good = unit(
        *GOOD.proposal.regulations,
        recommendations=[Recommendation("k", {"fin": "Puusto suositellaan säilytettäväksi."})],
    )
    assert severities(engine, good, "R-17") == []


def test_r18_number_in_text(engine):
    text = "Vähittäiskaupan kerrosalan enimmäismitoitus Kalevassa on 70 000 k-m²."
    found = results(
        engine, unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), verbal(text), text=text), "R-18"
    )
    assert [r.severity for r in found] == ["huomio"] and "Kaleva" in found[0].message
    assert severities(engine, GOOD, "R-18") == []


def test_r19_source_text(engine):
    changed = unit(reg("keskustatoimintojenAlue", i("paakayttotarkoitus")), verbal("Aluetta kehitetään!"))
    assert "virhe" in severities(engine, changed, "R-19")
    assert severities(engine, GOOD, "R-19") == []
    assert results(engine, changed, "R-19", mode="laadinta") == []  # VOOKA only


def test_r20_color(engine):
    bad = unit(*GOOD.proposal.regulations)
    bad.proposal.color_code = "punainen"
    assert severities(engine, bad, "R-20") == ["virhe"]
    good = unit(*GOOD.proposal.regulations)
    good.proposal.color_code = "#A0B1C2"
    assert severities(engine, good, "R-20") == []


def test_ryhti_rule_ids_have_messages(kb):
    for rule in kb.rules["saannot"]:
        for rule_id in rule.get("ryhti") or []:
            assert kb.ryhti_message(rule_id), f"{rule['tunnus']}: {rule_id}"


def test_ryhti_rule_id_normalization(kb):
    from kaavamaaraysavustaja.knowledge.base import normalize_ryhti_rule_id

    assert normalize_ryhti_rule_id("quality__req_planregulationgroup_letteridentifier_not_null") == (
        "quality/req-planregulationgroup-letteridentifier-not-null"
    )
    assert kb.ryhti_message("quality__req_geom_areaobject_additionalinfo_mainuseclass_section_area_mandatory")


def test_vocabulary_codes_exist(kb):
    index = kb.index
    voc = kb.vocabulary
    for entry in voc["maareet"]:
        assert index.get("RY_Kaavamaarayksen_Lisatiedonlaji", entry["lisatieto"]), entry
    for code in voc["sanallisen_lajit"]:
        assert index.get("RY_Sanallisen_Kaavamaarayksen_Laji", code), code
    for code in voc["sanallisen_maarayksen_tyypit"]:
        assert index.get("RY_Kaavamaarayslaji", code), code
    for entry in voc["otsikon_avainsanat"]:
        assert index.get("RY_Kaavamaarayslaji", entry["kaavamaarayslaji"]), entry
    for entry in voc["suureet"]:
        assert index.get("RY_Kaavamaarayslaji", entry["kaavamaarayslaji"]).in_extension("suure"), entry
