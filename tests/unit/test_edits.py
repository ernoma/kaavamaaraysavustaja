"""Additional information chosen by the user (feedback P3-01, ADR-0019): core and dock logic."""

import dataclasses
import json

import pytest

from kaavamaaraysavustaja.core import edits as edit_log
from kaavamaaraysavustaja.core import workflow
from kaavamaaraysavustaja.core.hybrid import RequestBuilder, needs_model
from kaavamaaraysavustaja.core.llm.fake import FakeProvider
from kaavamaaraysavustaja.core.llm.prompts import PromptSet
from kaavamaaraysavustaja.core.model import CodeRef, ConversionProject
from kaavamaaraysavustaja.core.policy import PolicyError, load_settings

HEADING = (
    "TYÖPAIKKOJEN JA ELINKEINOJEN ALUE, JOLLA YMPÄRISTÖ ASETTAA TOIMINNAN LAADULLE ERITYISIÄ VAATIMUKSIA"
)
TEXT = (
    "Alue varataan toimisto- ja työpaikkatiloille. Alueelle ei tule sijoittaa sellaisia toimintoja, "
    "jotka häiriintyvät raskaasta liikenteestä, melusta ja tärinästä."
)
QUALITY = "ymparistoAsettaaToiminnanLaadulleErityisiaVaatimuksia"
LEGEND = """\
@kartta Kartta 1 - Yhdyskuntarakenne
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille. Alueen suunnittelussa tulee kiinnittää huomiota kulttuuriympäristön arvoihin.
c-1 TÄYDENTYVÄ KESKUSTA
Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
"""


def question(unit, kind):
    return next(q for q in unit.proposal.questions if q.kind == kind)


def with_code(kb, code="tyopaikkojenAlue"):
    """The P3-01 regulation in force with its regulation type chosen from the code list (K5)."""
    request = workflow.ConversionRequest(heading=HEADING, text=TEXT, mode="vooka")
    unit = workflow.rule_based(kb, request).units[0]
    request.decisions = [workflow.decision_for(unit, question(unit, "K5"), workflow.code_option(code))]
    return request, workflow.rule_based(kb, request)


def main_infos(proposal):
    return [
        (i.type.value, i.value.code.value if i.value else None)
        for i in proposal.regulations[0].additional_infos
    ]


# -- what can be chosen ------------------------------------------------------------------------


def test_info_choices_of_the_plan_level(kb):
    choices = {c.value: c for c in workflow.info_choices(kb, "yleiskaava")}
    assert choices[QUALITY].name == "Ympäristö asettaa toiminnan laadulle erityisiä vaatimuksia"
    assert "kaavamääräyksellä määrätään" in choices[QUALITY].description
    assert choices["paakayttotarkoitus"].value_codelist is None
    assert "tyyppi" not in choices and "rakentamisenOhjaus" not in choices  # header-level codes
    assert "ehdottomastiNoudatettava" not in choices  # asemakaava only
    assert "ehdottomastiNoudatettava" in {c.value for c in workflow.info_choices(kb, "asemakaava")}
    # Values that are numbers, ranges or periods, or codes of a list not in the knowledge base
    assert "kayttotarkoituksenOsuusKerrosalastaK-m2" not in choices
    assert "valiaikainenMaarays" not in choices and "rakennusluvanPeruste" not in choices
    target = choices["kayttotarkoituskohdistus"]
    assert target.value_codelist == "RY_Kaavamaarayslaji" and target.label.endswith(
        "– arvona kaavamääräyslaji"
    )
    values = [c.value for c in workflow.value_choices(kb, "yleiskaava", "kayttotarkoituskohdistus")]
    assert values == [c.value for c in workflow.code_choices(kb, "yleiskaava")]  # the same as K5
    assert workflow.value_choices(kb, "yleiskaava", QUALITY) == []


def test_value_types_are_data_and_r06_reads_them(kb):
    infos = kb.rules["lisatietojen_arvot"]
    assert {k for k, v in infos.items() if v.get("koodisto") == "RY_Kaavamaarayslaji"} == {
        "kayttotarkoituskohdistus",
        "poisluettavaKayttotarkoitus",
    }
    for info in infos:
        assert kb.index.get("RY_Kaavamaarayksen_Lisatiedonlaji", info) is not None, info


# -- the example of the feedback: K5 code + an additional information --------------------------


def test_p3_01_add_information_to_a_chosen_code(kb):
    request, project = with_code(kb)
    unit = project.units[0]
    view = workflow.edit_view(kb, project, unit, request.edits)
    assert view.available and not view.edited and "Sanallinen teksti säilyy ennallaan" in view.message
    (target,) = view.targets
    assert target.regulation is None and target.label == "Päämääräys: Työpaikkojen alue (tyopaikkojenAlue)"
    assert [(i.label, i.button) for i in target.items] == [
        ("Pääkäyttötarkoitus (avustajan ehdotus)", "Poista lisätieto")
    ]
    request.edits = workflow.add_info(kb, "yleiskaava", request.edits, unit, QUALITY, target=target)
    pending = workflow.edit_view(kb, project, unit, request.edits)
    assert pending.pending.startswith("⏳ Tallennettuja muutoksia 1")
    assert pending.targets[0].items[1].state == "lisataan"
    notes = " ".join(workflow.ryhti_view(project, unit.id, edits=request.edits).notes)
    assert "lisätietojen muutoksia, jotka eivät vielä näy JSONissa: 1" in notes

    again = workflow.rule_based(kb, request)
    unit = again.units[0]
    p = unit.proposal
    assert main_infos(p) == [("paakayttotarkoitus", None), (QUALITY, None)]
    assert p.status == "muokattu" and p.letter_code == "TP"  # the row the structure came from
    assert not p.results("virhe") and not p.results("varoitus") and workflow.unit_status(unit) == "valmis"
    assert workflow.schema_problems(kb, again) == {}
    claims = [r.claim for r in p.rationale]
    assert any(
        c.startswith(
            "Käyttäjä lisäsi lisätiedon ”Ympäristö asettaa toiminnan laadulle erityisiä vaatimuksia” "
            f"({QUALITY}) määräykseen ”Työpaikkojen alue”."
        )
        for c in claims
    )
    assert any("ei vastaa mitään liitteen 4 riviä" in c and "tarkista tunnus" in c for c in claims)
    verbal = [r for r in p.regulations if r.value and r.value.data_type == "LocalizedText"]
    assert verbal[0].value.text["fin"] == unit.normalized_text  # VOOKA: the text is untouched
    html = workflow.detail_html(kb, unit)
    assert "Käyttäjä lisäsi lisätiedon" in html and "ryhmää ei lähetetä kielimallille" in html
    view = workflow.edit_view(kb, again, unit, request.edits)
    assert view.pending == "" and view.edited
    assert [i.label for i in view.targets[0].items][1] == (
        "Ympäristö asettaa toiminnan laadulle erityisiä vaatimuksia (lisäsit)"
    )
    group = json.loads(workflow.ryhti_view(again, unit.id, edits=request.edits).text)
    types = [i["type"] for i in group["planRegulations"][0]["additionalInformations"]]
    assert types[-1].endswith(f"RY_Kaavamaarayksen_Lisatiedonlaji/code/{QUALITY}")
    # The user's structure is not sent to the language model.
    assert not needs_model(unit) and workflow.llm_plan(kb, again, "claude").estimate.units == 0
    from kaavamaaraysavustaja.exporters.report import markdown

    report = markdown(again, kb)
    assert "Käyttäjä lisäsi lisätiedon" in report and "Käyttäjän rakennemuokkaukset (lisätiedot): 1" in report


def test_changed_combination_takes_the_letter_code_of_its_annex_row(kb):
    request, project = with_code(kb, "teollisuusalue")
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=target)
    p = workflow.rule_based(kb, request).units[0].proposal
    assert p.letter_code == "TY"  # Katja annex 4, row 16
    assert any("vastaa liitteen 4 riviä 16" in r.claim for r in p.rationale)


def test_works_on_a_structure_from_annex_4(kb):
    request = workflow.ConversionRequest(text=LEGEND, legend=True)
    project = workflow.rule_based(kb, request)
    unit = project.units[0]
    assert unit.heading == "KESKUSTATOIMINTOJEN ALUE"
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, "uusi", target=target, basis="Uusi alue")
    again = workflow.rule_based(kb, request)
    p = again.units[0].proposal
    assert main_infos(p) == [("paakayttotarkoitus", None), ("uusi", None)]
    assert p.letter_code == "C" and p.status == "muokattu"
    assert any(r.claim.endswith("Perustelu: Uusi alue.") for r in p.rationale)
    other = again.units[1].proposal
    assert other.status == "ehdotus"  # only the edited marking is the user's


def test_a_value_is_chosen_from_the_code_list(kb):
    request, project = with_code(kb)
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    with pytest.raises(workflow.InputError, match="arvo"):
        workflow.add_info(kb, "yleiskaava", [], unit, "kayttotarkoituskohdistus", target=target)
    with pytest.raises(workflow.InputError, match="listasta"):
        workflow.add_info(
            kb, "yleiskaava", [], unit, "kayttotarkoituskohdistus", value="eiOle", target=target
        )
    with pytest.raises(workflow.InputError, match="ei anneta arvoa"):
        workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, value="teollisuusalue", target=target)
    with pytest.raises(workflow.InputError, match="on jo"):
        workflow.add_info(kb, "yleiskaava", [], unit, "paakayttotarkoitus", target=target)
    request.edits = workflow.add_info(
        kb, "yleiskaava", [], unit, "kayttotarkoituskohdistus", value="teollisuusalue", target=target
    )
    again = workflow.rule_based(kb, request)
    p = again.units[0].proposal
    assert ("kayttotarkoituskohdistus", "teollisuusalue") in main_infos(p)
    assert not [r for r in p.rule_results if r.rule_id == "R-06"]
    label = workflow.edit_view(kb, again, again.units[0], request.edits).targets[0].items[-1].label
    assert label == "Käyttötarkoituskohdistus → Teollisuusalue (lisäsit)"
    group = json.loads(workflow.ryhti_view(again, again.units[0].id).text)
    value = group["planRegulations"][0]["additionalInformations"][-1]["value"]
    assert value["dataType"] == "Code" and value["code"].endswith("RY_Kaavamaarayslaji/code/teollisuusalue")
    assert workflow.schema_problems(kb, again) == {}


# -- removing and restoring ----------------------------------------------------------------------


def test_remove_and_restore_the_assistants_information(kb):
    request, project = with_code(kb)
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    main_use = target.items[0]
    request.edits = workflow.change_item([], unit, target, main_use)
    assert [e.action for e in request.edits] == ["poista_lisatieto"]
    assert workflow.edit_view(kb, project, unit, request.edits).targets[0].items[0].button == "Peru poisto"
    again = workflow.rule_based(kb, request)
    unit = again.units[0]
    p = unit.proposal
    assert main_infos(p) == []
    errors = [r for r in p.results("virhe")]
    assert [r.rule_id for r in errors] == ["R-08"]  # an area needs a main use or a sub-area
    g = workflow.glossary(kb)
    assert "tarkistussääntö R-08" in workflow.detail_html(kb, unit, g)
    assert any(r.claim.startswith("Käyttäjä poisti lisätiedon ”Pääkäyttötarkoitus”") for r in p.rationale)
    view = workflow.edit_view(kb, again, unit, request.edits)
    (item,) = view.targets[0].items
    assert (item.label, item.button) == ("Pääkäyttötarkoitus – poistit (ei ryhmässä)", "Palauta lisätieto")
    request.edits = workflow.change_item(request.edits, unit, view.targets[0], item)
    assert request.edits == []  # restoring cancels the removal
    assert workflow.edit_view(kb, again, unit, request.edits).targets[0].items[0].state == "palautetaan"
    restored = workflow.rule_based(kb, request).units[0].proposal
    assert main_infos(restored) == [("paakayttotarkoitus", None)] and restored.status == "ehdotus"


def test_removing_an_own_addition_cancels_it(kb):
    request, project = with_code(kb)
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=target)
    pending = workflow.edit_view(kb, project, unit, request.edits).targets[0].items[1]
    assert pending.button == "Peru lisäys"
    assert workflow.change_item(request.edits, unit, target, pending) == []
    again = workflow.rule_based(kb, request)
    unit = again.units[0]
    view = workflow.edit_view(kb, again, unit, request.edits)
    own = view.targets[0].items[1]
    request.edits = workflow.change_item(request.edits, unit, view.targets[0], own)
    assert request.edits == []
    assert workflow.edit_view(kb, again, unit, request.edits).targets[0].items[1].state == "poistetaan"
    assert main_infos(workflow.rule_based(kb, request).units[0].proposal) == [("paakayttotarkoitus", None)]


# -- re-runs, an earlier conversion, the settings file ------------------------------------------


def test_edits_are_kept_in_the_project_and_on_reopening(kb, tmp_path):
    request, project = with_code(kb)
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=target)
    again = workflow.rule_based(kb, request)
    assert [e.info.value for e in again.edits] == [QUALITY]
    assert again.edits[0].heading == HEADING and again.edits[0].at
    assert again.edits[0].info.codelist_version == kb.index.version("RY_Kaavamaarayksen_Lisatiedonlaji")
    path = workflow.export(kb, again, tmp_path, "p", ["projekti"]).paths["projekti"]
    loaded = ConversionProject.load(path)
    assert loaded == again and json.loads(path.read_text(encoding="utf-8"))["format_version"] == 2
    assert workflow.pending_edits(loaded, loaded.edits) == 0
    reopened = workflow.rule_based(
        kb, dataclasses.replace(request, decisions=loaded.decisions, edits=loaded.edits)
    )
    assert main_infos(reopened.units[0].proposal) == main_infos(again.units[0].proposal)
    # A version 1 project (no edits) still opens.
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("edits")
    data["format_version"] = 1
    assert ConversionProject.from_dict(data).edits == []


def test_edit_follows_the_main_regulation_when_the_code_changes(kb):
    request, project = with_code(kb)
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=target)
    request.decisions = [
        workflow.decision_for(unit, question(unit, "K5"), workflow.code_option("teollisuusalue"))
    ]
    p = workflow.rule_based(kb, request).units[0].proposal
    assert p.regulations[0].type.value == "teollisuusalue" and (QUALITY, None) in main_infos(p)


def test_edit_without_a_target_regulation(kb):
    request = workflow.ConversionRequest(heading=HEADING, text=TEXT, mode="vooka")
    project = workflow.rule_based(kb, request)
    unit = project.units[0]
    view = workflow.edit_view(kb, project, unit)
    assert not view.available and "Ei sopivaa Katja-koodia" in view.message
    request.edits = edit_log.parse_edits(kb, [{"otsikko": HEADING, "lisaa": QUALITY}])
    again = workflow.rule_based(kb, request)
    p = again.units[0].proposal
    assert p.status == "muokattu" and not needs_model(again.units[0])
    assert any("ei voitu käsitellä" in r.claim and r.confidence == "matala" for r in p.rationale)
    assert again.provenance[0].details["muokkausten_varoitukset"]


def test_quantity_as_a_target_and_r05(kb):
    request = workflow.ConversionRequest(
        heading="Pientalovaltainen asuntoalue",
        text="Alueelle saa rakentaa enintään 6 000 k-m² pientaloja.",
        mode="laadinta",
    )
    project = workflow.rule_based(kb, request)
    unit = project.units[0]
    view = workflow.edit_view(kb, project, unit)
    assert [t.label for t in view.targets] == [
        "Päämääräys: Asuinpientaloalue (asuinpientaloalue)",
        "Suure: Sallittu kerrosala (sallittuKerrosala)",
    ]
    quantity = view.targets[1]
    before = {r.rule_id for r in unit.proposal.results("virhe")}
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=quantity)
    p = workflow.rule_based(kb, request).units[0].proposal
    assert {r.rule_id for r in p.results("virhe")} - before == {"R-05"}  # only a few infos for a quantity
    assert any("määräykseen ”Sallittu kerrosala”" in r.claim for r in p.rationale)
    request.edits = workflow.add_info(
        kb, "yleiskaava", [], unit, "kayttotarkoituskohdistus", value="asuinpientaloalue", target=quantity
    )
    p = workflow.rule_based(kb, request).units[0].proposal
    assert {r.rule_id for r in p.results("virhe")} == before
    reg = next(r for r in p.regulations if r.type.value == "sallittuKerrosala")
    assert [i.type.value for i in reg.additional_infos] == ["kayttotarkoituskohdistus"]


def test_settings_file_edits(kb, tmp_path):
    items = [
        {"otsikko": HEADING, "lisaa": QUALITY, "perustelu": "liite 4 TY"},
        {"otsikko": HEADING, "poista": "paakayttotarkoitus"},
        {
            "yksikko": "u001",
            "lisaa": "kayttotarkoituskohdistus",
            "arvo": "teollisuusalue",
            "maarays": "sallittuKerrosala",
        },
    ]
    edits = edit_log.parse_edits(kb, items)
    assert [e.action for e in edits] == ["lisaa_lisatieto", "poista_lisatieto", "lisaa_lisatieto"]
    assert edits[2].value.value == "teollisuusalue" and edits[2].regulation.value == "sallittuKerrosala"
    for bad, message in (
        ({"otsikko": HEADING}, "lisaa tai poista"),
        ({"otsikko": HEADING, "lisaa": "eiOle"}, "ei ole voimassa"),
        ({"otsikko": HEADING, "lisaa": "kayttotarkoituskohdistus"}, "tarvitaan arvo"),
        ({"otsikko": HEADING, "lisaa": QUALITY, "arvo": "teollisuusalue"}, "ei anneta arvoa"),
        ({"lisaa": QUALITY}, "otsikko puuttuu"),
        ({"otsikko": HEADING, "lisaa": QUALITY, "laajuus": "projekti"}, "tuntemattomat"),
    ):
        with pytest.raises(edit_log.EditError, match=message):
            edit_log.parse_edits(kb, [bad])
    path = tmp_path / "asetukset.yaml"
    path.write_text(f"muokkaukset:\n  - otsikko: {HEADING}\n    lisaa: {QUALITY}\n", encoding="utf-8")
    assert load_settings(path)["muokkaukset"][0]["lisaa"] == QUALITY
    path.write_text("muokkaukset: x\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_settings(path)


def test_cli_keeps_edits_of_the_earlier_project(kb, tmp_path):
    from kaavamaaraysavustaja import cli

    source = tmp_path / "syote.txt"
    source.write_text(LEGEND, encoding="utf-8")
    settings = tmp_path / "asetukset.yaml"
    settings.write_text(
        "muokkaukset:\n  - otsikko: KESKUSTATOIMINTOJEN ALUE\n    lisaa: uusi\n", encoding="utf-8"
    )
    out = tmp_path / "ulos"
    assert cli.main(["convert", str(source), "--asetukset", str(settings), "--ulos", str(out)]) == 0
    first = ConversionProject.load(out / "syote.kma.json")
    assert [e.info.value for e in first.edits] == ["uusi"]
    again = tmp_path / "uudelleen"
    assert (
        cli.main(["convert", str(source), "--projekti", str(out / "syote.kma.json"), "--ulos", str(again)])
        == 0
    )
    second = ConversionProject.load(again / "syote.kma.json")
    assert [e.info.value for e in second.edits] == ["uusi"]
    assert ("uusi", None) in main_infos(second.units[0].proposal)


def test_l05_addition_is_not_made_when_the_user_removed_it(kb, policies):
    from kaavamaaraysavustaja.core.convert import convert_units
    from kaavamaaraysavustaja.core.ingest import parse

    text = """\
YLEISMÄÄRÄYS
Yleiskaavan ohjausvaikutus
Yleiskaavan RA ja R -alueilla yleiskaavaa voidaan käyttää MRL 72 §:n mukaisesti rakentamisen ohjaamiseen.
R(200) VAPAA-AJAN ASUMISEN JA MATKAILUN ALUE
Rakennuspaikalle saa sijoittaa yhteisöjen käyttöön tarkoitettua lomarakentamista.
"""
    choices = policies.resolve({"L-05": "sailytys_ja_rakenteinen_lisays"})
    units = parse(text).units
    marking = next(u for u in units if u.kind == "merkinta")
    removal = workflow.edit_for(
        marking,
        edit_log.REMOVE,
        edit_log.ref(kb, "RY_Kaavamaarayksen_Lisatiedonlaji", "rakennusluvanPeruste"),
        value=CodeRef("http://uri.suomi.fi/codelist/rytj/oikeusvaik_YK/code/12"),
    )
    project = convert_units(kb, units, choices, name="testi", edits=[removal])
    target = next(u for u in project.units if u.heading == "VAPAA-AJAN ASUMISEN JA MATKAILUN ALUE")
    infos = [i.type.value for reg in target.proposal.regulations for i in reg.additional_infos]
    assert "rakennusluvanPeruste" not in infos
    assert any("ei lisätty, koska käyttäjä on poistanut sen" in r.claim for r in target.proposal.rationale)


# -- the language model ----------------------------------------------------------------------------


def model_answer(request):
    task = json.loads(request.task_input)
    return {
        "ryhmat": [
            {
                "otsikko": task["yksikko"]["otsikko"],
                "kirjaintunnus": "TP",
                "ryhmatyyppi": "kaavakohde",
                "geometria": ["alue"],
                "maaraykset": [
                    {
                        "laji": "tyopaikkojenAlue",
                        "arvo": None,
                        "lisatiedot": [{"laji": "paakayttotarkoitus", "arvo": None}],
                        "sanallisen_lajit": [],
                        "tekstiviitteet": [],
                    },
                    {
                        "laji": "sanallinenMaarays",
                        "arvo": task["yksikko"]["teksti"],
                        "lisatiedot": [],
                        "sanallisen_lajit": ["ymparistohairiot"],
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


def test_edited_group_is_not_sent_but_an_earlier_answer_is_reused(kb):
    from kaavamaaraysavustaja.core.hybrid import reuse_from_project

    request = workflow.ConversionRequest(heading=HEADING, text=TEXT, mode="vooka")
    project = workflow.rule_based(kb, request)
    provider = FakeProvider(model_answer)
    workflow.run_llm(kb, project, provider, "claude-opus-5-5", budget=1.0)
    assert len(provider.requests) == 1
    unit = project.units[0]
    assert unit.proposal.regulations[0].type.value == "tyopaikkojenAlue"  # the model's structure
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=target)
    again = workflow.rule_based(kb, request)
    assert not needs_model(again.units[0])
    plan = workflow.llm_plan(kb, again, "claude", previous=project)
    assert plan.estimate.units == 0 and "Ei lähetettävää" in workflow.request_preview(
        kb, again, reuse=plan.reuse
    )
    report = workflow.run_llm(
        kb, again, provider, "claude-opus-5-5", budget=1.0, reuse=reuse_from_project(project)
    )
    assert len(provider.requests) == 1  # no new call
    assert report.totals()["uudelleenkaytettyja"] == 1
    p = again.units[0].proposal
    assert p.status == "muokattu" and p.model_check is not None
    assert main_infos(p) == [("paakayttotarkoitus", None), (QUALITY, None)]
    assert any(r.claim.startswith("Käyttäjä lisäsi lisätiedon") for r in p.rationale)


def test_requests_of_unedited_groups_do_not_change(kb):
    request = workflow.ConversionRequest(text=LEGEND, legend=True)
    plain = workflow.rule_based(kb, request)
    unit = plain.units[0]
    target = workflow.edit_view(kb, plain, unit).targets[0]
    edited = workflow.rule_based(
        kb,
        dataclasses.replace(
            request, edits=workflow.add_info(kb, "yleiskaava", [], unit, "uusi", target=target)
        ),
    )
    prompts = PromptSet.load(kb)
    before, after = RequestBuilder(kb, plain, prompts), RequestBuilder(kb, edited, prompts)
    assert before.system == after.system and before.static_context == after.static_context
    assert before.task(plain.units[1]) == after.task(edited.units[1])
    assert needs_model(plain.units[0]) == needs_model(plain.units[0]) and not needs_model(edited.units[0])


def test_no_unexplained_identifiers_in_the_edit_view(kb):
    from tests.unit.test_workflow_palaute import unexplained_ids

    request, project = with_code(kb)
    unit = project.units[0]
    target = workflow.edit_view(kb, project, unit).targets[0]
    request.edits = workflow.add_info(kb, "yleiskaava", [], unit, QUALITY, target=target)
    again = workflow.rule_based(kb, request)
    view = workflow.edit_view(kb, again, again.units[0], request.edits)
    texts = [view.message, view.pending, *(t.label for t in view.targets)]
    texts += [i.label for t in view.targets for i in t.items]
    for text in texts:
        assert unexplained_ids(text) == [], text
    assert unexplained_ids(workflow.detail_html(kb, again.units[0])) == []
