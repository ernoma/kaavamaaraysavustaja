"""Decision log: user answers, scope and re-runs (plan 6.10, ADR-0014)."""

from pathlib import Path

import pytest
import yaml

from kaavamaaraysavustaja.core import decisions as log
from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.evaluation import structure_of
from kaavamaaraysavustaja.core.ingest import parse
from kaavamaaraysavustaja.core.model import ConversionProject

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "kartta1_otos.txt"


def convert(kb, policies, decisions=None):
    units = parse(GOLDEN.read_text(encoding="utf-8")).units
    return convert_units(kb, units, policies.resolve(), name="testi", decisions=decisions)


def unit_by(project, heading):
    return next(u for u in project.units if u.heading == heading)


def test_parse_and_validate():
    [d] = log.parse_decisions([{"kysymys": "u004-K1", "valinta": "aluevaraus", "laajuus": "projekti"}])
    assert (d.unit_id, d.kind, d.option, d.scope) == ("u004", "K1", "aluevaraus", "projekti")
    with pytest.raises(log.DecisionError, match="linjauskirjastossa"):
        log.parse_decisions([{"kysymys": "u004-K1", "valinta": "x", "laajuus": "linjaus"}])
    with pytest.raises(log.DecisionError, match="valinta"):
        log.parse_decisions([{"kysymys": "u004-K1"}])
    with pytest.raises(log.DecisionError, match="tuntemattomat"):
        log.parse_decisions([{"kysymys": "u004-K1", "valinta": "x", "outo": 1}])


def test_k1_reservation_changes_the_structure(kb, policies):
    decisions = log.parse_decisions(
        [{"otsikko": "TÄYDENTYVÄ KESKUSTA", "tunnus": "c-1", "tyyppi": "K1", "valinta": "aluevaraus"}]
    )
    project = convert(kb, policies, decisions)
    unit = unit_by(project, "TÄYDENTYVÄ KESKUSTA")
    assert structure_of(unit.proposal) == ["keskustatoimintojenAlue(paakayttotarkoitus)"]
    k1 = next(q for q in unit.proposal.questions if q.kind == "K1")
    assert (k1.answer, k1.resolved_by) == ("aluevaraus", "kayttaja")
    assert project.decisions[0].question_id == f"{unit.id}-K1"


def test_geometry_answer_feeds_the_conversion(kb, policies):
    project = convert(kb, policies)
    unit = unit_by(project, "VAIHTOPYSÄKKI")
    assert any(q.kind == "K8" and q.is_open for q in unit.proposal.questions)
    decisions = log.parse_decisions([{"kysymys": f"{unit.id}-K8", "valinta": "piste"}])
    project = convert(kb, policies, decisions)
    unit = unit_by(project, "VAIHTOPYSÄKKI")
    assert unit.proposal.geometry_types == ["piste"]
    assert not any(q.kind == "K8" and q.is_open for q in unit.proposal.questions)


def test_project_scope_applies_to_similar_units(kb, policies):
    project = convert(kb, policies)
    k5 = [u for u in project.units if any(q.kind == "K5" and q.is_open for q in u.proposal.questions)]
    loma = [u for u in k5 if "LOMA-ASUNTOALUE" in u.heading]
    assert len(loma) == 2
    decisions = log.parse_decisions(
        [{"otsikko": loma[0].heading, "tyyppi": "K5", "valinta": "lahin_koodi", "laajuus": "merkinta"}]
    )
    project = convert(kb, policies, decisions)
    answered = [
        u for u in project.units if any(q.kind == "K5" and q.resolved_by for q in u.proposal.questions)
    ]
    assert [u.heading for u in answered] == [loma[0].heading]
    # Same letter-code-less heading base: "yhteisöjen" variant is not similar; a project-wide
    # answer reaches units with the same base heading or text only.
    decisions[0].scope = "projekti"
    project = convert(kb, policies, decisions)
    answered = [
        u for u in project.units if any(q.kind == "K5" and q.resolved_by for q in u.proposal.questions)
    ]
    assert loma[0].heading in [u.heading for u in answered]


def test_invalid_option_is_reported(kb, policies):
    decisions = log.parse_decisions(
        [{"otsikko": "TÄYDENTYVÄ KESKUSTA", "tunnus": "c-1", "tyyppi": "K1", "valinta": "kumpikin"}]
    )
    project = convert(kb, policies, decisions)
    warnings = project.provenance[0].details["ratkaisujen_varoitukset"]
    assert any("ei ole vaihtoehto" in w for w in warnings)


def test_rerun_keeps_decisions(kb, policies, tmp_path):
    decisions = log.parse_decisions(
        [{"otsikko": "TÄYDENTYVÄ KESKUSTA", "tunnus": "c-1", "tyyppi": "K1", "valinta": "aluevaraus"}]
    )
    first = convert(kb, policies, decisions)
    path = tmp_path / "p.kma.json"
    first.save(path)
    loaded = ConversionProject.load(path)
    again = convert(kb, policies, log.merge_decisions(loaded.decisions, []))
    unit = unit_by(again, "TÄYDENTYVÄ KESKUSTA")
    assert structure_of(unit.proposal) == ["keskustatoimintojenAlue(paakayttotarkoitus)"]
    newer = log.parse_decisions(
        [{"otsikko": "TÄYDENTYVÄ KESKUSTA", "tunnus": "c-1", "tyyppi": "K1", "valinta": "osa_alue"}]
    )
    merged = log.merge_decisions(loaded.decisions, newer)
    assert len(merged) == 1 and merged[0].option == "osa_alue"


def test_template_is_valid_settings_yaml(kb, policies):
    project = convert(kb, policies)
    text = log.template(project)
    assert yaml.safe_load(text) == {"ratkaisut": None}
    uncommented = "\n".join(
        line[2:] if line.startswith("# ") and line[2:].startswith(("- ", "  ")) else line
        for line in text.splitlines()
    )
    parsed = log.parse_decisions(yaml.safe_load(uncommented)["ratkaisut"])
    assert len(parsed) == sum(len(u.proposal.open_questions()) for u in project.units)
