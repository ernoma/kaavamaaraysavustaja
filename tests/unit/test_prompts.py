"""Prompts are data in the knowledge base (CLAUDE.md rule 3); v3 adds the drafting mode."""

from pathlib import Path

import pytest

from kaavamaaraysavustaja.core.llm.prompts import PromptSet
from kaavamaaraysavustaja.core.model import SourceUnit


def test_prompt_set_loads(kb):
    prompts = PromptSet.load(kb)
    assert prompts.label == "prompts/v3 v3"
    assert [q["tyyppi"] for q in prompts.question_types] == [f"K{n}" for n in range(1, 16)]
    assert "K8" in prompts.model_resolvable() and "K1" not in prompts.model_resolvable()
    assert "VOOKA" in prompts.system


def test_static_context_lists_codes_annex_questions_and_policies(kb, policies):
    prompts = PromptSet.load(kb)
    text = prompts.static_context(kb, "yleiskaava", "vooka", policies.resolve())
    assert "{{" not in text
    assert "- keskustatoimintojenAlue: Keskustatoimintojen alue [aluevaraus]" in text
    assert "- muuArkeologinenKohde:" not in text  # retired code is not offered
    assert "K2 Sekoittunut käyttötarkoitus" in text and "Ei tätä:" in text
    assert "L-04: sanallinenMaarays (suositeltu oletus)" in text
    assert "eheytettavaTaiTiivistettava" in text
    assert text == prompts.static_context(kb, "yleiskaava", "vooka", policies.resolve())  # deterministic


def test_example_codes_exist(kb):
    for example in PromptSet.load(kb).examples:
        for reg in example["tulos"]["maaraykset"]:
            assert kb.index.get("RY_Kaavamaarayslaji", reg["laji"]), reg
            for info in reg.get("lisatiedot", []):
                assert kb.index.get("RY_Kaavamaarayksen_Lisatiedonlaji", info["laji"]), info
                if info.get("arvo"):
                    assert kb.index.get("RY_Kaavamaarayslaji", info["arvo"]), info
        for verbal in example["tulos"]["sanallisen_lajit"]:
            assert kb.index.get("RY_Sanallisen_Kaavamaarayksen_Laji", verbal), verbal


def test_example_search(kb):
    prompts = PromptSet.load(kb)
    unit = SourceUnit(
        "u1", "merkinta", "", "Aluetta kehitetään tiivistyvänä alueena.", heading="TIIVISTYVÄ ALUE"
    )
    chosen = prompts.select_examples(kb, unit)
    assert chosen and chosen[0]["tunnus"] == "E-02"
    assert len(chosen) <= prompts.max_examples
    general = SourceUnit("u2", "yleismaarays", "", "Hulevedet on käsiteltävä.", heading="Hulevedet")
    assert prompts.select_examples(kb, general)[0]["tunnus"] == "E-06"


GOLDEN = Path(__file__).resolve().parents[1] / "golden"


def test_v3_vooka_request_is_identical_to_v2(kb, policies):
    """ADR-0017: the drafting section must not change VOOKA requests (recorded v2 responses stay valid)."""
    from kaavamaaraysavustaja.core.convert import convert_units
    from kaavamaaraysavustaja.core.hybrid import RequestBuilder, plan_units
    from kaavamaaraysavustaja.core.ingest import parse

    v2, v3 = PromptSet.load(kb, "prompts/v2"), PromptSet.load(kb, "prompts/v3")
    choices = policies.resolve()
    assert v3.system_for("vooka") == v2.system
    assert v3.static_context(kb, "yleiskaava", "vooka", choices) == v2.static_context(
        kb, "yleiskaava", "vooka", choices
    )
    compared = 0
    for name in ("kartta1", "keskusta", "kartat2_4"):
        units = parse((GOLDEN / f"{name}_otos.txt").read_text(encoding="utf-8")).units
        project = convert_units(kb, units, choices, name=f"testiaineisto {name}")
        old, new = RequestBuilder(kb, project, v2), RequestBuilder(kb, project, v3)
        assert new.system == old.system and new.static_context == old.static_context
        for unit in plan_units(project)[0]:
            assert new.task(unit) == old.task(unit), unit.id
            compared += 1
    assert compared > 50


def test_v3_drafting_mode_has_its_own_instructions(kb, policies):
    prompts = PromptSet.load(kb)
    assert "laadintatila" in prompts.system_for("laadinta").lower()
    assert prompts.system_for("laadinta") != prompts.system_for("vooka")
    text = prompts.static_context(kb, "yleiskaava", "laadinta", policies.resolve())
    assert "{{" not in text
    assert "## Laadintatila: uuden määräyksen muunnos" in text
    assert "Laadintatila" not in prompts.static_context(kb, "yleiskaava", "vooka", policies.resolve())


@pytest.mark.parametrize("mode", ["vooka", "laadinta"])
def test_drafting_examples_only_in_drafting_mode(kb, mode):
    prompts = PromptSet.load(kb)
    ids = {e.get("tunnus") for e in prompts.all_examples(kb, mode)}
    assert ("E-L1" in ids) is (mode == "laadinta")
    assert "E-01" in ids


def test_drafting_example_search(kb):
    prompts = PromptSet.load(kb)
    unit = SourceUnit("u1", "merkinta", "", "Alue on tarkoitettu pientaloasumiselle.", heading="Pientaloalue")
    assert prompts.select_examples(kb, unit, "laadinta")[0]["tunnus"] == "E-L1"
    assert all(e.get("tila") != "laadinta" for e in prompts.select_examples(kb, unit, "vooka"))
