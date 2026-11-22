"""Golden test data v1 (30 units of map 1): quality gate for the rule-based conversion.

The expected results are developer drafts (``tila: vahvistamaton``). The thresholds below are
the phase 1 results; a change that lowers them must be justified (plan 10.4).
"""

from pathlib import Path

import pytest
import yaml

from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.evaluation import evaluate
from kaavamaaraysavustaja.core.ingest import normalization_preserves_content, parse
from kaavamaaraysavustaja.exporters import arho_yaml, ryhti_json
from kaavamaaraysavustaja.validation.schema import validate_fragments

HERE = Path(__file__).parent
TEXT = HERE / "kartta1_otos.txt"
EXPECTED = HERE / "kartta1_odotetut.yaml"


@pytest.fixture(scope="module")
def expected():
    return yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def project(kb, policies):
    result = parse(TEXT.read_text(encoding="utf-8"))
    assert result.warnings == []
    return convert_units(kb, result.units, policies.resolve(), name="testiaineisto v1")


def test_thirty_units(project, expected):
    assert len(project.units) == 30
    assert expected["tila"] == "vahvistamaton"
    assert len(expected["yksikot"]) == 30


def test_verbal_text_is_source_text_character_by_character(project):
    """R-19 and the plan 2.3 target: 0 changes to the text of the plan in force."""
    for unit in project.units:
        assert normalization_preserves_content(
            unit.raw_text, unit.normalized_text, unit.normalization_diff
        ), unit.id
        verbal = [r for r in unit.proposal.regulations if r.value and r.value.data_type == "LocalizedText"]
        if unit.normalized_text and unit.proposal.kind != "ei_maarays":
            assert "\n\n".join(r.value.text["fin"] for r in verbal) == unit.normalized_text, unit.id
        assert not [r for r in unit.proposal.rule_results if r.rule_id == "R-19" and r.severity == "virhe"], (
            unit.id
        )


def test_fragments_pass_schema(kb, project):
    fragments = ryhti_json.project_fragments(project)
    assert fragments["planRegulationGroups"] and fragments["generalRegulationGroups"]
    assert validate_fragments(fragments, kb.load_schema()) == {}


def test_arho_library_codes_exist(kb, project):
    """Proxy for Arho's TemplateSyntaxError: every code must be a valid code of the code lists."""
    loaded = yaml.safe_load(arho_yaml.dumps(arho_yaml.library(project, include_incomplete=True)))
    assert loaded["format_version"] == 2
    for group in loaded["plan_regulation_groups"]:
        for reg in group["plan_regulations"]:
            code = kb.index.get("RY_Kaavamaarayslaji", reg["regulation_code"])
            assert code and code.is_valid and not code.header_level, reg["regulation_code"]
            for info in reg.get("additional_information", []):
                assert kb.index.get("RY_Kaavamaarayksen_Lisatiedonlaji", info["type"]), info
            for verbal in reg.get("verbal_regulation_types", []):
                assert kb.index.get("RY_Sanallisen_Kaavamaarayksen_Laji", verbal), verbal


def test_expected_codes_exist(kb, expected):
    for item in expected["yksikot"]:
        for option in [item.get("rakenne", []), *item.get("hyvaksyttavat", [])]:
            for structure in option:
                code, _, rest = structure.partition("(")
                assert kb.index.get("RY_Kaavamaarayslaji", code), structure
                for info in filter(None, rest.rstrip(")").split(",")):
                    name, _, value = info.partition("=")
                    assert kb.index.get("RY_Kaavamaarayksen_Lisatiedonlaji", name), structure
                    if value:
                        assert kb.index.get("RY_Kaavamaarayslaji", value), structure


def test_quality_gate(project, expected):
    evaluation = evaluate(project, expected)
    assert evaluation.unmatched == []
    m = evaluation.metrics()
    assert m["ryhmätyyppi oikein"] == (30, 30)
    assert m["pääkoodin osuvuus"][0] >= 19
    assert m["rakenteen osuvuus"][0] >= 18
    assert m["tunnetuista kysymyksistä tunnistettu"][0] >= 28
    hit, total = m["sellaisenaan hyväksyttävistä oikein"]
    assert hit == total and total >= 11
    hit, total = m["korkean varmuuden ehdotuksista oikein"]
    assert hit == total
    assert evaluation.text_changes == 0


def test_cli_convert_end_to_end(tmp_path):
    from kaavamaaraysavustaja.cli import main

    assert main(["convert", str(TEXT), "--ulos", str(tmp_path), "--tiedostonimi", "k1", "--html"]) == 0
    for name in [
        "k1.kma.json",
        "k1.arho.yaml",
        "k1.ryhti.json",
        "k1_raportti.md",
        "k1_raportti.csv",
        "k1_raportti.html",
    ]:
        assert (tmp_path / name).stat().st_size > 0, name
    assert main(["validate", str(tmp_path / "k1.kma.json")]) == 0


def test_cli_locked_or_unknown_policy_is_an_error(tmp_path):
    from kaavamaaraysavustaja.cli import EXIT_USAGE, main

    assert main(["convert", str(TEXT), "--ulos", str(tmp_path), "--linjaus", "L-03=aiheittain"]) == EXIT_USAGE
    assert main(["convert", str(TEXT), "--ulos", str(tmp_path), "--linjaus", "L-99=x"]) == EXIT_USAGE
