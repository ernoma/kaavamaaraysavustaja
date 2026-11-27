"""Feedback round 1 (P1-01–P1-09, docs/palaute_vaihe3.md): the dock's logic without QGIS."""

import dataclasses
import json
import re

import pytest

from kaavamaaraysavustaja.core import workflow
from kaavamaaraysavustaja.core.model import InterpretationQuestion, QuestionOption

LEGEND = """\
@kartta Kartta 1 - Yhdyskuntarakenne
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille. Alueen suunnittelussa tulee kiinnittää huomiota kulttuuriympäristön arvoihin.
c-1 TÄYDENTYVÄ KESKUSTA
Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
"""
ONE_MARKING = "c-1 TÄYDENTYVÄ KESKUSTA\nAluetta kehitetään täydennettävänä keskustatoimintojen alueena.\n"
TWO_MAPS = """\
@kartta Kartta 1 - Yhdyskuntarakenne
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille.
@kartta Kartta 2 - Liikenne
RAITIOTIE
Raitiotie on ohjeellinen.
"""
IDS = re.compile(r"\b(?:L-\d{2}|K\d{1,2}|R-\d{2}|ADR-\d{4}|TP-\d{4}\.\d{2}-\d+)\b")
LOCK = {
    "perustelu": "Jäljitettävyys voimassa olevaan kaavaan.",
    "paivamaara": "2026-12-01",
    "hyvaksyja": "yleiskaavoitus",
}


def drafting(**kwargs):
    base = dict(
        text="Alueelle saa rakentaa enintään 6 000 k-m² pientaloja.\n\nPihoille suositellaan hulevesien viivyttämistä.",
        heading="Pientalovaltainen asuntoalue",
        mode="laadinta",
    )
    return workflow.ConversionRequest(**{**base, **kwargs})


def unexplained_ids(text: str) -> list[str]:
    """Identifiers not in an explained form: 'Kirjaintunnukset (L-06)', 'Kirjaintunnus
    (tulkintakysymys K14)' or 'tarkistussääntö R-19'. ADR and knowledge base ids never."""
    bad = []
    for m in IDS.finditer(text):
        before, after = text[: m.start()], text[m.end() :]
        explained = (
            (before.endswith("(") and after.startswith(")"))
            or before.endswith("(tulkintakysymys ")
            or before.lower().endswith("tarkistussääntö ")
        )
        if m.group().startswith(("ADR-", "TP-")) or not explained:
            bad.append(m.group())
    return bad


def question(unit, kind):
    return next(q for q in unit.proposal.questions if q.kind == kind)


# -- P1-01 plain language ------------------------------------------------------------------


def test_p1_01_header_is_plain_language(kb):
    text, details = workflow.header(kb, "laadinta")
    month = workflow.MONTHS[kb.valid_on.month - 1]
    assert "Uusi määräys (laadinta)" in text
    assert f"Koodistot ja säännöt: {month} {kb.valid_on.year}" in text
    assert not IDS.search(text) and "prompts/" not in text and "kehote" not in text
    assert kb.version in details and "kielimallin ohjeiden" in details  # identifier only in the tooltip
    assert "Voimassa oleva määräys (VOOKA)" in workflow.header(kb, "vooka")[0]


def test_p1_01_plain_text_explains_identifiers(kb):
    g = workflow.glossary(kb)
    assert (
        workflow.plain_text("K14: Valittu c-1: L-06: alkuperaiset (suositeltu oletus).", g)
        == "Kirjaintunnus (tulkintakysymys K14): Valittu c-1: linjaus Kirjaintunnukset (L-06): "
        "lähteen tunnus (suositeltu oletus)."
    )
    assert workflow.plain_text("Periaate P2; ADR-0007", g) == "lähdeuskollisuus"
    assert (
        workflow.plain_text("Liitetty selite (useita merkintöjä, ADR-0009)", g)
        == "Liitetty selite (useita merkintöjä)"
    )
    assert workflow.plain_text("(ADR-0009)", g) == ""
    rule = workflow.plain_text(
        "ryhmässä on sanallinenMaarays (linjaus L-04; vaihtoehto kehittamisvyohyke_suunnittelumaarays noudattaa opasta).",
        g,
    )
    assert "(linjaus Sanallisen määräyksen tyyppi yleiskaavassa (L-04);" in rule
    assert "”kehittämisvyöhykkeellä suunnittelumääräys”" in rule and "kehittamisvyohyke_" not in rule
    assert workflow.plain_text("knowledge/org/tampere/linjaukset.yaml", g) == "linjauskirjasto"
    assert (
        workflow.plain_text("vain yksi suure (R-04), joten", g)
        == "vain yksi suure (tarkistussääntö R-04), joten"
    )
    assert workflow.plain_text("Teksti on tarkistettu. Sääntö R-19 ei huomauta.", g) == (
        "Teksti on tarkistettu. Tarkistussääntö R-19 ei huomauta."
    )
    assert (
        workflow.plain_text("avoin tulkintakysymys: K13", g)
        == "avoin tulkintakysymys: Määräys vai suositus (K13)"
    )
    assert workflow.plain_text("1 virhettä; avoin tulkintakysymys: K1, K14", g) == (
        "1 virhettä; avoimia tulkintakysymyksiä: Aluevaraus vai osa-alue (K1), Kirjaintunnus (K14)"
    )
    assert unexplained_ids("(avoin tulkintakysymys: K13)") == ["K13"]  # the check itself is strict
    assert workflow.plain_text("Varmistus vektoriaineistosta (vaihe 4).", g) == (
        "Varmistus vektoriaineistosta (myöhemmässä versiossa)."
    )
    assert workflow.plain_text("Katja liite 4 / rivi 6; suunnitelma 6.10 K1", g) == (
        "Katja liite 4 / rivi 6; tulkintakysymys Aluevaraus vai osa-alue (K1)"
    )
    assert workflow.plain_text("laajempi (Katja 2 §). L-15: lahde (suositeltu oletus).", g).startswith(
        "laajempi (Katja 2 §). Linjaus Ryhmän otsikko"
    )
    # A letter code that looks like a question type is left alone.
    assert workflow.plain_text("Kirjaintunnus K1 säilyy.", g) == "Kirjaintunnus K1 säilyy."
    # Explaining twice changes nothing.
    for text in (
        "K14: Valittu c-1: L-06: alkuperaiset (suositeltu oletus).",
        "(Katja 2 §; linjaus L-15). Sääntö R-19 ja (R-04).",
        "Katja liite 4 / rivi 6; suunnitelma 6.10 K1",
        "2 varoitusta; avoin tulkintakysymys: K1, K14",
    ):
        once = workflow.plain_text(text, g)
        assert workflow.plain_text(once, g) == once and unexplained_ids(once) == [], once


def test_p1_01_detail_and_questions_have_no_unexplained_ids(kb):
    for request in (
        drafting(),
        workflow.ConversionRequest(text=LEGEND, legend=True),
        workflow.ConversionRequest(
            text=TWO_MAPS, legend=True, overrides={"L-06": "katja", "L-03": "kappaleittain"}
        ),
    ):
        project = workflow.rule_based(kb, request)
        for unit in project.units:
            assert unexplained_ids(workflow.detail_html(kb, unit)) == [], unit.id
            for q in unit.proposal.questions:
                view = workflow.question_view(kb, project, unit, q)
                for text in (view.title, view.basis, view.explanation, view.how_to_change, view.answer):
                    assert unexplained_ids(text) == [], (q.id, text)
                assert q.kind in view.tooltip  # the type identifier only secondary, explained


def test_p1_01_summary_is_plain(kb):
    project = workflow.rule_based(kb, drafting())
    assert workflow.summary_text(project).startswith("1 yksikkö, ")


# -- P1-02, P1-03 map ----------------------------------------------------------------------


def test_p1_02_maps_of_the_pasted_text(kb):
    assert workflow.legend_maps(TWO_MAPS) == ["Kartta 1 - Yhdyskuntarakenne", "Kartta 2 - Liikenne"]
    assert workflow.legend_maps(ONE_MARKING) == []
    assert "2 karttaa" in workflow.map_hint(workflow.legend_maps(TWO_MAPS))
    assert workflow.map_hint([]) == ""
    both = workflow.rule_based(kb, workflow.ConversionRequest(text=TWO_MAPS, legend=True))
    assert len(both.units) == 2 and both.meta.map is None  # all maps
    second = workflow.rule_based(
        kb, workflow.ConversionRequest(text=TWO_MAPS, legend=True, map="Kartta 2 - Liikenne")
    )
    assert [u.heading for u in second.units] == ["RAITIOTIE"] and second.meta.map == "Kartta 2 - Liikenne"
    only = workflow.rule_based(kb, workflow.ConversionRequest(text=LEGEND, legend=True))
    assert only.meta.map == "Kartta 1 - Yhdyskuntarakenne"  # the only map of the text is recorded


def test_p1_02_exact_map_title_is_chosen(kb):
    text = (
        "@kartta Kartta 1 - Liikenne\nRAITIOTIE\nRaitiotie on ohjeellinen.\n"
        "@kartta Kartta 1 - Liikenne ja pysäköinti\nPYSÄKÖINTILAITOS\nPysäköinti keskitetään.\n"
    )
    units, _ = workflow.build_units(
        workflow.ConversionRequest(text=text, legend=True, map="Kartta 1 - Liikenne")
    )
    assert [u.heading for u in units] == ["RAITIOTIE"]


def test_p1_03_single_regulation_has_no_map(kb):
    project = workflow.rule_based(kb, drafting(map="Kartta 1"))
    assert project.units[0].map is None and project.meta.map is None


# -- P1-04 policy choices ------------------------------------------------------------------


def test_p1_04_policy_texts_are_plain_and_complete(kb):
    for option in workflow.policy_options(kb):
        assert option.explanation and not IDS.search(option.explanation), option.id
        assert option.id not in option.title
        for value in option.options:
            assert option.labels.get(value) and option.effects.get(value), (option.id, value)
            assert not IDS.search(option.labels[value] + option.effects[value]), (option.id, value)
        assert option.label(option.default) == option.labels[option.default]


def test_p1_04_only_changed_choices_are_overrides(kb):
    options = workflow.policy_options(kb)
    selected = {o.id: o.default for o in options} | {"L-06": "katja"}
    assert workflow.policy_overrides(options, selected) == {"L-06": "katja"}
    assert workflow.policy_summary(options, {}) == "kaikki suositellussa oletuksessa"
    assert (
        workflow.policy_summary(options, {"L-06": "katja"})
        == "muutettu 1: Kirjaintunnukset (liitteen 4 tunnus)"
    )
    project = workflow.rule_based(kb, drafting(overrides=workflow.policy_overrides(options, selected)))
    sources = {c.id: c.source for c in project.policy_choices}
    assert sources["L-06"] == "kayttaja" and sources["L-03"] == "oletus"  # defaults stay defaults


def test_p1_04_locked_policy_is_explained_and_fixed(kb):
    options = [
        dataclasses.replace(o, locked=True, decision=LOCK) if o.id == "L-06" else o
        for o in workflow.policy_options(kb)
    ]
    l06 = next(o for o in options if o.id == "L-06")
    assert not l06.changeable
    assert "1.12.2026" in l06.lock_reason and "yleiskaavoitus" in l06.lock_reason
    assert "ei voi muuttaa" in l06.lock_reason
    assert workflow.policy_overrides(options, {"L-06": "katja"}) == {}
    with pytest.raises(workflow.InputError, match="lukittu"):
        workflow.set_policy(options, {}, "L-06", "katja")


# -- P1-05 pasted text with one marking ----------------------------------------------------


def test_p1_05_pasted_text_with_one_marking(kb):
    project = workflow.rule_based(
        kb, workflow.ConversionRequest(text=ONE_MARKING, legend=True, mode="laadinta")
    )
    (unit,) = project.units
    assert unit.heading == "TÄYDENTYVÄ KESKUSTA" and unit.letter_code == "c-1"
    assert unit.proposal.title["fin"] == "Täydentyvä keskusta" and unit.proposal.letter_code == "c-1"
    text = "KESKUSTATOIMINTOJEN ALUE\nAlue varataan julkisille ja yksityisille palveluille.\n"
    (unit,) = workflow.rule_based(kb, workflow.ConversionRequest(text=text, legend=True)).units
    assert unit.heading == "KESKUSTATOIMINTOJEN ALUE" and unit.letter_code is None


def test_p1_05_example_shown_in_the_dock_is_valid():
    units, warnings = workflow.build_units(
        workflow.ConversionRequest(text=workflow.LEGEND_EXAMPLE, legend=True)
    )
    assert len(units) == 1 and units[0].letter_code == "c-1" and not warnings


def test_p1_05_text_without_headings_explains_the_format(kb):
    request = workflow.ConversionRequest(
        text="Pientalovaltainen asuntoalue\nAlueelle saa rakentaa pientaloja.", legend=True
    )
    with pytest.raises(workflow.InputError, match="ISOIN KIRJAIMIN"):
        workflow.rule_based(kb, request)


def test_p1_05_skipped_lines_are_reported(kb):
    project = workflow.rule_based(
        kb, workflow.ConversionRequest(text="Tämä rivi ei ole merkintä.\n" + ONE_MARKING, legend=True)
    )
    assert len(project.units) == 1
    (warning,) = workflow.input_warnings(project)
    assert "rivi 1" in warning


# -- P1-06 who resolved a question ---------------------------------------------------------


def test_p1_06_open_policy_and_own_answers(kb):
    request = drafting()
    project = workflow.rule_based(kb, request)
    unit = project.units[0]
    view = workflow.question_view(kb, project, unit, question(unit, "K13"))
    assert view.resolver == "avoin" and view.editable and view.policy_id is None
    assert view.status == "avoin" and view.answer == ""
    view = workflow.question_view(kb, project, unit, question(unit, "K14"))
    assert view.resolver == "linjaus" and not view.editable and view.policy_id == "L-06"
    assert view.policy_switchable and dict(view.policy_choices)["katja"] == "liitteen 4 tunnus"
    assert view.policy_value == "alkuperaiset" and view.answer == "lähteen tunnus"
    assert "Kirjaintunnukset" in view.explanation and "koko muunnosta" in view.how_to_change
    # The user's own answer can always be changed.
    request.decisions = workflow.add_decision(
        [], workflow.decision_for(unit, question(unit, "K13"), "suositus")
    )
    again = workflow.rule_based(kb, request)
    unit = again.units[0]
    view = workflow.question_view(kb, again, unit, question(unit, "K13"), decisions=request.decisions)
    assert view.resolver == "kayttaja" and view.editable and view.own_decision
    assert view.status == "ratkaisit itse" and "aina" in view.how_to_change
    assert view.answer == "Kaavasuositus (suosittelevat kappaleet)"


def test_p1_06_locked_policy_cannot_be_changed_in_the_card(kb):
    project = workflow.rule_based(kb, drafting())
    unit = project.units[0]
    choice = next(c for c in project.policy_choices if c.id == "L-06")
    choice.source, choice.decision = "lukittu", LOCK
    view = workflow.question_view(kb, project, unit, question(unit, "K14"))
    assert view.resolver == "lukittu" and not view.editable and not view.policy_switchable
    assert "1.12.2026" in view.how_to_change and "ei voi muuttaa" in view.how_to_change


def test_p1_06_model_and_mode_resolutions(kb):
    project = workflow.rule_based(kb, drafting())
    unit = project.units[0]
    options = [QuestionOption("a", "Koodi A"), QuestionOption("b", "Koodi B")]
    q = InterpretationQuestion("u001-K5", "K5", "Ei sopivaa koodia", options, "a", "", "b", "kielimalli")
    view = workflow.question_view(kb, project, unit, q)
    assert view.resolver == "kielimalli" and view.editable and view.answer == "Koodi B"
    options = [
        QuestionOption("ennallaan", "Teksti säilyy ennallaan"),
        QuestionOption("korvaava", "Päivitetään"),
    ]
    q = InterpretationQuestion(
        "u001-K12", "K12", "Vanhentunut lakiviittaus", options, "ennallaan", "", "ennallaan", "tila vooka"
    )
    view = workflow.question_view(kb, project, unit, q)
    assert view.resolver == "tila" and not view.editable and "Uusi määräys (laadinta)" in view.how_to_change


def test_p1_06_answer_made_for_a_similar_marking(kb):
    text = "c-1 TÄYDENTYVÄ KESKUSTA\nAluetta kehitetään.\nc-2 TÄYDENTYVÄ KESKUSTA\nAluetta kehitetään myös.\n"
    request = workflow.ConversionRequest(text=text, legend=True)
    project = workflow.rule_based(kb, request)
    first = project.units[0]
    request.decisions = [workflow.decision_for(first, question(first, "K1"), "osa_alue", scope="projekti")]
    again = workflow.rule_based(kb, request)
    second = again.units[1]
    view = workflow.question_view(kb, again, second, question(second, "K1"), decisions=request.decisions)
    assert view.resolver == "kayttaja" and view.editable and not view.own_decision
    assert "c-1" in view.explanation


def test_p1_06_switch_policy_from_the_card(kb):
    options = workflow.policy_options(kb)
    overrides = workflow.set_policy(options, {}, "L-06", "katja")
    assert overrides == {"L-06": "katja"}
    project = workflow.rule_based(
        kb, workflow.ConversionRequest(text=ONE_MARKING, legend=True, overrides=overrides)
    )
    unit = project.units[0]
    assert unit.proposal.letter_code == "cka"
    assert next(c for c in project.policy_choices if c.id == "L-06").source == "kayttaja"
    view = workflow.question_view(kb, project, unit, question(unit, "K14"))
    assert view.policy_value == "katja" and "valitsit" in view.explanation
    assert workflow.set_policy(options, overrides, "L-06", "alkuperaiset") == {}  # back to the default
    with pytest.raises(workflow.InputError):
        workflow.set_policy(options, {}, "L-06", "tuntematon")
    with pytest.raises(workflow.InputError):
        workflow.set_policy(options, {}, "L-03", "aiheittain")  # not available in this version


def test_p1_06_own_answer_can_be_removed(kb):
    project = workflow.rule_based(kb, drafting())
    unit = project.units[0]
    decisions = workflow.add_decision([], workflow.decision_for(unit, question(unit, "K13"), "suositus"))
    assert workflow.find_decision(decisions, unit, "K13") is not None
    assert workflow.remove_decision(decisions, unit, "K13") == []
    view = workflow.question_view(kb, project, unit, question(unit, "K13"), decisions=decisions)
    assert "Kaavasuositus" in view.pending  # saved, not yet re-run


# -- P1-07 Ryhti JSON view -----------------------------------------------------------------


def test_p1_07_ryhti_view_is_the_exported_json(kb, tmp_path):
    project = workflow.rule_based(kb, drafting())
    result = workflow.export(kb, project, tmp_path, "uusi", ["ryhti"])
    whole = workflow.ryhti_view(project)
    assert whole.text == result.paths["ryhti"].read_text(encoding="utf-8")
    unit = project.units[0]
    view = workflow.ryhti_view(project, unit.id)
    group = json.loads(view.text)
    assert group["planRegulationGroupKey"] == unit.proposal.key
    assert group == json.loads(whole.text)["planRegulationGroups"][0]
    assert view.included and view.open_questions == 1
    assert any("Avoimia tulkintakysymyksiä 1" in note for note in view.notes)


def test_p1_07_ryhti_view_tells_about_open_and_pending_answers(kb):
    request = drafting()
    project = workflow.rule_based(kb, request)
    unit = project.units[0]
    decisions = workflow.add_decision([], workflow.decision_for(unit, question(unit, "K13"), "suositus"))
    assert workflow.pending_decisions(project, decisions) == 1
    assert any(
        "Aja uudelleen ratkaisuin" in note for note in workflow.ryhti_view(project, decisions=decisions).notes
    )
    request.decisions = decisions
    again = workflow.rule_based(kb, request)
    assert workflow.pending_decisions(again, decisions) == 0
    assert workflow.pending_decisions(again, []) == 1  # a removed answer is pending as well
    view = workflow.ryhti_view(again, again.units[0].id, decisions=decisions)
    assert view.open_questions == 0 and any("Ei avoimia tulkintakysymyksiä" in note for note in view.notes)
    assert not any("Aja uudelleen" in note for note in view.notes)
    assert "planRecommendations" in json.loads(view.text)


def test_p1_07_unit_not_in_ryhti_json(kb):
    project = workflow.rule_based(kb, drafting())
    unit = project.units[0]
    unit.proposal.kind = "ei_maarays"
    view = workflow.ryhti_view(project, unit.id)
    assert not view.included and view.text == ""
    assert any("ei ole kaavamääräys" in note for note in view.notes)


# -- P1-08 file name -----------------------------------------------------------------------


def test_p1_08_file_name_from_the_group(kb):
    project = workflow.rule_based(kb, drafting())
    assert workflow.suggested_stem(project) == "Pientalovaltainen_asuntoalue"
    legend = workflow.rule_based(kb, workflow.ConversionRequest(text=LEGEND, legend=True))
    assert legend.meta.title == "Kartta 1 - Yhdyskuntarakenne"
    assert workflow.suggested_stem(legend) == "Keskustatoimintojen_alue"  # the first group, not the map
    project.units[0].proposal.title = {}
    assert workflow.suggested_stem(project) == "AP"  # letter code when there is no title


def test_p1_08_suggestion_follows_every_conversion_unless_edited(kb):
    first = workflow.rule_based(kb, drafting())
    second = workflow.rule_based(kb, workflow.ConversionRequest(text=LEGEND, legend=True))
    stem, suggestion = workflow.stem_after_conversion("", None, first)
    assert stem == suggestion == "Pientalovaltainen_asuntoalue"
    stem, suggestion = workflow.stem_after_conversion(stem, suggestion, second)
    assert stem == suggestion == "Keskustatoimintojen_alue"
    assert workflow.stem_after_conversion("oma_nimi", suggestion, first) == (
        "oma_nimi",
        "Pientalovaltainen_asuntoalue",
    )
    assert workflow.file_stem(" c-1 / Täydentyvä keskusta ") == "c-1_Täydentyvä_keskusta"


# -- P1-09 export never overwrites without asking ------------------------------------------


def test_p1_09_export_adds_a_number_by_default(kb, tmp_path):
    project = workflow.rule_based(kb, drafting())
    formats = ["projekti", "markdown", "ryhti"]
    first = workflow.export(kb, project, tmp_path, "uusi", formats)
    assert first.stem == "uusi" and not first.renamed and not first.replaced
    first.paths["markdown"].write_text("oma muokkaus", encoding="utf-8")
    assert workflow.existing_exports(tmp_path, "uusi", formats) == [first.paths[f] for f in formats]
    second = workflow.export(kb, project, tmp_path, "uusi", formats)
    assert second.stem == "uusi_2" and second.renamed and not second.replaced
    assert first.paths["markdown"].read_text(encoding="utf-8") == "oma muokkaus"  # kept
    assert all(path.exists() and "uusi_2" in path.name for path in second.paths.values())
    assert workflow.export(kb, project, tmp_path, "uusi", formats).stem == "uusi_3"


def test_p1_09_overwrite_is_a_separate_choice(kb, tmp_path):
    project = workflow.rule_based(kb, drafting())
    first = workflow.export(kb, project, tmp_path, "uusi", ["markdown"])
    first.paths["markdown"].write_text("vanha", encoding="utf-8")
    again = workflow.export(kb, project, tmp_path, "uusi", ["markdown"], overwrite=True)
    assert again.stem == "uusi" and again.replaced == [first.paths["markdown"]]
    assert "Muunnosraportti" in first.paths["markdown"].read_text(encoding="utf-8")


def test_p1_09_only_the_chosen_formats_count(kb, tmp_path):
    project = workflow.rule_based(kb, drafting())
    workflow.export(kb, project, tmp_path, "uusi", ["markdown"])
    assert workflow.export(kb, project, tmp_path, "uusi", ["ryhti"]).stem == "uusi"
    with pytest.raises(workflow.InputError):
        workflow.export(kb, project, tmp_path, "uusi", [])
