"""Interpretation questions and the decision log (plan 6.10, ADR-0014).

The user's answers come from the settings file (``ratkaisut``) or from an earlier project
(``kma convert --projekti``). Each answer is stored in the project (``decisions``) with its
scope: ``merkinta`` (this unit) or ``projekti`` (all similar units in the project). The scope
*Tampereen linjaus* is a locked policy in the policy library (ADR-0008) and is not set here.

Some answers change the conversion input before the rule-based step (K6 kind, K8 geometry,
K1 reservation vs. sub-area); all of them settle the question (``resolved_by = "kayttaja"``)
and are passed to the language model as resolved items.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kaavamaaraysavustaja.core import match
from kaavamaaraysavustaja.core.model import ConversionProject, Decision, InterpretationQuestion, SourceUnit

SCOPES = ("merkinta", "projekti")
FIELDS = {
    "kysymys",
    "yksikko",
    "otsikko",
    "tunnus",
    "tyyppi",
    "valinta",
    "laajuus",
    "perustelu",
    "ratkaisija",
    "aika",
}


class DecisionError(ValueError):
    pass


def parse_decisions(items: list[dict[str, Any]] | None) -> list[Decision]:
    """``ratkaisut`` of the settings file → decisions (validated)."""
    decisions = []
    for n, item in enumerate(items or [], 1):
        if not isinstance(item, dict):
            raise DecisionError(f"ratkaisut[{n}] ei ole sanakirja")
        unknown = sorted(set(item) - FIELDS)
        if unknown:
            raise DecisionError(f"ratkaisut[{n}]: tuntemattomat kentät {', '.join(unknown)}")
        scope = str(item.get("laajuus", "merkinta"))
        if scope == "linjaus":
            raise DecisionError(
                f"ratkaisut[{n}]: laajuus 'linjaus' tarkoittaa Tampereen linjausta, joka lukitaan "
                "linjauskirjastossa (knowledge/org/tampere/linjaukset.yaml, ADR-0008). Käytä merkinta tai projekti."
            )
        if scope not in SCOPES:
            raise DecisionError(f"ratkaisut[{n}]: laajuus on merkinta tai projekti, saatiin {scope!r}")
        question = str(item.get("kysymys") or "")
        kind = str(item.get("tyyppi") or (question.rsplit("-", 1)[-1] if "-K" in question else ""))
        unit_id = str(item.get("yksikko") or (question.rsplit("-", 1)[0] if "-K" in question else ""))
        if not kind.startswith("K"):
            raise DecisionError(f"ratkaisut[{n}]: tyyppi (K1–K15) tai kysymys (esim. u004-K1) puuttuu")
        if not (unit_id or item.get("otsikko")):
            raise DecisionError(f"ratkaisut[{n}]: yksikkö, kysymys tai otsikko puuttuu")
        if "valinta" not in item:
            raise DecisionError(f"ratkaisut[{n}]: valinta puuttuu")
        decisions.append(
            Decision(
                question_id=question or f"{unit_id}-{kind}",
                unit_id=unit_id,
                option=str(item["valinta"]),
                scope=scope,
                by=item.get("ratkaisija"),
                at=str(item["aika"]) if item.get("aika") else None,
                basis=str(item.get("perustelu") or ""),
                kind=kind,
                heading=item.get("otsikko"),
                letter_code=item.get("tunnus"),
            )
        )
    return decisions


def merge_decisions(older: list[Decision], newer: list[Decision]) -> list[Decision]:
    """Newer answers replace older ones for the same unit and question type."""

    def key(d: Decision) -> tuple:
        return (d.kind, d.heading or "", d.letter_code or "", d.unit_id if not d.heading else "")

    merged = {key(d): d for d in older}
    for d in newer:
        merged[key(d)] = d
    return list(merged.values())


def _fold(text: str | None) -> str:
    return match.fold(text or "")


def _heading_base(kb, heading: str | None) -> str:
    if not heading:
        return ""
    base, _ = match.split_modifiers(kb, heading)
    return _fold(base)


def targets(decision: Decision, unit: SourceUnit) -> bool:
    """Is ``unit`` the unit the decision was made for?"""
    if decision.heading is not None:
        return _fold(decision.heading) == _fold(unit.heading) and (decision.letter_code or None) == (
            unit.letter_code or None
        )
    return decision.unit_id == unit.id


def similar(kb, decision: Decision, origin: SourceUnit | None, unit: SourceUnit) -> bool:
    """Scope ``projekti``: same letter code base (c-1 … c-4), same heading without modifiers or same text."""
    if origin is None:
        return False
    if origin.letter_code and unit.letter_code:
        if match.base_letter_code(origin.letter_code) == match.base_letter_code(unit.letter_code):
            return True
    if origin.heading and _heading_base(kb, origin.heading) == _heading_base(kb, unit.heading):
        return True
    return bool(origin.normalized_text) and origin.normalized_text == unit.normalized_text


@dataclass
class Applicable:
    decision: Decision
    unit: SourceUnit
    via: str  # "merkinta" or "projekti (u004)"


def applicable(kb, decisions: list[Decision], units: list[SourceUnit]) -> list[Applicable]:
    """Decisions per unit; a unit-specific answer wins over a project-wide one."""
    result: dict[tuple[str, str], Applicable] = {}
    for decision in decisions:
        origin = next((u for u in units if targets(decision, u)), None)
        if origin is not None:
            result[(origin.id, decision.kind)] = Applicable(decision, origin, "merkinta")
    for decision in decisions:
        if decision.scope != "projekti":
            continue
        origin = next((u for u in units if targets(decision, u)), None)
        for unit in units:
            if (unit.id, decision.kind) in result or unit is origin:
                continue
            if similar(kb, decision, origin, unit):
                result[(unit.id, decision.kind)] = Applicable(decision, unit, f"projekti ({origin.id})")
    return list(result.values())


def unmatched(decisions: list[Decision], units: list[SourceUnit]) -> list[Decision]:
    return [d for d in decisions if not any(targets(d, u) for u in units)]


def apply_input_hints(kb, decisions: list[Decision], units: list[SourceUnit]) -> dict[tuple[str, str], str]:
    """Answers that change the input of the rule-based step. Returns ``{(unit id, kind): option}``."""
    answers = {}
    for item in applicable(kb, decisions, units):
        answers[(item.unit.id, item.decision.kind)] = item.decision.option
        if item.decision.kind == "K8" and item.decision.option in ("alue", "viiva", "piste"):
            item.unit.geometry_hint = item.decision.option
    return answers


def apply_answers(kb, project: ConversionProject, decisions: list[Decision]) -> list[str]:
    """Settle the questions answered by the user. Returns warnings (e.g. unknown option)."""
    warnings = []
    for item in applicable(kb, decisions, project.units):
        proposal = item.unit.proposal
        if proposal is None:
            continue
        question = next((q for q in proposal.questions if q.kind == item.decision.kind), None)
        if question is None:
            if item.via == "merkinta":
                warnings.append(
                    f"{item.unit.id} {item.unit.heading}: ratkaisulle {item.decision.kind} ei ole kysymystä"
                )
            continue
        ids = {o.id for o in question.options}
        if ids and item.decision.option not in ids:
            warnings.append(
                f"{question.id}: valinta {item.decision.option!r} ei ole vaihtoehto ({', '.join(sorted(ids))})"
            )
            continue
        question.answer = item.decision.option
        question.resolved_by = "kayttaja" if item.via == "merkinta" else f"kayttaja, {item.via}"
        if item.decision.basis:
            question.basis = (
                question.basis + " " if question.basis else ""
            ) + f"Käyttäjä: {item.decision.basis}"
    return warnings


def record(project: ConversionProject, decisions: list[Decision]) -> None:
    """Store the decision log in the project, with unit identification for re-runs."""
    stored = []
    for d in decisions:
        unit = next((u for u in project.units if targets(d, u)), None)
        stored.append(
            Decision(
                question_id=f"{unit.id}-{d.kind}" if unit else d.question_id,
                unit_id=unit.id if unit else d.unit_id,
                option=d.option,
                scope=d.scope,
                by=d.by,
                at=d.at or datetime.now(UTC).replace(microsecond=0).isoformat(),
                basis=d.basis,
                kind=d.kind,
                heading=d.heading if d.heading is not None else (unit.heading if unit else None),
                letter_code=d.letter_code if d.heading is not None else (unit.letter_code if unit else None),
            )
        )
    project.decisions = stored


def resolved_for_model(question: InterpretationQuestion) -> dict[str, str]:
    return {
        "tyyppi": question.kind,
        "kysymys": question.question,
        "ratkaisu": question.answer or "",
        "ratkaisija": question.resolved_by or "",
    }


def template(project: ConversionProject) -> str:
    """A settings-file template (``ratkaisut``) of the open questions, for the user to fill in."""
    lines = [
        "# Avoimet tulkintakysymykset: kopioi tarvittavat ratkaisut asetustiedostoon (kma convert --asetukset)",
        "# tai aja muunnos uudelleen: kma convert <syöte> --projekti <tämä projekti> --asetukset <tiedosto>.",
        "# laajuus: merkinta (vain tämä yksikkö) tai projekti (kaikki samankaltaiset tässä projektissa).",
        "ratkaisut:",
    ]
    count = 0
    for unit in project.units:
        if not unit.proposal:
            continue
        for q in unit.proposal.open_questions():
            count += 1
            options = ", ".join(f"{o.id} = {o.description}" for o in q.options) or "vapaa valinta"
            lines += [
                "",
                f"## {q.question}",
                f"##   vaihtoehdot: {options}",
                f"##   suositus: {q.recommendation or '–'}",
                f"# - kysymys: {q.id}",
                f"#   otsikko: {_yaml_str(unit.heading)}",
                f"#   tunnus: {_yaml_str(unit.letter_code)}",
                f"#   tyyppi: {q.kind}",
                f"#   valinta: {q.recommendation or ''}",
                "#   laajuus: merkinta",
                "#   perustelu: ''",
            ]
    if not count:
        lines.append("# (ei avoimia kysymyksiä)")
    return "\n".join(lines) + "\n"


def _yaml_str(value: str | None) -> str:
    if value is None:
        return "null"
    return '"' + value.replace('"', '\\"') + '"'
