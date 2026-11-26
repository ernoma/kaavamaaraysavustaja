"""Drafting mode (laadintatila, UC2, ADR-0016): a new regulation written by the user.

Differences from VOOKA (ADR-0017): R-19 is not applied, a numeric value is proposed as a
quantity (opas 3.3.9) and a recommendation-like paragraph raises K13 (määräys vai suositus).
The text itself is never rewritten (no wording suggestions in the first version).
"""

from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.decisions import parse_decisions
from kaavamaaraysavustaja.core.ingest import single_unit
from kaavamaaraysavustaja.core.model import SourceUnit


def convert(kb, policies, units, mode="laadinta", decisions=None, **overrides):
    return convert_units(
        kb, units, policies.resolve(overrides), mode=mode, name="laadinta", decisions=decisions
    )


def unit(heading, text, letter_code=None, kind="merkinta"):
    return single_unit(heading, text, letter_code=letter_code, kind=kind)


# -- input ---------------------------------------------------------------------------------


def test_single_unit_normalizes_text_and_keeps_raw():
    u = unit(
        "Kerrostalovaltainen asuntoalue", "Alueen täydennys-\nrakentamisessa tulee\n\nToinen kappale.", "AK"
    )
    assert isinstance(u, SourceUnit)
    assert u.id == "u001" and u.kind == "merkinta"
    assert u.heading == "Kerrostalovaltainen asuntoalue" and u.letter_code == "AK"
    assert u.raw_text.startswith("Alueen täydennys-")
    assert u.normalized_text == "Alueen täydennysrakentamisessa tulee\n\nToinen kappale."
    assert any(c.kind == "tavutus" for c in u.normalization_diff)


def test_single_unit_general_regulation_and_empty_code():
    u = unit("Hulevedet", "Hulevedet on käsiteltävä.", letter_code="  ", kind="yleismaarays")
    assert u.kind == "yleismaarays" and u.letter_code is None


# -- R-19 only in VOOKA ----------------------------------------------------------------------


def test_r19_is_not_applied_in_drafting_mode(kb, policies):
    from kaavamaaraysavustaja.core.rules import RuleEngine

    engine = RuleEngine(kb)
    assert "R-19" in {r["tunnus"] for r in engine.active("yleiskaava", "vooka")}
    assert "R-19" not in {r["tunnus"] for r in engine.active("yleiskaava", "laadinta")}
    text = "Alue varataan asumiselle."
    draft = convert(kb, policies, [unit("ASUINALUE", text)])
    assert not [r for r in draft.units[0].proposal.rule_results if r.rule_id == "R-19"]
    # The text is still the user's text character by character.
    verbal = draft.units[0].proposal.regulations[-1]
    assert verbal.value.text["fin"] == text


# -- numeric values as quantities -------------------------------------------------------------


def test_number_becomes_quantity_in_drafting_mode(kb, policies):
    text = "Alueelle saa rakentaa enintään 12 000 k-m² asuin- ja liiketilaa."
    p = convert(kb, policies, [unit("Asuntoalue", text, "A")]).units[0].proposal
    quantities = [r for r in p.regulations if r.type.value == "sallittuKerrosala"]
    assert len(quantities) == 1
    q = quantities[0]
    assert q.value.data_type == "PositiveNumeric" and q.value.number == 12000 and q.value.unit == "k-m²"
    assert q.text_span is not None and text[q.text_span[0] : q.text_span[1]] == "12 000 k-m²"
    assert any("3.3.9" in (r.reference or "") for r in q.rationale)
    assert not [r for r in p.rule_results if r.rule_id in ("R-04", "R-05")], p.rule_results
    # The verbal text keeps the number (no rewording); R-18 tells that it is now also a quantity.
    r18 = [r for r in p.rule_results if r.rule_id == "R-18"]
    assert r18 and "myös suureena" in r18[0].message


def test_efficiency_number_is_decimal(kb, policies):
    p = convert(kb, policies, [unit("Asuntoalue", "Tehokkuusluku e=0,6.", "A")]).units[0].proposal
    q = next(r for r in p.regulations if r.type.value == "tehokkuusluku")
    assert q.value.data_type == "PositiveDecimal" and q.value.number == 0.6 and q.value.unit is None


def test_number_stays_verbal_in_vooka(kb, policies):
    text = "Alueelle saa rakentaa enintään 12 000 k-m² asuin- ja liiketilaa."
    p = convert(kb, policies, [unit("ASUINALUE", text)], mode="vooka").units[0].proposal
    assert not [r for r in p.regulations if r.type.value == "sallittuKerrosala"]


def test_several_numbers_are_not_quantities(kb, policies):
    """R-04: one quantity per group. Two values → stay verbal, the rationale says why."""
    text = "Kortteliin saa rakentaa 5 000 k-m² asumista ja 800 k-m² liiketilaa."
    p = convert(kb, policies, [unit("Asuntoalue", text, "A")]).units[0].proposal
    assert not [r for r in p.regulations if r.type.value == "sallittuKerrosala"]
    assert any("useita numeroarvoja" in r.claim for r in p.rationale)


def test_place_bound_number_follows_l07(kb, policies):
    text = "Vähittäiskaupan enimmäismitoitus Kalevassa on 70 000 k-m²."
    p = convert(kb, policies, [unit("Keskustatoimintojen alue", text, "C")]).units[0].proposal
    assert not [r for r in p.regulations if r.type.value == "sallittuKerrosala"]
    assert any(q.kind == "K4" for q in p.questions)


# -- K13: regulation or recommendation ----------------------------------------------------------


TEXT_MIXED = (
    "Alueen täydennysrakentamisessa tulee säilyttää korttelirakenne.\n\n"
    "Pihoille suositellaan hulevesiä viivyttäviä ratkaisuja."
)


def test_k13_raised_for_recommendation_paragraph(kb, policies):
    p = convert(kb, policies, [unit("Asuntoalue", TEXT_MIXED, "A")]).units[0].proposal
    k13 = next(q for q in p.questions if q.kind == "K13")
    assert k13.is_open and k13.recommendation == "suositus"
    assert {o.id for o in k13.options} == {"maarays", "suositus"}
    assert "suositellaan" in k13.basis
    assert not p.recommendations


def test_k13_answer_moves_paragraph_to_recommendation(kb, policies):
    decisions = parse_decisions([{"kysymys": "u001-K13", "valinta": "suositus"}])
    p = convert(kb, policies, [unit("Asuntoalue", TEXT_MIXED, "A")], decisions=decisions).units[0].proposal
    k13 = next(q for q in p.questions if q.kind == "K13")
    assert k13.answer == "suositus" and k13.resolved_by == "kayttaja"
    assert [r.text["fin"] for r in p.recommendations] == [
        "Pihoille suositellaan hulevesiä viivyttäviä ratkaisuja."
    ]
    verbal = [r for r in p.regulations if r.value and r.value.data_type == "LocalizedText"]
    assert [r.value.text["fin"] for r in verbal] == [
        "Alueen täydennysrakentamisessa tulee säilyttää korttelirakenne."
    ]
    for reg in verbal:
        assert TEXT_MIXED[reg.text_span[0] : reg.text_span[1]] == reg.value.text["fin"]
    rec = p.recommendations[0]
    assert TEXT_MIXED[rec.text_span[0] : rec.text_span[1]] == rec.text["fin"]
    assert not [r for r in p.rule_results if r.rule_id == "R-17"]


def test_k13_answer_regulation_keeps_text(kb, policies):
    decisions = parse_decisions([{"kysymys": "u001-K13", "valinta": "maarays"}])
    p = convert(kb, policies, [unit("Asuntoalue", TEXT_MIXED, "A")], decisions=decisions).units[0].proposal
    assert not p.recommendations
    assert p.regulations[-1].value.text["fin"] == TEXT_MIXED


def test_k13_mixed_paragraph_recommends_regulation(kb, policies):
    text = "Rakennukset tulee sovittaa ympäristöön, ja julkisivuissa suositellaan puuta."
    p = convert(kb, policies, [unit("Asuntoalue", text, "A")]).units[0].proposal
    k13 = next(q for q in p.questions if q.kind == "K13")
    assert k13.recommendation == "maarays"


def test_no_k13_in_vooka(kb, policies):
    p = convert(kb, policies, [unit("ASUINALUE", TEXT_MIXED)], mode="vooka").units[0].proposal
    assert not [q for q in p.questions if q.kind == "K13"]


def test_k12_law_reference_stays_open_in_drafting_mode(kb, policies):
    text = "Rakentaminen on sallittua MRL 72 §:n mukaisesti."
    p = convert(kb, policies, [unit("Rantavyöhyke", text, kind="yleismaarays")]).units[0].proposal
    k12 = next(q for q in p.questions if q.kind == "K12")
    assert k12.is_open
