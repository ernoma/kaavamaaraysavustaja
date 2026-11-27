"""Exporters: Ryhti fragments (schema), Arho library YAML, report; Syke client parsing."""

import csv
import io
import json

import pytest
import yaml

from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.ingest import parse
from kaavamaaraysavustaja.exporters import arho_yaml, report, ryhti_json
from kaavamaaraysavustaja.validation.schema import validate, validate_fragments
from kaavamaaraysavustaja.validation.syke_public_api import parse_findings, validate_url

TEXT = """\
@kartta Kartta 1 - Yhdyskuntarakenne
YLEISMÄÄRÄYS
Yleiskaavan ohjausvaikutus
Yleiskaavan RA ja R -alueilla yleiskaavaa voidaan käyttää rakentamisen ohjaamiseen.
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille. Alueen suunnittelussa tulee kiinnittää huomiota kulttuuriympäristön arvoihin.
c-1 TÄYDENTYVÄ KESKUSTA
Aluetta kehitetään täydennettävänä keskustatoimintojen alueena. Vähittäiskaupan kerrosalan enimmäismitoitus Kalevassa on 70 000 k-m².
RAUTATIE
YLEISKAAVA-ALUEEN RAJA
"""


@pytest.fixture(scope="module")
def project(kb, policies):
    return convert_units(
        kb, parse(TEXT).units, policies.resolve(), name="testi", map_title="Kartta 1 - Yhdyskuntarakenne"
    )


def test_ryhti_fragments_validate_against_schema(kb, project):
    fragments = ryhti_json.project_fragments(project)
    assert len(fragments["planRegulationGroups"]) == 3  # informative marking left out
    assert len(fragments["generalRegulationGroups"]) == 1
    assert validate_fragments(fragments, kb.load_schema()) == {}


def test_code_value_data_type_is_capitalised(project):
    groups = {
        g["letterIdentifier"]: g
        for g in ryhti_json.project_fragments(project)["planRegulationGroups"]
        if "letterIdentifier" in g
    }
    info = groups["c-1"]["planRegulations"][0]["additionalInformations"][1]
    assert info["value"] == {
        "dataType": "Code",
        "code": "http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji/code/keskustatoimintojenAlue",
        "codeList": "http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji",
    }
    verbal = groups["C"]["planRegulations"][1]
    assert verbal["value"]["dataType"] == "LocalizedText"
    assert verbal["verbalRegulations"][0].startswith(
        "http://uri.suomi.fi/codelist/rytj/RY_Sanallisen_Kaavamaarayksen_Laji/code/"
    )


def test_schema_rejects_wrong_data_type(kb, project):
    group = ryhti_json.project_fragments(project)["planRegulationGroups"][1]
    group["planRegulations"][0]["additionalInformations"][1]["value"]["dataType"] = "code"
    assert validate(group, "PlanRegulationGroup", kb.load_schema())


def test_synthetic_plan(project):
    proposals = [u.proposal for u in ryhti_json.exported_units(project)]
    plan = ryhti_json.synthetic_plan(proposals)
    assert (
        len(plan["planObjects"]) == len(plan["planRegulationGroups"]) == 3
    )  # C is the reservation, no carrier
    assert len(plan["generalRegulationGroups"]) == 1
    kinds = {o["geometry"]["geometry"]["type"] for o in plan["planObjects"]}
    assert kinds == {"Polygon", "LineString"}  # Rautatie is a line in annex 4
    assert plan == ryhti_json.synthetic_plan(proposals)  # deterministic keys


def test_arho_library_format(project):
    data = arho_yaml.library(project, name="Testikirjasto")
    text = arho_yaml.dumps(data)
    loaded = yaml.safe_load(text)
    assert text.startswith("format_version: 2\n")
    assert loaded["library_type"] == "regulation_group"
    assert loaded["name"] == "Testikirjasto"
    groups = {g["heading"]["fin"]: g for g in loaded["plan_regulation_groups"]}
    assert set(groups) == {"Keskustatoimintojen alue", "Täydentyvä keskusta", "Rautatie"}
    c1 = groups["Täydentyvä keskusta"]
    assert c1["letter_code"] == "c-1" and c1["geometry"] == ["Alue"]
    assert c1["plan_regulations"][0] == {
        "regulation_code": "kehittamisvyohyke",
        "additional_information": [
            {"type": "osaAlue"},
            {"type": "kayttotarkoituskohdistus", "code_value": "keskustatoimintojenAlue"},
        ],
    }
    verbal = c1["plan_regulations"][1]
    assert verbal["value_data_type"] == "LocalizedText"
    source = next(u for u in project.units if u.letter_code == "c-1").normalized_text
    assert verbal["text_value"] == {"fin": source}  # character by character after a YAML round trip
    assert set(verbal["verbal_regulation_types"]) >= {"kaupanOhjaus"}
    assert "geometry" not in groups["Keskustatoimintojen alue"] or groups["Keskustatoimintojen alue"][
        "geometry"
    ] == ["Alue"]
    for group in loaded["plan_regulation_groups"]:  # Arho drops empty values (TemplateManager._clean_data)
        assert all(v not in (None, "", []) for v in group.values())


def test_long_text_is_not_folded(kb, policies):
    long_text = "KESKUSTATOIMINTOJEN ALUE\n" + " ".join(["Alue varataan julkisille palveluille."] * 60) + "\n"
    project = convert_units(kb, parse(long_text).units, policies.resolve(), name="pitkä")
    loaded = yaml.safe_load(arho_yaml.dumps(arho_yaml.library(project, include_incomplete=True)))
    text = loaded["plan_regulation_groups"][0]["plan_regulations"][1]["text_value"]["fin"]
    assert text == project.units[0].normalized_text


def test_incomplete_groups_left_out_by_default(kb, policies):
    project = convert_units(
        kb, parse("TUNTEMATON MERKINTÄ\nTeksti tästä.\n").units, policies.resolve(), name="x"
    )
    assert arho_yaml.library(project).get("plan_regulation_groups") is None
    assert len(arho_yaml.library(project, include_incomplete=True)["plan_regulation_groups"]) == 1


def test_report(kb, project):
    md = report.markdown(project, kb)
    assert "## Linjausvalinnat" in md and "L-03: ei_pilkota (suositeltu oletus)" in md
    assert "K1 Aluevaraus vai osa-alue?" in md
    assert "quality/req-planregulationgroup-letteridentifier-not-null" not in md or "Ryhti" in md
    rows = list(csv.DictReader(io.StringIO(report.csv_text(project))))
    assert [r["yksikko"] for r in rows] == [u.id for u in project.units]
    c1 = next(r for r in rows if r["kirjaintunnus"] == "c-1")
    assert c1["avoimet_kysymykset"] == "K1" and c1["sellaisenaan"] == "ei"
    html = report.html_text(project, kb)
    assert html.startswith("<!doctype html>") and "Täydentyvä keskusta" in html


def test_syke_url_and_findings():
    url = validate_url(plan_type="http://uri.suomi.fi/codelist/rytj/RY_Kaavalaji/code/21")
    assert url.endswith("/api/Plan/Validate?planType=21&administrativeAreaIdentifiers=837")
    assert url.startswith("https://api-test.ymparisto.fi/")
    body = {
        "errors": {
            "planRegulationGroups[0]": [
                {
                    "ruleId": "quality__req_planregulationgroup_letteridentifier_not_null",
                    "localizedMessage": {"fi": "Kirjaintunnus puuttuu"},
                },
            ]
        },
        "warnings": [{"ruleId": "lifecycle__req_approval_date_mandatory", "message": "x"}],
    }
    findings = parse_findings(body)
    assert [f.rule for f in findings] == [
        "quality/req-planregulationgroup-letteridentifier-not-null",
        "lifecycle/req-approval-date-mandatory",
    ]
    assert findings[0].message == "Kirjaintunnus puuttuu"
    assert [f.plan_level for f in findings] == [False, True]
    assert parse_findings({"errors": {"planKey": ["pakollinen"]}})[0].message == "pakollinen"


def test_project_json_is_written_and_read(tmp_path, project):
    from kaavamaaraysavustaja.core.model import ConversionProject

    path = tmp_path / "p.kma.json"
    project.save(path)
    assert ConversionProject.load(path) == project
    assert json.loads(path.read_text(encoding="utf-8"))["format_version"] == 2  # 2: structure edits


@pytest.mark.live
def test_syke_live(kb, project):
    """Needs RYHTI_API_KEY and network: python -m pytest -m live."""
    from kaavamaaraysavustaja.validation.syke_public_api import api_key, validate_plan

    key = api_key()
    if not key:
        pytest.skip("RYHTI_API_KEY puuttuu")
    unit = next(u for u in project.units if u.heading == "RAUTATIE")
    result = validate_plan(ryhti_json.synthetic_plan([unit.proposal], name="live"), key=key)
    assert result.status == 200, result.body


def test_schema_discriminates_numeric_values_by_data_type(kb):
    """Ryhti's OpenAPI lists the value types in oneOf without a discriminator: an integer matches
    four of them. Validation picks the alternative by dataType (ADR-0017)."""
    schema = kb.load_schema()
    value = {"dataType": "PositiveNumeric", "number": 6000, "unitOfMeasure": "k-m²"}
    regulation = {
        "planRegulationKey": "00000000-0000-0000-0000-000000000001",
        "lifeCycleStatus": "http://uri.suomi.fi/codelist/rytj/kaavaelinkaari/code/03",
        "type": "http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji/code/sallittuKerrosala",
        "value": value,
    }
    assert not [e for e in validate(regulation, "PlanRegulation", schema) if e.startswith("value")]
    wrong = {**regulation, "value": {**value, "number": 0.5}}
    assert [e for e in validate(wrong, "PlanRegulation", schema) if e.startswith("value")]
    decimal = {**regulation, "value": {"dataType": "PositiveDecimal", "number": 0.6}}
    assert not [e for e in validate(decimal, "PlanRegulation", schema) if e.startswith("value")]
