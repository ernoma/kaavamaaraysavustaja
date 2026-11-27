"""The user's changes to the structure of a group (ADR-0019, feedback P3-01).

A change adds an additional information (code list RY_Kaavamaarayksen_Lisatiedonlaji) to a
regulation of the group, or removes one, also one the assistant proposed. Changes are kept in
the project (``ConversionProject.edits``) apart from the decision log: a decision answers an
interpretation question, a change edits the structure whatever it came from (annex 4, a code
name, the vocabulary or a code chosen for K5). Like a decision, a change identifies its unit
by heading and letter code (:func:`decisions.targets`), so it is kept on re-runs and when an
earlier conversion is opened. A group with changes is the user's (``status = "muokattu"``)
and is not sent to the language model.

Which information types take a value, and from which code list, is data
(``rules_v1.yaml``, ``lisatietojen_arvot``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kaavamaaraysavustaja.core import decisions as decision_log
from kaavamaaraysavustaja.core import match
from kaavamaaraysavustaja.core.model import (
    AdditionalInfo,
    CodeRef,
    Rationale,
    Regulation,
    SourceUnit,
    StructureEdit,
    Value,
)
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase
from kaavamaaraysavustaja.knowledge.codelists import ADDITIONAL_INFO_TYPE, REGULATION_TYPE, Code

ADD = "lisaa_lisatieto"
REMOVE = "poista_lisatieto"
ACTIONS = (ADD, REMOVE)
VERBAL_PARENT = "sanallinenMaarays"

# Results of applying a change (Applied.result)
ADDED, PRESENT, REMOVED, ABSENT, NO_TARGET = "lisatty", "oli_jo", "poistettu", "ei_ollut", "ei_maaraysta"


class EditError(ValueError):
    pass


# --------------------------------------------------------------------------------------
# Information types and their values (data)


def value_spec(kb: KnowledgeBase, info: str) -> dict[str, Any] | None:
    """``{"arvo": "koodi", "koodisto": …}`` or ``{"arvo": "muu", …}``; None = no value."""
    spec = ((kb.rules or {}).get("lisatietojen_arvot") or {}).get(info)
    return spec if isinstance(spec, dict) else None


def value_codelist(kb: KnowledgeBase, info: str) -> str | None:
    """The code list of the value of ``info`` (e.g. RY_Kaavamaarayslaji), if it takes a code."""
    spec = value_spec(kb, info)
    return str(spec["koodisto"]) if spec and spec.get("arvo") == "koodi" and spec.get("koodisto") else None


def choosable_infos(kb: KnowledgeBase, plan_level: str) -> list[Code]:
    """Information types the user may add: valid, not header-level, in the plan level's
    hierarchy, and with no value or a code value from a code list in the knowledge base."""
    out = []
    known = set(kb.index.codelists())
    for code in kb.index.usable_codes(ADDITIONAL_INFO_TYPE, plan_level, kb.valid_on):
        spec = value_spec(kb, code.value)
        if spec is None or (spec.get("arvo") == "koodi" and spec.get("koodisto") in known):
            out.append(code)
    return out


def choosable_values(kb: KnowledgeBase, plan_level: str, info: str) -> list[Code]:
    """Codes the user may give as the value of ``info`` ([] = no value)."""
    from kaavamaaraysavustaja.core.convert import choosable_codes  # convert imports this module

    codelist = value_codelist(kb, info)
    if codelist is None or codelist not in kb.index.codelists():
        return []
    if codelist == REGULATION_TYPE:
        return choosable_codes(kb, plan_level)  # the same as for K5 (no verbal, no quantities)
    return kb.index.usable_codes(codelist)


def code_name(kb: KnowledgeBase, ref: CodeRef | None) -> str:
    if ref is None:
        return ""
    code = kb.index.by_uri(ref.uri)
    return (code.name.get("fi") if code else None) or ref.value


def ref(kb: KnowledgeBase, codelist: str, value: str) -> CodeRef:
    return CodeRef(kb.uri(codelist, value), kb.codelist_version(codelist))


# --------------------------------------------------------------------------------------
# Regulations a change can target


def is_verbal(kb: KnowledgeBase, regulation: Regulation) -> bool:
    if regulation.type.value == VERBAL_PARENT:
        return True
    code = kb.index.by_uri(regulation.type.uri)
    return bool(code and code.parent == VERBAL_PARENT)


def is_quantity(kb: KnowledgeBase, regulation: Regulation) -> bool:
    code = kb.index.by_uri(regulation.type.uri)
    return bool(code and code.in_extension(match.QUANTITY, kb.valid_on))


def main_regulation(kb: KnowledgeBase, regulations: list[Regulation]) -> Regulation | None:
    """The first regulation that is neither verbal nor a quantity."""
    return next((r for r in regulations if not is_verbal(kb, r) and not is_quantity(kb, r)), None)


def targets_of(kb: KnowledgeBase, regulations: list[Regulation]) -> list[tuple[str | None, Regulation]]:
    """(key, regulation): the main regulation (key None) and the other non-verbal regulations
    by their regulation type (e.g. a quantity)."""
    main = main_regulation(kb, regulations)
    out: list[tuple[str | None, Regulation]] = [(None, main)] if main is not None else []
    seen = {main.type.uri} if main is not None else set()
    for reg in regulations:
        if reg is main or is_verbal(kb, reg) or reg.type.uri in seen:
            continue
        seen.add(reg.type.uri)
        out.append((reg.type.value, reg))
    return out


def target_regulation(
    kb: KnowledgeBase, regulations: list[Regulation], edit: StructureEdit
) -> Regulation | None:
    if edit.regulation is None:
        return main_regulation(kb, regulations)
    return next((r for r in regulations if not is_verbal(kb, r) and r.type.uri == edit.regulation.uri), None)


def same_info(info: AdditionalInfo, edit: StructureEdit) -> bool:
    value = info.value.code.uri if info.value and info.value.code else None
    return info.type.uri == edit.info.uri and value == (edit.value.uri if edit.value else None)


# --------------------------------------------------------------------------------------
# The list of changes: identification, merging, recording


def key(edit: StructureEdit) -> tuple:
    """One change per unit, target regulation, information type and value."""
    return (
        edit.heading or "",
        edit.letter_code or "",
        edit.unit_id if not edit.heading else "",
        edit.regulation.uri if edit.regulation else "",
        edit.info.uri,
        edit.value.uri if edit.value else "",
    )


def merge(older: Iterable[StructureEdit], newer: Iterable[StructureEdit]) -> list[StructureEdit]:
    """Newer changes replace older ones with the same key (e.g. a removal an addition)."""
    merged = {key(e): e for e in older}
    for edit in newer:
        merged[key(edit)] = edit
    return list(merged.values())


def for_unit(edits: Iterable[StructureEdit], unit: SourceUnit) -> list[StructureEdit]:
    return [e for e in edits if decision_log.targets(e, unit)]  # same identification as decisions


def by_unit(edits: Iterable[StructureEdit], units: list[SourceUnit]) -> dict[str, list[StructureEdit]]:
    edits = list(edits)
    return {u.id: found for u in units if (found := for_unit(edits, u))}


def unmatched(edits: Iterable[StructureEdit], units: list[SourceUnit]) -> list[StructureEdit]:
    return [e for e in edits if not any(decision_log.targets(e, u) for u in units)]


def record(edits: Iterable[StructureEdit], units: list[SourceUnit]) -> list[StructureEdit]:
    """The changes as stored in the project: the unit id of this run, heading and letter code."""
    stored = []
    for e in edits:
        unit = next((u for u in units if decision_log.targets(e, u)), None)
        stored.append(
            StructureEdit(
                action=e.action,
                info=e.info,
                unit_id=unit.id if unit else e.unit_id,
                value=e.value,
                regulation=e.regulation,
                heading=e.heading if e.heading is not None else (unit.heading if unit else None),
                letter_code=e.letter_code if e.heading is not None else (unit.letter_code if unit else None),
                by=e.by,
                at=e.at or now(),
                basis=e.basis,
            )
        )
    return stored


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------------------
# Applying


@dataclass
class Applied:
    edit: StructureEdit
    result: str  # lisatty | oli_jo | poistettu | ei_ollut | ei_maaraysta
    regulation: Regulation | None


def apply(kb: KnowledgeBase, regulations: list[Regulation], edits: Iterable[StructureEdit]) -> list[Applied]:
    """Apply the changes to ``regulations`` (mutated). Repeating changes nothing."""
    applied = []
    for edit in edits:
        target = target_regulation(kb, regulations, edit)
        if target is None:
            applied.append(Applied(edit, NO_TARGET, None))
            continue
        present = [i for i in target.additional_infos if same_info(i, edit)]
        if edit.action == ADD:
            if present:
                applied.append(Applied(edit, PRESENT, target))
                continue
            value = None
            if edit.value is not None:
                value = Value("Code", code=CodeRef(edit.value.uri, kb.codelist_version(edit.value.codelist)))
            target.additional_infos.append(
                AdditionalInfo(CodeRef(edit.info.uri, kb.codelist_version(ADDITIONAL_INFO_TYPE)), value)
            )
            applied.append(Applied(edit, ADDED, target))
        else:
            if not present:
                applied.append(Applied(edit, ABSENT, target))
                continue
            target.additional_infos = [i for i in target.additional_infos if not same_info(i, edit)]
            applied.append(Applied(edit, REMOVED, target))
    return applied


def changed(applied: Iterable[Applied]) -> bool:
    return any(a.result in (ADDED, REMOVED) for a in applied)


def info_text(kb: KnowledgeBase, edit: StructureEdit) -> str:
    """``”Käyttötarkoituskohdistus” (kayttotarkoituskohdistus) arvolla ”Asuinalue” (asuinalue)``."""
    text = f"”{code_name(kb, edit.info)}” ({edit.info.value})"
    if edit.value is not None:
        text += f" arvolla ”{code_name(kb, edit.value)}” ({edit.value.value})"
    return text


def rationale(kb: KnowledgeBase, applied: Iterable[Applied]) -> list[Rationale]:
    """Why the structure is what the user made it (shown in the rationale and the report)."""
    out = []
    for a in applied:
        edit, info = a.edit, info_text(kb, a.edit)
        where = f"”{code_name(kb, a.regulation.type)}”" if a.regulation is not None else ""
        basis = f" Perustelu: {edit.basis.strip().rstrip('.')}." if edit.basis.strip() else ""
        reference = f"Koodin kuvaus: {edit.info.value}"
        if a.result == ADDED:
            out.append(
                Rationale(
                    f"Käyttäjä lisäsi lisätiedon {info} määräykseen {where}.{basis}",
                    "kayttaja",
                    "korkea",
                    reference=reference,
                )
            )
        elif a.result == PRESENT:
            out.append(
                Rationale(
                    f"Käyttäjän lisäämä lisätieto {info} on jo määräyksessä {where}, joten sitä ei lisätty toiseen kertaan.",
                    "kayttaja",
                    "korkea",
                    reference=reference,
                )
            )
        elif a.result == REMOVED:
            out.append(
                Rationale(
                    f"Käyttäjä poisti lisätiedon {info} määräyksestä {where}.{basis}",
                    "kayttaja",
                    "korkea",
                    reference=reference,
                )
            )
        elif a.result == ABSENT:
            out.append(
                Rationale(
                    f"Käyttäjä on poistanut lisätiedon {info}, eikä sitä ole määräyksessä {where}.",
                    "kayttaja",
                    "korkea",
                    reference=reference,
                )
            )
        else:
            target = (
                f"määräystä ”{code_name(kb, edit.regulation)}” ({edit.regulation.value})"
                if edit.regulation is not None
                else "kaavamääräystä (muuta kuin sanallista tai suureellista määräystä)"
            )
            verb = "lisäämää" if edit.action == ADD else "poistamaa"
            out.append(
                Rationale(
                    f"Käyttäjän {verb} lisätietoa {info} ei voitu käsitellä, koska ryhmässä ei ole {target}. "
                    "Valitse ensin kaavamääräyslaji tai poista muutos.",
                    "kayttaja",
                    "matala",
                    reference=reference,
                )
            )
    return out


def removes(edits: Iterable[StructureEdit], info: AdditionalInfo) -> bool:
    """Has the user removed this information from the group (from its main regulation)?"""
    return any(e.action == REMOVE and same_info(info, e) for e in edits)


# --------------------------------------------------------------------------------------
# Settings file (``muokkaukset``)

FIELDS = {"otsikko", "tunnus", "yksikko", "lisaa", "poista", "arvo", "maarays", "perustelu", "tekija", "aika"}


def parse_edits(kb: KnowledgeBase, items: list[dict[str, Any]] | None) -> list[StructureEdit]:
    """``muokkaukset`` of the settings file → changes (validated against the knowledge base).

    ``{otsikko, tunnus, lisaa | poista, arvo?, maarays?, perustelu?}``: ``maarays`` is the
    regulation type of the target (default: the main regulation).
    """
    out = []
    infos = {c.value for c in kb.index.usable_codes(ADDITIONAL_INFO_TYPE)}
    for n, item in enumerate(items or [], 1):
        if not isinstance(item, dict):
            raise EditError(f"muokkaukset[{n}] ei ole sanakirja")
        unknown = sorted(set(item) - FIELDS)
        if unknown:
            raise EditError(f"muokkaukset[{n}]: tuntemattomat kentät {', '.join(unknown)}")
        if ("lisaa" in item) == ("poista" in item):
            raise EditError(f"muokkaukset[{n}]: anna joko lisaa tai poista (lisätiedon laji)")
        action = ADD if "lisaa" in item else REMOVE
        info = str(item.get("lisaa") or item.get("poista") or "")
        if info not in infos:
            raise EditError(f"muokkaukset[{n}]: {info!r} ei ole voimassa oleva lisätiedon laji")
        if not (item.get("yksikko") or item.get("otsikko")):
            raise EditError(f"muokkaukset[{n}]: yksikkö tai otsikko puuttuu")
        value = None
        codelist = value_codelist(kb, info)
        if item.get("arvo") is not None:
            if codelist is None:
                raise EditError(f"muokkaukset[{n}]: lisätiedolle {info} ei anneta arvoa")
            if kb.index.get(codelist, str(item["arvo"])) is None:
                raise EditError(f"muokkaukset[{n}]: arvoa {item['arvo']!r} ei ole koodistossa {codelist}")
            value = ref(kb, codelist, str(item["arvo"]))
        elif action == ADD and codelist is not None:
            raise EditError(f"muokkaukset[{n}]: lisätiedolle {info} tarvitaan arvo koodistosta {codelist}")
        regulation = None
        if item.get("maarays"):
            if kb.index.get(REGULATION_TYPE, str(item["maarays"])) is None:
                raise EditError(f"muokkaukset[{n}]: kaavamääräyslajia {item['maarays']!r} ei ole koodistossa")
            regulation = ref(kb, REGULATION_TYPE, str(item["maarays"]))
        out.append(
            StructureEdit(
                action=action,
                info=ref(kb, ADDITIONAL_INFO_TYPE, info),
                unit_id=str(item.get("yksikko") or ""),
                value=value,
                regulation=regulation,
                heading=item.get("otsikko"),
                letter_code=item.get("tunnus"),
                by=item.get("tekija"),
                at=str(item["aika"]) if item.get("aika") else None,
                basis=str(item.get("perustelu") or ""),
            )
        )
    return out
