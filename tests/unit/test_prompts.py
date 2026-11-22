"""Prompts v1 are data in the knowledge base (CLAUDE.md rule 3)."""

from kaavamaaraysavustaja.core.llm.prompts import PromptSet
from kaavamaaraysavustaja.core.model import SourceUnit


def test_prompt_set_loads(kb):
    prompts = PromptSet.load(kb)
    assert prompts.label == "prompts/v1 v1"
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
