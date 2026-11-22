"""Rule-based conversion: matching, proposals, questions and policies (plan 6.5, 6.9, 6.10)."""

from kaavamaaraysavustaja.core.convert import convert_units, sentence_case
from kaavamaaraysavustaja.core.ingest import parse

TEXT = """\
@kartta Kartta 1 - Yhdyskuntarakenne
@lahdekaavat Kantakaupungin yleiskaava 2040|20.1.2020
YLEISMÄÄRÄYS
Yleiskaavan ohjausvaikutus
Yleiskaavan RA ja R -alueilla yleiskaavaa voidaan käyttää MRL 72 §:n mukaisesti rakentamisen ohjaamiseen.
MAANKÄYTTÖ
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille. Alueen suunnittelussa tulee kiinnittää huomiota kulttuuriympäristön arvoihin.
c-1 TÄYDENTYVÄ KESKUSTA
Aluetta kehitetään täydennettävänä keskustatoimintojen alueena. Vähittäiskaupan kerrosalan enimmäismitoitus Kalevassa on 70 000 k-m².
R(200) VAPAA-AJAN ASUMISEN JA MATKAILUN ALUE
Rakennuspaikalle saa sijoittaa yhteisöjen käyttöön tarkoitettua lomarakentamista.
VESIALUE
KEHITETTÄVÄ RAUTATIE
Rautatiealueeseen rajautuvissa maankäyttöhankkeissa tulee huomioida lisäraidetarpeet.
ASUMISEN JA VIRKISTYKSEN SEKOITTUNUT ALUE
Aluetta kehitetään nykyisen virkistyskäytön lähtökohdista.
YLEISKAAVA-ALUEEN RAJA
"""


def convert(kb, policies, text=TEXT, **overrides):
    units = parse(text).units
    return convert_units(kb, units, policies.resolve(overrides), name="testi")


def by_heading(project):
    return {u.heading: u for u in project.units}


def codes(regulation):
    return regulation.type.value, [i.type.value for i in regulation.additional_infos]


def test_standard_regulation_from_annex(kb, policies):
    unit = by_heading(convert(kb, policies))["KESKUSTATOIMINTOJEN ALUE"]
    p = unit.proposal
    assert p.title == {"fin": "Keskustatoimintojen alue"}
    assert p.letter_code == "C"  # only a symbol in the source: from annex 4 (L-06)
    assert p.geometry_types == ["alue"]
    assert codes(p.regulations[0]) == ("keskustatoimintojenAlue", ["paakayttotarkoitus"])
    verbal = p.regulations[1]
    assert verbal.type.value == "sanallinenMaarays"  # L-04 default
    assert verbal.value.text["fin"] == unit.normalized_text
    assert verbal.type.uri.startswith("http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji/code/")
    assert verbal.type.codelist_version == kb.index.version("RY_Kaavamaarayslaji")
    assert {v.value for v in verbal.verbal_types} >= {"kulttuuriymparisto"}
    k14 = next(q for q in p.questions if q.kind == "K14")
    assert k14.resolved_by == "linjaus L-06" and not k14.is_open
    assert not p.results("virhe") and not p.open_questions()
    assert p.confidence == "keskitaso"  # letter code and verbal types need confirmation (plan 8.1)
    assert any(r.method == "vakioluettelo" and "rivi" in (r.reference or "") for r in p.rationale)


def test_lowercase_index_is_k1_sub_area(kb, policies):
    p = by_heading(convert(kb, policies))["TÄYDENTYVÄ KESKUSTA"].proposal
    assert p.letter_code == "c-1"
    reg = p.regulations[0]
    assert codes(reg) == ("kehittamisvyohyke", ["osaAlue", "kayttotarkoituskohdistus"])
    assert reg.additional_infos[1].value.code.value == "keskustatoimintojenAlue"
    k1 = next(q for q in p.questions if q.kind == "K1")
    assert k1.is_open and k1.recommendation == "osa_alue"
    k4 = next(q for q in p.questions if q.kind == "K4")
    assert k4.resolved_by == "linjaus L-07" and "Kaleva" in k4.question
    assert p.confidence == "matala"
    assert any(r.rule_id == "R-18" for r in p.rule_results)


def test_general_regulation_targets(kb, policies):
    p = convert(kb, policies).units[0].proposal
    assert p.kind == "yleismaarays"
    assert p.title == {"fin": "Yleiskaavan ohjausvaikutus"}
    k3 = next(q for q in p.questions if q.kind == "K3")
    assert k3.resolved_by == "linjaus L-05" and "RA, R" in k3.question
    assert any(r.rule_id == "R-16" and r.severity == "huomio" for r in p.rule_results)
    assert any(q.kind == "K12" and q.resolved_by == "tila vooka" for q in p.questions)  # MRL


def test_l05_structured_addition(kb, policies):
    project = convert(kb, policies, **{"L-05": "sailytys_ja_rakenteinen_lisays"})
    r_group = by_heading(project)["VAPAA-AJAN ASUMISEN JA MATKAILUN ALUE"].proposal
    infos = [
        i
        for reg in r_group.regulations
        for i in reg.additional_infos
        if i.type.value == "rakennusluvanPeruste"
    ]
    assert len(infos) == 1
    assert infos[0].value.code.uri == "http://uri.suomi.fi/codelist/rytj/oikeusvaik_YK/code/12"
    default = convert(kb, policies)
    assert not [
        i
        for reg in by_heading(default)["VAPAA-AJAN ASUMISEN JA MATKAILUN ALUE"].proposal.regulations
        for i in reg.additional_infos
        if i.type.value == "rakennusluvanPeruste"
    ]


def test_modifier_and_line_geometry(kb, policies):
    p = by_heading(convert(kb, policies))["KEHITETTÄVÄ RAUTATIE"].proposal
    assert codes(p.regulations[0]) == ("raideliikenteenAlue", ["kehitettava"])
    assert p.geometry_types == ["viiva"]
    assert not p.results("virhe")


def test_marking_without_text(kb, policies):
    p = by_heading(convert(kb, policies))["VESIALUE"].proposal
    assert [r.type.value for r in p.regulations] == ["vesialue"]
    assert p.letter_code == "W"


def test_mixed_use_is_k2(kb, policies):
    p = by_heading(convert(kb, policies))["ASUMISEN JA VIRKISTYKSEN SEKOITTUNUT ALUE"].proposal
    assert [codes(r) for r in p.regulations[:2]] == [
        ("asumisenAlue", ["paakayttotarkoitus"]),
        ("virkistysalue", ["paakayttotarkoitus"]),
    ]
    assert any(q.kind == "K2" and q.is_open for q in p.questions)


def test_informative_marking(kb, policies):
    p = by_heading(convert(kb, policies))["YLEISKAAVA-ALUEEN RAJA"].proposal
    assert p.kind == "ei_maarays" and not p.regulations
    assert [q.kind for q in p.open_questions()] == ["K6"]


def test_policy_choices_are_stored(kb, policies):
    project = convert(kb, policies, **{"L-06": "katja"})
    assert project.policy("L-06") == "katja"
    assert {c.id: c.source for c in project.policy_choices}["L-06"] == "kayttaja"
    c1 = by_heading(project)["TÄYDENTYVÄ KESKUSTA"].proposal
    assert c1.letter_code == "cka"  # annex 4: keskustatoimintojen kehittämisvyöhyke (same code combination)
    assert project.meta.knowledge_version == kb.version
    assert project.meta.codelist_versions["RY_Kaavamaarayslaji"] == kb.index.version("RY_Kaavamaarayslaji")


def test_l03_paragraphs_and_l04_subcodes(kb, policies):
    text = (
        "@kartta Kartta 1\nKESKUSTATOIMINTOJEN ALUE\nAlue varataan palveluille.\n\n"
        "Alueen suunnittelussa tulee huomioida kulttuuriympäristö.\n"
    )
    project = convert(kb, policies, text, **{"L-03": "kappaleittain", "L-04": "alakoodit"})
    p = project.units[0].proposal
    verbal = p.regulations[1:]
    assert [r.value.text["fin"] for r in verbal] == [
        "Alue varataan palveluille.",
        "Alueen suunnittelussa tulee huomioida kulttuuriympäristö.",
    ]
    assert verbal[1].type.value == "suunnittelumaarays"
    assert not [r for r in p.rule_results if r.rule_id == "R-19" and r.severity == "virhe"]


def test_r19_detects_changed_text(kb, policies):
    from kaavamaaraysavustaja.core.rules import RuleEngine

    project = convert(kb, policies)
    unit = by_heading(project)["KESKUSTATOIMINTOJEN ALUE"]
    unit.proposal.regulations[1].value.text["fin"] += " Lisätty lause."
    results = RuleEngine(kb).check(unit, plan_level="yleiskaava", mode="vooka")
    assert any(r.rule_id == "R-19" and r.severity == "virhe" for r in results)


def test_keys_are_deterministic(kb, policies):
    first = convert(kb, policies)
    second = convert(kb, policies)
    assert [u.proposal.key for u in first.units] == [u.proposal.key for u in second.units]


def test_sentence_case():
    assert sentence_case("TÄYDENTYVÄ KESKUSTA") == "Täydentyvä keskusta"
    assert sentence_case("VAK -RATAPIHA") == "VAK -ratapiha"
    assert sentence_case("ALUE, JOLLE SAA SIJOITTAA") == "Alue, jolle saa sijoittaa"
    assert sentence_case("Hulevesien hallinta") == "Hulevesien hallinta"
