"""Evaluation against the golden test data (plan 2.3 and 10.3).

Metrics that can be measured without users: main code accuracy, structure accuracy,
letter code accuracy, question coverage, automation rate, accuracy of high-confidence
proposals and text integrity. Expected results are developer drafts until planners have
annotated them (``tila: vahvistamaton``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kaavamaaraysavustaja.core.model import ConversionProject, GroupProposal, SourceUnit
from kaavamaaraysavustaja.exporters.report import is_automatable

VERBAL = {"sanallinenMaarays", "suunnittelumaarays", "rakentamismaarays", "suojelumaarays"}


def structure_of(proposal: GroupProposal) -> list[str]:
    items = []
    for reg in proposal.regulations:
        if reg.type.value in VERBAL:
            continue
        infos = sorted(
            info.type.value + (f"={info.value.code.value}" if info.value and info.value.code else "")
            for info in reg.additional_infos
        )
        items.append(f"{reg.type.value}({','.join(infos)})")
    return sorted(items)


def main_codes(structure: list[str]) -> set[str]:
    return {item.split("(", 1)[0] for item in structure}


@dataclass
class UnitResult:
    unit: SourceUnit
    expected: dict[str, Any]
    structure_ok: bool
    main_ok: bool
    letter_ok: bool | None
    questions_expected: set[str]
    questions_found: set[str]
    automatable: bool

    @property
    def missing_questions(self) -> set[str]:
        return self.questions_expected - self.questions_found


@dataclass
class Evaluation:
    results: list[UnitResult] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    text_changes: int = 0

    def share(self, values: list[bool]) -> tuple[int, int]:
        return sum(values), len(values)

    def metrics(self) -> dict[str, tuple[int, int]]:
        r = self.results
        structured = [x for x in r if x.expected.get("ryhmatyyppi") == "kaavakohde"]
        high = [x for x in r if x.unit.proposal.confidence == "korkea"]
        automatable = [x for x in r if x.automatable]
        letters = [x.letter_ok for x in structured if x.letter_ok is not None]
        expected_q = sum(len(x.questions_expected) for x in r)
        found_q = sum(len(x.questions_expected & x.questions_found) for x in r)
        return {
            "pääkoodin osuvuus": self.share([x.main_ok for x in structured]),
            "rakenteen osuvuus": self.share([x.structure_ok for x in structured]),
            "kirjaintunnuksen osuvuus": self.share(letters),
            "ryhmätyyppi oikein": self.share(
                [x.unit.proposal.kind == x.expected.get("ryhmatyyppi") for x in r]
            ),
            "tunnetuista kysymyksistä tunnistettu": (found_q, expected_q),
            "hyväksyttävissä sellaisenaan": self.share([x.automatable for x in r]),
            "sellaisenaan hyväksyttävistä oikein": self.share([x.structure_ok for x in automatable]),
            "korkean varmuuden ehdotuksista oikein": self.share([x.structure_ok for x in high]),
        }


def evaluate(project: ConversionProject, expected: dict[str, Any]) -> Evaluation:
    evaluation = Evaluation()
    by_key = {(u.heading, u.letter_code): u for u in project.units}
    for item in expected["yksikot"]:
        unit = by_key.get((item["otsikko"], item.get("tunnus")))
        if unit is None or unit.proposal is None:
            evaluation.unmatched.append(item["otsikko"])
            continue
        p = unit.proposal
        found = structure_of(p)
        options = [sorted(item.get("rakenne", []))] + [sorted(alt) for alt in item.get("hyvaksyttavat", [])]
        structure_ok = found in options
        main_ok = any(main_codes(found) == main_codes(option) for option in options)
        letter_ok = None
        if "kirjaintunnus" in item:
            letter_ok = (p.letter_code or None) == item["kirjaintunnus"]
        evaluation.results.append(
            UnitResult(
                unit=unit,
                expected=item,
                structure_ok=structure_ok if p.kind == "kaavakohde" else p.kind == item.get("ryhmatyyppi"),
                main_ok=main_ok,
                letter_ok=letter_ok,
                questions_expected=set(item.get("kysymykset", [])),
                questions_found={q.kind for q in p.questions},
                automatable=is_automatable(p),
            )
        )
    evaluation.text_changes = sum(
        1
        for u in project.units
        if u.proposal
        for r in u.proposal.rule_results
        if r.rule_id == "R-19" and r.severity == "virhe"
    )
    return evaluation


def percent(value: tuple[int, int]) -> str:
    hit, total = value
    return f"{hit}/{total} ({100 * hit / total:.0f} %)" if total else "–"
