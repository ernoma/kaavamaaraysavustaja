import json

import pytest
import yaml

from tools import build_knowledge as bk


def sheet_findings(result, sheet, counted=True):
    return [f for f in result.findings if f.sheet == sheet and ((f.category in bk.COUNTED) == counted)]


def test_committed_knowledge_matches_fresh_build(build_result, root):
    stale = [path for path, content in build_result.files.items() if (root / path).read_bytes() != content]
    assert stale == [], "aja python tools/build_knowledge.py"


def test_row_counts(build_result):
    assert build_result.row_counts == {"Asemakaava": 256, "Yleiskaava": 360, "Maakuntakaava": 226}


def test_yleiskaava_has_13_conflicting_values(build_result):
    findings = sheet_findings(build_result, "Yleiskaava")
    assert len(findings) == 13
    values = {(f.row, f.category) for f in findings}
    assert (162, bk.RETIRED) in values  # muuArkeologinenKohde
    assert (46, bk.WRONG_COLUMN) in values  # tuulivoimalaAlue as lisätiedon laji
    assert (335, bk.PARSE) in values  # code;registryCode=...
    assert {(r, bk.UNKNOWN_CODELIST) for r in (358, 359, 360, 361)} <= values  # oikeusvaik_YK 11 / 12
    open_rows = {f.row for f in findings if not f.resolved}
    assert open_rows == {358, 359, 360, 361}


def test_other_sheets(build_result):
    assert len(sheet_findings(build_result, "Asemakaava")) == 5
    assert len(sheet_findings(build_result, "Maakuntakaava")) == 6
    assert all(f.resolved for f in sheet_findings(build_result, "Asemakaava"))
    assert all(f.resolved for f in sheet_findings(build_result, "Maakuntakaava"))
    whitespace = [
        f for f in sheet_findings(build_result, "Asemakaava", counted=False) if f.category == bk.WHITESPACE
    ]
    assert len(whitespace) == 5


def annex(build_result):
    return yaml.safe_load(build_result.files["knowledge/" + bk.ANNEX4_FILE])["kaavalajit"]


def test_annex_standard_regulation(build_result):
    entries = [e for e in annex(build_result)["yleiskaava"] if e["kirjaintunnus"] == "C"]
    assert entries[0]["otsikko"] == "Keskustatoimintojen alue"
    assert entries[0]["kaavamaarayslajit"] == ["keskustatoimintojenAlue"]
    assert entries[0]["lisatiedot"] == [{"laji": "paakayttotarkoitus"}]


def test_annex_corrections_applied(build_result):
    rows = {e["rivi"]: e for e in annex(build_result)["yleiskaava"]}
    assert rows[46]["lisatiedot"] == [
        {"laji": "paakayttotarkoitus"},
        {
            "laji": "kayttotarkoituskohdistus",
            "arvo": {"koodisto": bk.REGULATION_TYPE, "koodi": "tuulivoimalaAlue"},
        },
    ]
    assert rows[46]["korjaukset"] == ["YK-046-a", "YK-046-b", "YK-046-c"]
    assert rows[162]["kaavamaarayslajit"] == ["arkeologinenKohde"]
    assert "avoimet_havainnot" in rows[358]


def test_annex_has_no_retired_or_unknown_types(build_result, index):
    for entries in annex(build_result).values():
        for entry in entries:
            for code in entry["kaavamaarayslajit"]:
                assert isinstance(code, str), entry
                assert index.get(bk.REGULATION_TYPE, code).is_valid, entry


def test_correction_with_wrong_original_fails(root, index):
    checker = bk.CodeChecker(index.data["codelists"], set())
    wrong = {
        "id": "X-1",
        "valilehti": "Yleiskaava",
        "rivi": 162,
        "sarake": "kaavamaarayslaji_koodi",
        "alkuperainen": "http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji/code/jokuMuu",
        "korjattu": None,
    }
    with pytest.raises(SystemExit, match="X-1"):
        bk.read_annex(bk.single(root, bk.ANNEX_SOURCE), checker, [wrong])


def test_quality_report(build_result):
    report = build_result.files[bk.QUALITY_REPORT].decode("utf-8")
    assert "| Yleiskaava | 360 | 13 | 9 | 4 |" in report
    assert "muuArkeologinenKohde" in report


def test_schema_structure(build_result):
    schema = json.loads(build_result.files["knowledge/" + bk.SCHEMA_FILE])
    defs = schema["$defs"]
    assert set(bk.SCHEMA_ROOTS) <= set(defs)
    text = json.dumps(schema)
    assert "#/components/" not in text
    assert '"nullable"' not in text
    assert defs["PlanRegulationGroup"]["required"] == [
        "planRegulationGroupKey",
        "planRegulations",
        "titleOfPlanRegulation",
    ]


def test_schema_validates_example_group(build_result):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(build_result.files["knowledge/" + bk.SCHEMA_FILE])
    uri = "http://uri.suomi.fi/codelist/rytj/"
    group = {
        "planRegulationGroupKey": "6f1d2c9e-0000-4000-8000-000000000001",
        "titleOfPlanRegulation": {"fin": "Täydentyvä keskusta"},
        "letterIdentifier": "c-1",
        "groupNumber": None,
        "planRegulations": [
            {
                "planRegulationKey": "0b7e0000-0000-4000-8000-000000000002",
                "lifeCycleStatus": uri + "kaavaelinkaari/code/13",
                "type": uri + "RY_Kaavamaarayslaji/code/kehittamisvyohyke",
                "additionalInformations": [
                    {"type": uri + "RY_Kaavamaarayksen_Lisatiedonlaji/code/osaAlue"},
                    {
                        "type": uri + "RY_Kaavamaarayksen_Lisatiedonlaji/code/kayttotarkoituskohdistus",
                        "value": {
                            "dataType": "Code",
                            "code": uri + "RY_Kaavamaarayslaji/code/keskustatoimintojenAlue",
                            "codeList": uri + "RY_Kaavamaarayslaji",
                        },
                    },
                ],
            }
        ],
    }
    validator_schema = {"$ref": "#/$defs/PlanRegulationGroup", "$defs": schema["$defs"]}
    jsonschema.validate(group, validator_schema)
    group["planRegulations"][0]["type"] = uri + "RY_Kaavamaarayslaji/code/eiOle"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(group, validator_schema)


def test_validation_messages(build_result):
    text = build_result.files["knowledge/" + bk.MESSAGES_FILE].decode("utf-8-sig")
    lines = [line for line in text.splitlines() if line[:1].isdigit()]
    assert text.startswith("Nro,Sääntö_ID_en")
    assert "req-codelist-codevalue-headerlevel" in text
    assert len(lines) >= 240
