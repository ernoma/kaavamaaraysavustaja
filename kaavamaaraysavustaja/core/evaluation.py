"""Evaluation against the golden test data (plan 2.3 and 10.3).

Metrics that can be measured without users: main code and structure accuracy, letter code
accuracy, F1 of additional information and of verbal regulation types, question coverage,
automation rate, calibration of the confidence levels, text integrity and cost and time per
unit. Expected results are developer drafts until planners confirm them (``tila: vahvistamaton``).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from kaavamaaraysavustaja.core.model import ConversionProject, GroupProposal, SourceUnit
from kaavamaaraysavustaja.exporters.report import is_automatable

VERBAL = {"sanallinenMaarays", "suunnittelumaarays", "rakentamismaarays", "suojelumaarays"}
LEVELS = ("korkea", "keskitaso", "matala")


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


def info_pairs(structure: list[str]) -> set[str]:
    """``laji(a,b=c)`` → {``laji:a``, ``laji:b=c``} (additional information per regulation)."""
    pairs = set()
    for item in structure:
        code, _, rest = item.partition("(")
        for info in filter(None, rest.rstrip(")").split(",")):
            pairs.add(f"{code}:{info}")
    return pairs


def verbal_types_of(proposal: GroupProposal) -> set[str]:
    return {v.value for reg in proposal.regulations for v in reg.verbal_types}


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
    info_found: set[str] = field(default_factory=set)
    info_expected: set[str] = field(default_factory=set)
    verbal_found: set[str] = field(default_factory=set)
    verbal_expected: set[str] = field(default_factory=set)
    verbal_allowed: set[str] = field(default_factory=set)

    @property
    def missing_questions(self) -> set[str]:
        return self.questions_expected - self.questions_found

    @property
    def accepted_as_such(self) -> bool:
        """Proxy for 'the proposal is accepted as such': automatable and correct."""
        return self.automatable and self.structure_ok and self.letter_ok is not False


def f1(tp: int, predicted: int, relevant: int) -> tuple[float, float, float]:
    precision = tp / predicted if predicted else 1.0
    recall = tp / relevant if relevant else 1.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, score


@dataclass
class Evaluation:
    results: list[UnitResult] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    text_changes: int = 0
    units_total: int = 0

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
            "hyväksytään sellaisenaan (ehdokas ja oikein)": self.share([x.accepted_as_such for x in r]),
            "korkean varmuuden ehdotuksista oikein": self.share([x.structure_ok for x in high]),
        }

    def f1_scores(self) -> dict[str, tuple[float, float, float]]:
        structured = [x for x in self.results if x.expected.get("ryhmatyyppi") == "kaavakohde"]
        info_tp = sum(len(x.info_found & x.info_expected) for x in structured)
        info_pred = sum(len(x.info_found) for x in structured)
        info_rel = sum(len(x.info_expected) for x in structured)
        verbal = [x for x in self.results if x.expected.get("sanallisen_lajit")]
        v_tp_p = sum(len(x.verbal_found & (x.verbal_expected | x.verbal_allowed)) for x in verbal)
        v_pred = sum(len(x.verbal_found) for x in verbal)
        v_tp_r = sum(len(x.verbal_found & x.verbal_expected) for x in verbal)
        v_rel = sum(len(x.verbal_expected) for x in verbal)
        precision = v_tp_p / v_pred if v_pred else 1.0
        recall = v_tp_r / v_rel if v_rel else 1.0
        verbal_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "lisätiedot": f1(info_tp, info_pred, info_rel),
            "sanallisen määräyksen lajit": (precision, recall, verbal_f1),
        }

    def calibration(self) -> dict[str, tuple[int, int]]:
        """Structure correct per confidence level (plan 6.9: high ≥ 98 %)."""
        by_level: dict[str, list[bool]] = defaultdict(list)
        for x in self.results:
            by_level[x.unit.proposal.confidence].append(x.structure_ok)
        return {level: self.share(by_level.get(level, [])) for level in LEVELS}


def _matches(item: dict[str, Any], unit: SourceUnit) -> bool:
    if (unit.heading, unit.letter_code) != (item.get("otsikko"), item.get("tunnus")):
        return False
    return "kartta" not in item or item["kartta"] == unit.map


def evaluate(project: ConversionProject, expected: dict[str, Any]) -> Evaluation:
    """Expectations are matched to units in order (several units may share a heading)."""
    evaluation = Evaluation(units_total=len(project.units))
    used: set[str] = set()
    for item in expected["yksikot"]:
        unit = next((u for u in project.units if u.id not in used and _matches(item, u)), None)
        if unit is None or unit.proposal is None:
            evaluation.unmatched.append(str(item.get("otsikko")))
            continue
        used.add(unit.id)
        p = unit.proposal
        found = structure_of(p)
        options = [sorted(item.get("rakenne", []))] + [sorted(alt) for alt in item.get("hyvaksyttavat", [])]
        structure_ok = found in options
        main_ok = any(main_codes(found) == main_codes(option) for option in options)
        reference = found if structure_ok else options[0]
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
                info_found=info_pairs(found),
                info_expected=info_pairs(reference),
                verbal_found=verbal_types_of(p),
                verbal_expected=set(item.get("sanallisen_lajit", [])),
                verbal_allowed=set(item.get("sanallisen_lajit_muut", [])),
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


def combine(evaluations: list[Evaluation]) -> Evaluation:
    combined = Evaluation()
    for e in evaluations:
        combined.results += e.results
        combined.unmatched += e.unmatched
        combined.text_changes += e.text_changes
        combined.units_total += e.units_total
    return combined


def model_costs(projects: list[ConversionProject]) -> dict[str, float]:
    """Cost and time of the model steps (plan 10.3: dollars and seconds per unit)."""
    calls = cost = seconds = 0.0
    units = sum(len(p.units) for p in projects)
    for project in projects:
        for step in project.provenance:
            if step.step == "kielimalli":
                calls += step.details.get("kutsuja", 0)
                cost += step.details.get("kustannus_usd", 0.0)
                seconds += step.details.get("kesto_s", 0.0)
    return {
        "yksikoita": units,
        "kutsuja": calls,
        "kustannus_usd": cost,
        "kesto_s": seconds,
        "usd_per_yksikko": cost / units if units else 0.0,
        "usd_per_kutsu": cost / calls if calls else 0.0,
        "s_per_kutsu": seconds / calls if calls else 0.0,
    }


def percent(value: tuple[int, int]) -> str:
    hit, total = value
    return f"{hit}/{total} ({100 * hit / total:.0f} %)" if total else "–"
