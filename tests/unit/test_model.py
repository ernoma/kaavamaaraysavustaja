import json

import pytest

from kaavamaaraysavustaja.core.model import (
    AdditionalInfo,
    CodeRef,
    ConversionProject,
    GroupProposal,
    InterpretationQuestion,
    Meta,
    NormalizationChange,
    PolicyChoice,
    QuestionOption,
    Rationale,
    Regulation,
    SourcePlan,
    SourceUnit,
    Value,
)

URI = "http://uri.suomi.fi/codelist/rytj/"


def sample_project() -> ConversionProject:
    proposal = GroupProposal(
        key="g-1",
        kind="kaavakohde",
        title={"fin": "Täydentyvä keskusta"},
        letter_code="c-1",
        geometry_types=["alue"],
        regulations=[
            Regulation(
                key="r-1",
                type=CodeRef(URI + "RY_Kaavamaarayslaji/code/kehittamisvyohyke", "2025-10-07"),
                additional_infos=[
                    AdditionalInfo(
                        CodeRef(URI + "RY_Kaavamaarayksen_Lisatiedonlaji/code/osaAlue", "2026-01-12")
                    ),
                    AdditionalInfo(
                        CodeRef(URI + "RY_Kaavamaarayksen_Lisatiedonlaji/code/kayttotarkoituskohdistus"),
                        Value("Code", code=CodeRef(URI + "RY_Kaavamaarayslaji/code/keskustatoimintojenAlue")),
                    ),
                ],
            ),
            Regulation(
                key="r-2",
                type=CodeRef(URI + "RY_Kaavamaarayslaji/code/sanallinenMaarays"),
                value=Value("LocalizedText", text={"fin": "Aluetta kehitetään."}),
                verbal_types=[CodeRef(URI + "RY_Sanallisen_Kaavamaarayksen_Laji/code/kehittamisperiaate")],
                text_span=(0, 19),
                rationale=[Rationale("VOOKA-tila", "saanto", "korkea", quote="Aluetta kehitetään.")],
            ),
        ],
        questions=[
            InterpretationQuestion(
                "q-1",
                "K1",
                "Aluevaraus vai osa-alue?",
                [QuestionOption("osa_alue", "Osa-alue"), QuestionOption("aluevaraus", "Aluevaraus")],
                recommendation="osa_alue",
            )
        ],
    )
    unit = SourceUnit(
        id="u-1",
        kind="merkinta",
        raw_text="Aluetta kehite -\ntään.",
        normalized_text="Aluetta kehitetään.",
        normalization_diff=[NormalizationChange("tavutus", "kehite -\ntään", "kehitetään", line=3)],
        heading_raw="c-1 TÄYDENTYVÄ KESKUSTA",
        letter_code_raw="c-1",
        section_path=["MAANKÄYTTÖ"],
        page=3,
        source_plans=[SourcePlan("Kantakaupungin yleiskaava 2040", "20.1.2020")],
        proposal=proposal,
    )
    return ConversionProject(
        meta=Meta(map="Kartta 1 - Yhdyskuntarakenne", knowledge_version="TP-test"),
        units=[unit],
        policy_choices=[PolicyChoice("L-03", "ei_pilkota", "oletus", 1)],
    )


def test_round_trip():
    project = sample_project()
    data = project.to_dict()
    json.dumps(data)  # plain JSON
    assert ConversionProject.from_dict(data) == project
    assert ConversionProject.from_json(project.to_json()) == project


def test_save_and_load(tmp_path):
    project = sample_project()
    path = tmp_path / "x.kma.json"
    project.save(path)
    assert ConversionProject.load(path) == project


def test_code_ref_parts():
    ref = CodeRef(URI + "RY_Kaavamaarayslaji/code/keskustatoimintojenAlue", "2025-10-07")
    assert ref.value == "keskustatoimintojenAlue"
    assert ref.codelist == "RY_Kaavamaarayslaji"
    assert ref.codelist_uri == URI + "RY_Kaavamaarayslaji"


def test_unknown_field_rejected():
    data = sample_project().to_dict()
    data["meta"]["unexpected"] = 1
    with pytest.raises(ValueError, match="tuntemattomat"):
        ConversionProject.from_dict(data)


def test_newer_format_rejected():
    data = sample_project().to_dict()
    data["format_version"] = 99
    with pytest.raises(ValueError, match="uudempi"):
        ConversionProject.from_dict(data)


def test_helpers():
    project = sample_project()
    assert project.policy("L-03") == "ei_pilkota"
    assert project.policy("L-99") is None
    proposal = project.unit("u-1").proposal
    assert [q.id for q in proposal.open_questions()] == ["q-1"]
