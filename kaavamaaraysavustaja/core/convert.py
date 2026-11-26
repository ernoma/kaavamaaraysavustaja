"""Rule-based conversion of parsed units into proposals (plan 6.5 steps 4, 6 and 7).

No language model is used in phase 1. Each proposal carries rationales, interpretation
questions (K1–K15) and rule results; questions settled by a policy choice (L-01–L-07) are
stored as resolved with ``resolved_by = "linjaus L-0n"`` (ADR-0010).
"""

from __future__ import annotations

import copy
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kaavamaaraysavustaja import __version__ as ASSISTANT_VERSION
from kaavamaaraysavustaja.core import match
from kaavamaaraysavustaja.core.ingest import is_upper_heading
from kaavamaaraysavustaja.core.model import (
    AdditionalInfo,
    CodeRef,
    ConversionProject,
    Decision,
    GroupProposal,
    InterpretationQuestion,
    Meta,
    PolicyChoice,
    Provenance,
    QuestionOption,
    Rationale,
    Recommendation,
    Regulation,
    SourceDocument,
    SourceUnit,
    Value,
)
from kaavamaaraysavustaja.core.policy import describe_choice
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase
from kaavamaaraysavustaja.knowledge.codelists import (
    ADDITIONAL_INFO_TYPE,
    REGULATION_TYPE,
    URI_PREFIX,
    VERBAL_REGULATION_TYPE,
)

KEY_NAMESPACE = uuid.UUID("7d0d6a2e-5a55-4a5e-9d6e-6b6d61000001")
VERBAL_TYPES = {"sanallinenMaarays", "suunnittelumaarays", "rakentamismaarays", "suojelumaarays"}
SMALL_WORDS = {
    "JA",
    "TAI",
    "ON",
    "SEN",
    "EI",
    "SAA",
    "YLI",
    "OLE",
    "NE",
    "SE",
    "KUN",
    "JOS",
    "VOI",
    "OSA",
    "UUSI",
}


@dataclass
class Context:
    kb: KnowledgeBase
    plan_level: str
    mode: str
    choices: dict[str, PolicyChoice]
    project_name: str
    keys: dict[str, int] = field(default_factory=dict)
    answers: dict[tuple[str, str], str] = field(default_factory=dict)  # (unit id, K-type) -> user option
    proposals: dict[str, GroupProposal] = field(default_factory=dict)  # unit id -> proposal (sub-areas)

    def answer(self, unit: SourceUnit, kind: str) -> str | None:
        return self.answers.get((unit.id, kind))

    def policy(self, policy_id: str) -> str:
        return self.choices[policy_id].option

    def describe(self, policy_id: str) -> str:
        return describe_choice(self.choices[policy_id])

    def ref(self, codelist: str, value: str) -> CodeRef:
        return CodeRef(self.kb.uri(codelist, value), self.kb.codelist_version(codelist))

    def key(self, *parts: str) -> str:
        return str(uuid.uuid5(KEY_NAMESPACE, "/".join((self.project_name, *parts))))


# --------------------------------------------------------------------------------------
# Helpers


def sentence_case(heading: str) -> str:
    """``TÄYDENTYVÄ KESKUSTA`` → ``Täydentyvä keskusta``; short acronyms stay (``VAK``)."""
    if not heading:
        return heading
    if not is_upper_heading(heading):
        return heading
    out = []
    for token in heading.split(" "):
        letters = re.sub(r"[^A-ZÄÖÅa-zäöå]", "", token)
        if 1 < len(letters) <= 3 and letters.isupper() and letters not in SMALL_WORDS:
            out.append(token)
        else:
            out.append(token.lower())
    text = " ".join(out)
    return text[:1].upper() + text[1:]


def code_from_annex(value: Any, default_codelist: str) -> tuple[str, str] | None:
    """Annex 4 code cell: ``"keskustatoimintojenAlue"`` or ``{koodisto, koodi}``."""
    if isinstance(value, str):
        return default_codelist, value
    if isinstance(value, dict) and "koodi" in value:
        return value.get("koodisto", default_codelist), str(value["koodi"])
    return None


def question(
    ctx: Context,
    unit: SourceUnit,
    kind: str,
    text: str,
    options: list[tuple[str, str, str]],
    recommendation: str | None,
    basis: str,
    resolved_by: str | None = None,
    answer: str | None = None,
) -> InterpretationQuestion:
    return InterpretationQuestion(
        id=f"{unit.id}-{kind}",
        kind=kind,
        question=text,
        options=[QuestionOption(i, d, c) for i, d, c in options],
        recommendation=recommendation,
        basis=basis,
        answer=answer,
        resolved_by=resolved_by,
    )


def policy_question(
    ctx: Context, unit: SourceUnit, kind: str, policy_id: str, text: str, basis: str
) -> InterpretationQuestion:
    choice = ctx.choices[policy_id]
    return InterpretationQuestion(
        id=f"{unit.id}-{kind}",
        kind=kind,
        question=text,
        options=[],
        recommendation=choice.option,
        basis=basis,
        answer=choice.option,
        resolved_by=f"linjaus {policy_id}",
    )


# --------------------------------------------------------------------------------------
# Structure (non-verbal regulations)


@dataclass
class Structure:
    regulations: list[Regulation] = field(default_factory=list)
    rationale: list[Rationale] = field(default_factory=list)
    geometry: list[str] = field(default_factory=list)
    title: str | None = None
    letter_code: str | None = None  # Katja / annex letter code, if any
    confidence: str = "matala"
    method: str = ""
    annex_row: dict[str, Any] | None = None
    exact_annex: bool = False


def regulation_from_codes(
    ctx: Context,
    unit: SourceUnit,
    index: int,
    type_code: str,
    infos: list[tuple[str, str, tuple[str, str] | None]],
) -> Regulation:
    """``infos`` = (codelist, info code, optional (codelist, value code))."""
    additional = []
    for codelist, info, value in infos:
        info_value = None
        if value:
            value_codelist, value_code = value
            info_value = Value("Code", code=ctx.ref(value_codelist, value_code))
        additional.append(AdditionalInfo(ctx.ref(codelist, info), info_value))
    return Regulation(
        key=ctx.key(unit.id, f"r{index}"),
        type=ctx.ref(REGULATION_TYPE, type_code),
        additional_infos=additional,
    )


def structure_from_annex(ctx: Context, unit: SourceUnit, found: list[match.AnnexMatch]) -> Structure:
    chosen = match.choose_geometry_row(found, unit.geometry_hint)
    row = chosen.row
    infos: list[tuple[str, str, tuple[str, str] | None]] = []
    notes = []
    for item in row.get("lisatiedot", []):
        laji = code_from_annex(item.get("laji"), ADDITIONAL_INFO_TYPE)
        if not laji or laji[0] != ADDITIONAL_INFO_TYPE:
            notes.append(f"liitteen 4 lisätieto {item.get('laji')!r} ohitettu")
            continue
        value = code_from_annex(item["arvo"], REGULATION_TYPE) if "arvo" in item else None
        infos.append((ADDITIONAL_INFO_TYPE, laji[1], value))
    for modifier in chosen.modifiers:
        infos.append((ADDITIONAL_INFO_TYPE, modifier.info_code, None))
    regulations = []
    for n, type_value in enumerate(row.get("kaavamaarayslajit", [])):
        type_code = code_from_annex(type_value, REGULATION_TYPE)
        if not type_code or type_code[0] != REGULATION_TYPE:
            notes.append(f"liitteen 4 kaavamääräyslaji {type_value!r} ohitettu")
            continue
        if type_code[1] in VERBAL_TYPES:
            continue  # the verbal regulation comes from the source text
        regulations.append(regulation_from_codes(ctx, unit, n, type_code[1], infos))
    exact = chosen.how == "otsikko"
    how = {
        "otsikko": "Merkinnän nimi vastaa Katja-asetuksen liitteen 4 vakiomääräystä",
        "otsikko_maareet": "Merkinnän nimi ilman määreitä vastaa liitteen 4 vakiomääräystä",
        "tunnus": "Kirjaintunnus vastaa liitteen 4 vakiomääräystä",
    }[chosen.how]
    codes = " + ".join([*(r.type.value for r in regulations), *(i[1] for i in infos)])
    confidence = "korkea" if exact else "keskitaso"
    rationale = [
        Rationale(
            f"{how} {row.get('kirjaintunnus') or ''} {row['otsikko']}; rakenne {codes}.".replace("  ", " "),
            "vakioluettelo",
            confidence,
            reference=chosen.reference,
        )
    ]
    if chosen.modifiers:
        rationale.append(
            Rationale(
                "Otsikon määreet lisätietoina: "
                + ", ".join(f"{m.word.upper()} → {m.info_code}" for m in chosen.modifiers),
                "sanasto",
                "keskitaso",
                quote=unit.heading,
                reference="Sanasto v1 / maareet",
            )
        )
    for correction_id in row.get("korjaukset", []):
        correction = ctx.kb.corrections.get(correction_id, {})
        rationale.append(
            Rationale(
                f"Liitteen 4 rivi on korjattu ({correction_id})"
                + (": korjaus on vahvistamaton." if correction.get("vahvistettava") else "."),
                "vakioluettelo",
                "keskitaso" if correction.get("vahvistettava") else confidence,
                reference="knowledge/katja/annex4_corrections.yaml",
            )
        )
        if correction.get("vahvistettava"):
            confidence = "keskitaso"
    for note in row.get("avoimet_havainnot", []):
        rationale.append(
            Rationale(
                f"Liitteen 4 rivillä avoin havainto: {note}",
                "vakioluettelo",
                "matala",
                reference="docs/laaturaportti_liite3.md",
            )
        )
        confidence = "matala"
    for note in notes:
        rationale.append(Rationale(note, "vakioluettelo", "matala"))
    if len(found) > 1:
        alternatives = ", ".join(
            f"{m.row.get('geometria')} (rivi {m.row['rivi']})" for m in found if m is not chosen
        )
        rationale.append(
            Rationale(
                f"Valittu geometria {row.get('geometria')}; muut liitteen rivit: {alternatives}.",
                "vakioluettelo",
                "keskitaso",
            )
        )
    return Structure(
        regulations=regulations,
        rationale=rationale,
        geometry=[row["geometria"]] if row.get("geometria") else [],
        title=row["otsikko"] if exact else None,
        letter_code=row.get("kirjaintunnus"),
        confidence=confidence,
        method="vakioluettelo",
        annex_row=row,
        exact_annex=exact,
    )


def structure_from_code(ctx: Context, unit: SourceUnit, found: match.CodeMatch) -> Structure:
    code = found.code
    _, modifiers = match.split_modifiers(ctx.kb, unit.heading or "")
    infos: list[tuple[str, str, tuple[str, str] | None]] = []
    geometry = [unit.geometry_hint] if unit.geometry_hint else []
    is_reservation = code.in_extension(match.AREA_RESERVATION, ctx.kb.valid_on)
    rows = [
        r
        for r in ctx.kb.annex.get(ctx.plan_level, [])
        if [
            code_from_annex(v, REGULATION_TYPE)
            for v in r.get("kaavamaarayslajit", [])
            if (code_from_annex(v, REGULATION_TYPE) or ("", ""))[1] not in VERBAL_TYPES
        ]
        == [(REGULATION_TYPE, code.value)]
    ]
    annex_note = None
    if rows and not is_reservation:
        # Structure of the same code in annex 4 (e.g. kehittamisalue + osaAlue, area).
        row = match.choose_geometry_row([match.AnnexMatch(r, "koodi") for r in rows], unit.geometry_hint).row
        for item in row.get("lisatiedot", []):
            laji = code_from_annex(item.get("laji"), ADDITIONAL_INFO_TYPE)
            if laji and laji[0] == ADDITIONAL_INFO_TYPE:
                value = code_from_annex(item["arvo"], REGULATION_TYPE) if "arvo" in item else None
                infos.append((ADDITIONAL_INFO_TYPE, laji[1], value))
        geometry = geometry or ([row["geometria"]] if row.get("geometria") else [])
        annex_note = f"Rakenne kuten liitteen 4 rivillä {row['rivi']} ({row.get('kirjaintunnus') or '–'} {row['otsikko']})."
    elif is_reservation and (not geometry or geometry == ["alue"]):
        infos.append((ADDITIONAL_INFO_TYPE, "paakayttotarkoitus", None))
        geometry = ["alue"]
    infos += [(ADDITIONAL_INFO_TYPE, m.info_code, None) for m in modifiers]
    regulation = regulation_from_codes(ctx, unit, 0, code.value, infos)
    rationale = [
        Rationale(
            f'Merkinnän nimi vastaa kaavamääräyslajin {code.value} nimeä "{code.name.get("fi")}"'
            + (" (osittain)" if found.how == "nimi_osittain" else "")
            + (
                ". Koodi kuuluu Aluevaraus-hierarkiaan, joten lisätieto on pääkäyttötarkoitus."
                if is_reservation
                else "."
            ),
            "koodisto",
            "keskitaso",
            quote=unit.heading,
            reference=f"Koodin kuvaus: {code.value}",
        )
    ]
    if annex_note:
        rationale.append(Rationale(annex_note, "vakioluettelo", "keskitaso"))
    if modifiers:
        rationale.append(
            Rationale(
                "Otsikon määreet lisätietoina: "
                + ", ".join(f"{m.word.upper()} → {m.info_code}" for m in modifiers),
                "sanasto",
                "keskitaso",
                quote=unit.heading,
            )
        )
    return Structure([regulation], rationale, geometry, None, None, "keskitaso", "koodisto")


def structure_from_mixed(ctx: Context, unit: SourceUnit, codes: list) -> Structure:
    """K2 recommendation (opas 3.3.2): a combination of main uses, each with paakayttotarkoitus."""
    regulations = [
        regulation_from_codes(ctx, unit, n, code.value, [(ADDITIONAL_INFO_TYPE, "paakayttotarkoitus", None)])
        for n, code in enumerate(codes)
    ]
    rationale = [
        Rationale(
            "Sekoittunut käyttötarkoitus määräysyhdistelmänä (opas 3.3.2): "
            + " + ".join(f'{c.value} ("{c.name.get("fi")}")' for c in codes)
            + ", kukin pääkäyttötarkoituksena.",
            "saanto",
            "matala",
            quote=unit.heading,
            reference="Opas 3.3.2; suunnitelma 6.10 K2",
        )
    ]
    return Structure(regulations, rationale, ["alue"], None, None, "matala", "saanto")


def letter_code_by_signature(ctx: Context, regulations: list[Regulation]) -> dict[str, Any] | None:
    """Annex 4 row with the same code combination (for a letter code missing from the source)."""
    from kaavamaaraysavustaja.core.rules.checks import signature_of_row

    items = set()
    for reg in regulations:
        if reg.type.value in VERBAL_TYPES:
            continue
        items.add(("laji", reg.type.value))
        for info in reg.additional_infos:
            items.add(
                (
                    "lisatieto",
                    info.type.value,
                    info.value.code.value if info.value and info.value.code else None,
                )
            )
    if not items:
        return None
    for row in ctx.kb.annex.get(ctx.plan_level, []):
        if row.get("kirjaintunnus") and signature_of_row(row) == frozenset(items):
            return row
    return None


def structure_from_keyword(ctx: Context, unit: SourceUnit, entry: dict[str, Any]) -> Structure:
    infos = [(ADDITIONAL_INFO_TYPE, code, None) for code in entry.get("lisatiedot", [])]
    regulation = regulation_from_codes(ctx, unit, 0, entry["kaavamaarayslaji"], infos)
    rationale = [
        Rationale(
            f'Liitteestä 4 tai koodien nimistä ei löytynyt vastinetta. Otsikon sana "{entry["alku"]}" '
            f"ohjaa lähimpään koodiin {entry['kaavamaarayslaji']}.",
            "sanasto",
            "matala",
            quote=unit.heading,
            reference="Sanasto v1 / otsikon_avainsanat",
        )
    ]
    geometry = (
        [unit.geometry_hint]
        if unit.geometry_hint
        else ([entry["geometria"]] if entry.get("geometria") else [])
    )
    return Structure([regulation], rationale, geometry, None, None, "matala", "sanasto")


def lowercase_index_structure(
    ctx: Context, unit: SourceUnit
) -> tuple[Structure, InterpretationQuestion] | None:
    """K1: ``c-1`` next to an annex ``C`` → sub-area (development zone targeting C) or reservation."""
    code = unit.letter_code or ""
    base = match.base_letter_code(code)
    if not base or not base.islower():
        return None
    rows = [r for r in ctx.kb.annex.get(ctx.plan_level, []) if r.get("kirjaintunnus") == base.upper()]
    rows = [r for r in rows if any(i.get("laji") == "paakayttotarkoitus" for i in r.get("lisatiedot", []))]
    if not rows:
        return None
    row = rows[0]
    target = code_from_annex(row["kaavamaarayslajit"][0], REGULATION_TYPE)
    if not target:
        return None
    k1_options = [
        (
            "osa_alue",
            f"Osa-alue: kehittämisvyöhyke, joka kohdistuu käyttötarkoitukseen {target[1]}",
            "Kartalla osa-alueen rajaus aluevarauksen päällä.",
        ),
        (
            "aluevaraus",
            f"Aluevaraus: {target[1]} + pääkäyttötarkoitus, tunnus {base.upper()}{code[len(base) :]}",
            "Kohde on kaavan pohja-aluevaraus; ei sovi, jos samalla alueella on erillinen aluevaraus.",
        ),
    ]
    k1_basis = "Pienaakkosin kirjoitettu tunnus on liitteessä 4 osa-alueille tyypillinen. Varmistus vektoriaineistosta (vaihe 4)."
    if ctx.answer(unit, "K1") == "aluevaraus":
        regulation = regulation_from_codes(
            ctx, unit, 0, target[1], [(ADDITIONAL_INFO_TYPE, "paakayttotarkoitus", None)]
        )
        rationale = [
            Rationale(
                f"Käyttäjän ratkaisu K1: aluevaraus {target[1]} + pääkäyttötarkoitus "
                f"(liitteen 4 rivi {row['rivi']} {row['kirjaintunnus']} {row['otsikko']}).",
                "kayttaja",
                "korkea",
                reference=f"Katja liite 4 / rivi {row['rivi']}",
            )
        ]
        q = question(
            ctx,
            unit,
            "K1",
            f"Aluevaraus vai osa-alue? – {code} {unit.heading}",
            k1_options,
            "osa_alue",
            k1_basis,
        )
        return Structure([regulation], rationale, ["alue"], None, None, "keskitaso", "kayttaja"), q
    regulation = regulation_from_codes(
        ctx,
        unit,
        0,
        "kehittamisvyohyke",
        [
            (ADDITIONAL_INFO_TYPE, "osaAlue", None),
            (ADDITIONAL_INFO_TYPE, "kayttotarkoituskohdistus", (REGULATION_TYPE, target[1])),
        ],
    )
    rationale = [
        Rationale(
            f"Pienaakkosin kirjoitettu indeksoitu tunnus {code} on liitteessä 4 osa-alueille tyypillinen; "
            f"liitteen 4 aluevaraus {row['kirjaintunnus']} {row['otsikko']} on oma merkintänsä. Ehdotus: "
            f"kehittämisvyöhyke (osa-alue), joka kohdistuu käyttötarkoitukseen {target[1]}.",
            "saanto",
            "matala",
            quote=f"{code} {unit.heading}",
            reference=f"Katja liite 4 / rivi {row['rivi']}; suunnitelma 6.10 K1",
        )
    ]
    q = question(
        ctx, unit, "K1", f"Aluevaraus vai osa-alue? – {code} {unit.heading}", k1_options, "osa_alue", k1_basis
    )
    return Structure([regulation], rationale, ["alue"], None, None, "matala", "saanto"), q


# --------------------------------------------------------------------------------------
# Verbal regulations


def verbal_regulations(
    ctx: Context, unit: SourceUnit, start_index: int, development_zone: bool = False
) -> tuple[list[Regulation], list[Rationale]]:
    text = unit.normalized_text
    if not text:
        return [], []
    if ctx.policy("L-03") == "kappaleittain":
        paragraphs = text.split("\n\n")
    else:
        paragraphs = [text]
    regulations: list[Regulation] = []
    rationale: list[Rationale] = []
    offset = 0
    for n, paragraph in enumerate(paragraphs):
        start = text.index(paragraph, offset)
        offset = start + len(paragraph)
        type_code, keyword = match.verbal_regulation_type(ctx.kb, paragraph, ctx.policy("L-04"))
        if ctx.policy("L-04") == "kehittamisvyohyke_suunnittelumaarays" and development_zone:
            type_code, keyword = "suunnittelumaarays", None
        hits = match.find_verbal_types(ctx.kb, paragraph)
        reg = Regulation(
            key=ctx.key(unit.id, f"s{n}"),
            type=ctx.ref(REGULATION_TYPE, type_code),
            value=Value("LocalizedText", text={"fin": paragraph}),
            verbal_types=[ctx.ref(VERBAL_REGULATION_TYPE, h.code) for h in hits],
            text_span=(start, start + len(paragraph)),
        )
        reg.rationale.append(
            Rationale(
                "Sanallinen teksti siirtyy merkki merkiltä lähteen mukaisena (VOOKA-tila)."
                if ctx.mode == "vooka"
                else "Sanallinen teksti lähteen mukaisena.",
                "saanto",
                "korkea",
                reference="Periaate P2; ADR-0007",
            )
        )
        reg.rationale.append(
            Rationale(
                f"Kaavamääräyslaji {type_code}"
                + (f' (sana "{keyword}")' if keyword else "")
                + f": {ctx.describe('L-04')}.",
                "linjaus",
                "korkea",
                reference="knowledge/org/tampere/linjaukset.yaml",
            )
        )
        for hit in hits:
            reg.rationale.append(
                Rationale(
                    f'Sanallisen määräyksen laji {hit.code}: sana "{hit.keyword}" ({hit.count} osumaa).',
                    "sanasto",
                    "keskitaso",
                    quote=hit.quote,
                    reference="Sanasto v1 / sanallisen_lajit",
                )
            )
        regulations.append(reg)
    if len(paragraphs) > 1:
        rationale.append(
            Rationale(
                f"Teksti jaettu {len(paragraphs)} kappaleeseen: {ctx.describe('L-03')}.", "linjaus", "korkea"
            )
        )
    return regulations, rationale


# --------------------------------------------------------------------------------------
# Units


def letter_code_for(
    ctx: Context,
    unit: SourceUnit,
    structure: Structure,
    questions: list[InterpretationQuestion],
    rationale: list[Rationale],
) -> str | None:
    source = unit.letter_code
    katja = structure.letter_code if structure.annex_row else None
    if not katja and not structure.annex_row and structure.method in ("koodisto", "saanto"):
        row = letter_code_by_signature(ctx, structure.regulations)
        if row:
            katja = row["kirjaintunnus"]
            rationale.append(
                Rationale(
                    f"Koodiyhdistelmä vastaa liitteen 4 riviä {row['rivi']} ({row['kirjaintunnus']} {row['otsikko']}).",
                    "vakioluettelo",
                    "keskitaso",
                    reference=f"Katja liite 4 / rivi {row['rivi']}",
                )
            )
            structure.annex_row = row
    if ctx.policy("L-06") == "katja" and katja:
        chosen = katja
    else:
        chosen = source or katja
    if katja and source != katja:
        questions.append(
            policy_question(
                ctx,
                unit,
                "K14",
                "L-06",
                f"Kirjaintunnus: lähteessä {source or 'ei tunnusta'}, liitteessä 4 {katja}.",
                f"Valittu {chosen}: {ctx.describe('L-06')}.",
            )
        )
        rationale.append(
            Rationale(
                f"Kirjaintunnus {chosen}"
                + (
                    " otettu liitteestä 4, koska lähteessä tunnus on vain symbolissa; vahvistetaan vektoriaineistosta."
                    if not source
                    else f" ({ctx.describe('L-06')})."
                ),
                "linjaus",
                "keskitaso" if not source else "korkea",
                reference=ctx.describe("L-06"),
            )
        )
    return chosen


def propose_marking(ctx: Context, unit: SourceUnit) -> GroupProposal:
    heading = unit.heading or ""
    questions: list[InterpretationQuestion] = []
    rationale: list[Rationale] = []
    proposal = GroupProposal(key=ctx.key(unit.id, "group"), kind="kaavakohde")
    category = " / ".join(x for x in [unit.map, *(s.capitalize() for s in unit.section_path)] if x) or None
    proposal.category = category

    if (
        match.is_informative(ctx.kb, heading)
        and not unit.normalized_text
        and ctx.answer(unit, "K6") != "maarays"
    ):
        proposal.kind = "ei_maarays"
        proposal.title = {"fin": sentence_case(heading)}
        questions.append(
            question(
                ctx,
                unit,
                "K6",
                f"Informatiivinen merkintä vai määräys? – {heading}",
                [
                    ("ei_maarays", "Ei kaavamääräys (kaavan rajaus tai lähtötieto)", "Ei viedä kirjastoon."),
                    ("maarays", "Kaavamääräys", "Määräysryhmä rakennetaan käsin."),
                ],
                "ei_maarays",
                "Otsikko kuvaa rajausta, eikä merkinnällä ole määräystekstiä (L-08: vahvistetaan merkinnöittäin).",
            )
        )
        proposal.questions = questions
        return proposal

    structure: Structure | None = None
    approved = match.find_approved(ctx.kb, heading, unit.letter_code)
    if approved:
        structure = structure_from_approved(ctx, unit, approved)
    if structure is None:
        found = match.find_annex(ctx.kb, ctx.plan_level, heading, unit.letter_code)
        if found:
            structure = structure_from_annex(ctx, unit, found)
    if structure is None:
        k1 = lowercase_index_structure(ctx, unit)
        if k1:
            structure, q = k1
            questions.append(q)
    if structure is None and "sekoittunut" in fold(heading):
        mixed = match.find_mixed_use(ctx.kb, ctx.plan_level, heading)
        if mixed:
            structure = structure_from_mixed(ctx, unit, mixed)
    nearest = False
    if structure is None:
        codes = match.find_codes_by_name(ctx.kb, ctx.plan_level, heading)
        if codes:
            structure = structure_from_code(ctx, unit, codes[0])
            nearest = codes[0].how == "nimi_sisaltyy"
    if unit.parent_id and (structure is None or nearest):
        inherited = structure_from_parent(ctx, unit)
        if inherited:
            structure, nearest = inherited, False
    if structure is None or nearest:
        entry = None if nearest else match.find_keyword(ctx.kb, heading)
        if nearest:
            structure.confidence = "matala"
        elif entry:
            structure = structure_from_keyword(ctx, unit, entry)
        else:
            structure = Structure(
                rationale=[
                    Rationale(
                        "Liitteestä 4, koodien nimistä tai sanastosta ei löytynyt vastinetta.",
                        "saanto",
                        "matala",
                    )
                ]
            )
        questions.append(
            question(
                ctx,
                unit,
                "K5",
                f"Ei sopivaa Katja-koodia – {heading}",
                [
                    (
                        "lahin_koodi",
                        "Lähin perusteltu koodi ja sanallinen määräys",
                        "Tapaus kirjataan Katja-puutelistaan.",
                    ),
                    (
                        "kehittamisvyohyke",
                        "Kehittämisvyöhyke ja käyttötarkoituskohdistus",
                        "Osa-alue aluevarauksen päällä.",
                    ),
                ],
                "lahin_koodi",
                "Suunnitelma 6.10 K5: lähin perusteltu koodi; tapaus Katja-puutelistaan.",
            )
        )

    proposal.regulations = list(structure.regulations)
    rationale += structure.rationale
    proposal.geometry_types = structure.geometry or ([unit.geometry_hint] if unit.geometry_hint else [])
    proposal.title = {"fin": structure.title or sentence_case(heading)}
    if structure.title and fold(structure.title) != fold(heading):
        rationale.append(
            Rationale(f'Otsikoksi liitteen 4 otsikko "{structure.title}".', "vakioluettelo", "korkea")
        )
    proposal.letter_code = letter_code_for(ctx, unit, structure, questions, rationale)
    apply_title_policy(ctx, unit, proposal, rationale)

    _, modifiers = match.split_modifiers(ctx.kb, heading)
    if len(modifiers) > 1 or any(m.needs_confirmation for m in modifiers):
        questions.append(
            question(
                ctx,
                unit,
                "K7",
                f"Otsikon määreet lisätiedoiksi – {heading}",
                [
                    ("sanasto", ", ".join(m.info_code for m in modifiers), "Lisätiedot kuten ehdotettu."),
                    ("osittain", "Vain osa määreistä lisätiedoiksi", "Muokataan käsin."),
                ],
                "sanasto",
                "Yhdistelmät ja vahvistettavat määreet kysytään (suunnitelma 6.10 K7).",
            )
        )
    if "sekoittunut" in fold(heading):
        questions.append(
            question(
                ctx,
                unit,
                "K2",
                f"Sekoittunut käyttötarkoitus – {heading}",
                [
                    (
                        "yhdistelma",
                        "Määräysyhdistelmä: useita pääkäyttötarkoituksia",
                        "Opas 3.3.2; otsikoksi ei liitteen 4 otsikkoa.",
                    ),
                    (
                        "yksi_ja_kohdistus",
                        "Yksi pääkäyttötarkoitus ja käyttötarkoituskohdistus",
                        "Yksi aluevaraus.",
                    ),
                ],
                "yhdistelma",
                "Opas 3.3.2 (suunnitelma 6.10 K2).",
            )
        )
    if not proposal.geometry_types:
        questions.append(
            question(
                ctx,
                unit,
                "K8",
                f"Geometriatyyppi – {heading}",
                [("alue", "Alue", ""), ("viiva", "Viiva", ""), ("piste", "Piste", "")],
                None,
                "Liitteestä 4 ei saatu geometriaa; ratkaistaan vektoriaineistosta tai käyttäjältä (@geometria).",
            )
        )

    finish(
        ctx, unit, proposal, structure.confidence, questions, rationale, start_index=len(proposal.regulations)
    )
    return proposal


def structure_from_parent(ctx: Context, unit: SourceUnit) -> Structure | None:
    """K9: a numbered sub-area (``1. SÄRKÄNNIEMEN … ALUE``) has the structure of its parent marking."""
    parent = ctx.proposals.get(unit.parent_id or "")
    if parent is None:
        return None
    regulations = []
    for n, reg in enumerate(r for r in parent.regulations if r.type.value not in VERBAL_TYPES):
        infos = [
            (
                ADDITIONAL_INFO_TYPE,
                info.type.value,
                (REGULATION_TYPE, info.value.code.value) if info.value and info.value.code else None,
            )
            for info in reg.additional_infos
        ]
        regulations.append(regulation_from_codes(ctx, unit, n, reg.type.value, infos))
    if not regulations:
        return None
    rationale = [
        Rationale(
            f"Alakohta {unit.sub_index} merkinnästä {parent.title.get('fin')}: rakenne kuten yläkohdalla "
            "(suunnitelma 6.10 K9: ryhmä alakohtaa kohden).",
            "saanto",
            "keskitaso",
            reference=f"yksikkö {unit.parent_id}",
        )
    ]
    return Structure(regulations, rationale, list(parent.geometry_types), None, None, "keskitaso", "saanto")


def add_sub_area_questions(ctx: Context, units: list[SourceUnit]) -> None:
    """K9 on the parent of numbered sub-areas: one group per sub-area or one group."""
    children: dict[str, list[SourceUnit]] = {}
    for unit in units:
        if unit.parent_id:
            children.setdefault(unit.parent_id, []).append(unit)
    for parent_id, subs in children.items():
        parent = next((u for u in units if u.id == parent_id), None)
        if (
            parent is None
            or parent.proposal is None
            or any(q.kind == "K9" for q in parent.proposal.questions)
        ):
            continue
        parent.proposal.questions.append(
            question(
                ctx,
                parent,
                "K9",
                f"Alakohtaiset määräykset ({len(subs)} numeroitua osa-aluetta) – {parent.heading}",
                [
                    (
                        "ryhma_alakohtaa_kohden",
                        "Ryhmä alakohtaa kohden (nykyinen jako)",
                        "Kohdistuvat eri alueisiin; yläkohdan teksti koskee kaikkia.",
                    ),
                    ("yksi_ryhma", "Yksi ryhmä", "Alakohtien tekstit yhdistetään yläkohdan ryhmään."),
                ],
                "ryhma_alakohtaa_kohden",
                "Alakohdat: " + "; ".join(f"{u.sub_index}. {u.heading}" for u in subs),
            )
        )


def apply_title_policy(
    ctx: Context, unit: SourceUnit, proposal: GroupProposal, rationale: list[Rationale]
) -> None:
    """L-15: the source heading (Katja 2 §) or the annex 4 title of the same code combination (opas 3.1.1)."""
    if "L-15" not in ctx.choices or not unit.heading:
        return
    rows = annex_rows_by_signature(ctx, proposal.regulations)
    if not rows or fold(proposal.title.get("fin", "")) in {fold(r["otsikko"]) for r in rows}:
        return
    row = next((r for r in rows if r.get("geometria") in proposal.geometry_types), rows[0])
    if not unit.normalized_text:
        # No verbal regulation: the information content is not broader (Katja 2 §), so
        # opas 3.1.1 applies whatever L-15 says.
        proposal.title = {"fin": row["otsikko"]}
        rationale.append(
            Rationale(
                f'Otsikoksi liitteen 4 otsikko "{row["otsikko"]}" (rivi {row["rivi"]}): koodiyhdistelmä vastaa '
                f"liitteen riviä eikä ryhmässä ole sanallista määräystä (opas 3.1.1); lähteen otsikko {unit.heading}.",
                "vakioluettelo",
                "korkea",
                reference=f"Opas 3.1.1; Katja liite 4 / rivi {row['rivi']}",
            )
        )
        return
    if ctx.policy("L-15") == "katja":
        proposal.title = {"fin": row["otsikko"]}
        rationale.append(
            Rationale(
                f'Otsikoksi liitteen 4 otsikko "{row["otsikko"]}" (rivi {row["rivi"]}), koska koodiyhdistelmä vastaa '
                f"liitteen riviä; lähteen otsikko {unit.heading}. {ctx.describe('L-15')}.",
                "linjaus",
                "korkea",
                reference=f"Opas 3.1.1; Katja liite 4 / rivi {row['rivi']}",
            )
        )
    else:
        rationale.append(
            Rationale(
                f'Koodiyhdistelmä vastaa liitteen 4 otsikkoa "{row["otsikko"]}" (rivi {row["rivi"]}); lähteen otsikko '
                f"säilyy, koska tietosisältö on laajempi (Katja 2 §). {ctx.describe('L-15')}.",
                "linjaus",
                "korkea",
                reference="Katja 2 §; opas 3.1.1",
            )
        )


def annex_row_by_signature(ctx: Context, regulations: list[Regulation]) -> dict[str, Any] | None:
    from kaavamaaraysavustaja.core.rules.checks import signature_of_row

    items = set()
    for reg in regulations:
        if reg.type.value in VERBAL_TYPES:
            continue
        items.add(("laji", reg.type.value))
        for info in reg.additional_infos:
            items.add(
                (
                    "lisatieto",
                    info.type.value,
                    info.value.code.value if info.value and info.value.code else None,
                )
            )
    if not items:
        return None
    for row in ctx.kb.annex.get(ctx.plan_level, []):
        if row.get("otsikko") and signature_of_row(row) == frozenset(items):
            return row
    return None


def annex_rows_by_signature(ctx: Context, regulations: list[Regulation]) -> list[dict[str, Any]]:
    """All annex 4 rows with the same code combination (e.g. the area and the point row)."""
    from kaavamaaraysavustaja.core.rules.checks import signature_of_row

    first = annex_row_by_signature(ctx, regulations)
    if first is None:
        return []
    signature = signature_of_row(first)
    return [
        r
        for r in ctx.kb.annex.get(ctx.plan_level, [])
        if r.get("otsikko") and signature_of_row(r) == signature
    ]


def structure_from_approved(ctx: Context, unit: SourceUnit, entry: dict[str, Any]) -> Structure:
    group = entry["ryhma"]
    regulations = []
    for n, item in enumerate(group.get("maaraykset", [])):
        infos = []
        for info in item.get("lisatiedot", []):
            value = code_from_annex(info["arvo"], REGULATION_TYPE) if "arvo" in info else None
            infos.append((ADDITIONAL_INFO_TYPE, info["laji"], value))
        regulations.append(regulation_from_codes(ctx, unit, n, item["laji"], infos))
    approved = entry.get("hyvaksytty", {})
    rationale = [
        Rationale(
            f"Tampereen hyväksymä muunnos ({approved.get('hyvaksyja', '')} {approved.get('paivamaara', '')}).".replace(
                " )", ")"
            ),
            "hyvaksytty",
            "korkea",
            reference="knowledge/org/tampere/hyvaksytyt.yaml",
        )
    ]
    return Structure(
        regulations,
        rationale,
        list(group.get("geometria", [])),
        group.get("otsikko"),
        group.get("kirjaintunnus"),
        "korkea",
        "hyvaksytty",
    )


def propose_general(ctx: Context, unit: SourceUnit) -> GroupProposal:
    proposal = GroupProposal(key=ctx.key(unit.id, "group"), kind="yleismaarays")
    proposal.title = {"fin": unit.heading or "Yleismääräys"}
    proposal.category = unit.map
    questions: list[InterpretationQuestion] = []
    rationale = [
        Rationale(
            "YLEISMÄÄRÄYS-lohko: yleismääräysryhmä, joka koskee koko kaava-aluetta.",
            "saanto",
            "korkea",
            reference="Opas 3.2.1",
        )
    ]
    for hint in match.find_general_targets(unit.normalized_text):
        questions.append(
            policy_question(
                ctx,
                unit,
                "K3",
                "L-05",
                f"Yleismääräys koskee vain osaa alueista ({', '.join(hint.letter_codes)}).",
                f'"{hint.sentence}" – {ctx.describe("L-05")}.',
            )
        )
    finish(ctx, unit, proposal, "korkea", questions, rationale, start_index=0)
    return proposal


def finish(
    ctx: Context,
    unit: SourceUnit,
    proposal: GroupProposal,
    confidence: str,
    questions: list[InterpretationQuestion],
    rationale: list[Rationale],
    start_index: int,
) -> None:
    zone = any(r.type.value == "kehittamisvyohyke" for r in proposal.regulations)
    verbal, verbal_rationale = verbal_regulations(ctx, unit, start_index, development_zone=zone)
    proposal.regulations += verbal
    rationale += verbal_rationale
    text = unit.normalized_text
    hits = [h for reg in verbal for h in reg.verbal_types]
    if len({h.uri for h in hits}) > 1:
        questions.append(
            policy_question(
                ctx,
                unit,
                "K10",
                "L-03",
                "Useita aiheita yhdessä tekstissä.",
                f"Lajit {', '.join(h.value for h in hits)}; {ctx.describe('L-03')}.",
            )
        )
    if verbal:
        questions.append(
            policy_question(
                ctx,
                unit,
                "K11",
                "L-04",
                "Sanallisen määräyksen tyyppi.",
                f"{verbal[0].type.value}: {ctx.describe('L-04')}.",
            )
        )
    if ctx.mode == "laadinta":
        drafting_additions(ctx, unit, proposal, questions, rationale, start_index)
    for number in match.find_numbers(ctx.kb, text):
        if number.place:
            questions.append(
                policy_question(
                    ctx,
                    unit,
                    "K4",
                    "L-07",
                    f"Paikkasidonnainen numeroarvo: {number.place} {text[number.span[0] : number.span[1]]}.",
                    f'"{number.sentence}" – {ctx.describe("L-07")}.',
                )
            )
            break
    for law in match.find_law_references(ctx.kb, text):
        questions.append(
            question(
                ctx,
                unit,
                "K12",
                f"Vanhentunut lakiviittaus: {law.abbreviation}",
                [
                    ("ennallaan", "Teksti säilyy ennallaan", law.note),
                    ("korvaava", "Viittaus päivitetään", "Vain laadintatilassa."),
                ],
                "ennallaan",
                law.note,
                resolved_by="tila vooka" if ctx.mode == "vooka" else None,
                answer="ennallaan" if ctx.mode == "vooka" else None,
            )
        )
        rationale.append(Rationale(law.note, "sanasto", "korkea", quote=law.sentence))
    sub_areas = match.find_sub_areas(text)
    if len(sub_areas) > 1:
        questions.append(
            question(
                ctx,
                unit,
                "K9",
                f"Alakohtaiset määräykset ({len(sub_areas)} alakohtaa)",
                [
                    ("yksi_ryhma", "Yksi ryhmä", "Alakohdat yhden määräyksen tekstinä."),
                    (
                        "ryhma_alakohtaa_kohden",
                        "Ryhmä alakohtaa kohden (indeksoitu tunnus)",
                        "Kohdistuvat eri alueisiin.",
                    ),
                ],
                "ryhma_alakohtaa_kohden",
                "Alakohdat: " + "; ".join(sub_areas[:5]),
            )
        )
    if ctx.policy("L-01") == "lahdekaava" and len(unit.source_plans) > 1:
        questions.append(
            question(
                ctx,
                unit,
                "K15",
                "Mihin lähdekaavaan merkintä kuuluu?",
                [(f"kaava{n}", plan.name, plan.date or "") for n, plan in enumerate(unit.source_plans, 1)],
                None,
                f"{ctx.describe('L-01')}: merkintä on kohdistettava lähdekaavaansa.",
            )
        )
    for q in questions:
        if q.resolved_by and q.resolved_by.startswith("linjaus"):
            rationale.append(Rationale(f"{q.kind}: {q.basis}", "linjaus", "korkea", reference=q.resolved_by))
    proposal.questions = questions
    proposal.rationale = rationale
    proposal.confidence = confidence
    proposal.status = "ehdotus"


def fold(text: str) -> str:
    return match.fold(text or "")


# --------------------------------------------------------------------------------------
# Drafting mode (laadintatila, UC2, ADR-0017)


def paragraphs_of(text: str, base: int = 0) -> list[tuple[int, int, str]]:
    """Paragraphs (empty line = break) with their spans in the text, offset by ``base``."""
    found, offset = [], 0
    for paragraph in text.split("\n\n"):
        start = text.index(paragraph, offset)
        offset = start + len(paragraph)
        if paragraph.strip():
            found.append((base + start, base + offset, paragraph))
    return found


def recommendation_paragraphs(ctx: Context, text: str) -> list[tuple[int, int, str]]:
    return [p for p in paragraphs_of(text) if match.recommendation_words(ctx.kb, p[2])]


def drafting_additions(
    ctx: Context,
    unit: SourceUnit,
    proposal: GroupProposal,
    questions: list[InterpretationQuestion],
    rationale: list[Rationale],
    start_index: int,
) -> None:
    """A new regulation: one numeric value as a quantity (opas 3.3.9) and K13 for recommendations.

    The text is not changed: the number stays in the verbal text (R-18 tells that it is also a
    quantity) and a recommendation paragraph is moved only when K13 is answered ``suositus``.
    """
    text = unit.normalized_text
    numbers = [n for n in match.find_numbers(ctx.kb, text) if not n.place]
    if proposal.kind == "kaavakohde" and numbers:
        distinct = {(n.quantity_code, n.value) for n in numbers}
        if len(distinct) == 1:
            hit = numbers[0]
            number: float | int = int(hit.value) if hit.data_type.endswith("Numeric") else hit.value
            quantity = Regulation(
                key=ctx.key(unit.id, "q0"),
                type=ctx.ref(REGULATION_TYPE, hit.quantity_code),
                value=Value(hit.data_type, number=number, unit=hit.measure),
                text_span=hit.span,
            )
            quantity.rationale.append(
                Rationale(
                    f"Numeroarvo {text[hit.span[0] : hit.span[1]]} suureena {hit.quantity_code} "
                    "(laadintatila: suureellinen määräys, yksi koodi ja yksi arvo). Teksti säilyy ennallaan.",
                    "sanasto",
                    "keskitaso",
                    quote=text[hit.span[0] : hit.span[1]],
                    reference="Opas 3.3.9; sanasto / suureet",
                )
            )
            proposal.regulations.insert(start_index, quantity)
        else:
            rationale.append(
                Rationale(
                    f"Tekstissä on useita numeroarvoja ({', '.join(text[n.span[0] : n.span[1]] for n in numbers)}); "
                    "ryhmässä voi olla vain yksi suure (R-04), joten ne jäävät sanalliseen tekstiin. "
                    "Jaa tarvittaessa omiksi ryhmikseen.",
                    "saanto",
                    "keskitaso",
                    reference="Opas 3.3.9",
                )
            )
    candidates = recommendation_paragraphs(ctx, text)
    if not candidates:
        return
    binding = [p for p in candidates if match.binding_words(ctx.kb, p[2])]
    found = sorted({w for p in candidates for w in match.recommendation_words(ctx.kb, p[2])})
    several = len(paragraphs_of(text)) > 1
    basis = f"Ei-velvoittavat ilmaukset: {', '.join(found)}."
    if binding:
        basis += (
            " Samassa kappaleessa on myös velvoittava ilmaus, joten suositus on kaavamääräys; "
            "erota suositus omaksi kappaleekseen (tyhjä rivi), jos se on tarkoitettu kaavasuositukseksi."
        )
    questions.append(
        question(
            ctx,
            unit,
            "K13",
            f"Määräys vai suositus? – {unit.heading or 'yleismääräys'}",
            [
                ("maarays", "Kaavamääräys", "Teksti pysyy sanallisena määräyksenä."),
                (
                    "suositus",
                    "Kaavasuositus" + (" (suosittelevat kappaleet)" if several else ""),
                    "Kappale siirtyy kaavasuositukseksi (Ryhti PlanRecommendation, Arho plan_propositions).",
                ),
            ],
            "maarays" if binding else "suositus",
            basis,
        )
    )


def apply_recommendations(ctx: Context, unit: SourceUnit) -> None:
    """K13 answered ``suositus``: recommendation paragraphs become plan recommendations.

    The remaining text stays as verbal regulations (one per contiguous run of paragraphs), so
    every text keeps its span in the source and nothing is reworded.
    """
    proposal = unit.proposal
    if ctx.mode != "laadinta" or proposal is None:
        return
    k13 = next((q for q in proposal.questions if q.kind == "K13"), None)
    if k13 is None or k13.answer != "suositus":
        return
    method = "kielimalli" if k13.resolved_by == "kielimalli" else "kayttaja"
    regulations: list[Regulation] = []
    for reg in proposal.regulations:
        if reg.type.value not in VERBAL_TYPES or not reg.value or not reg.text_span:
            regulations.append(reg)
            continue
        parts = paragraphs_of(reg.value.text.get("fin", ""), reg.text_span[0])
        moving = [p for p in parts if match.recommendation_words(ctx.kb, p[2])] or (
            parts if len(parts) == 1 else []
        )
        if not moving:
            regulations.append(reg)
            continue
        run: list[tuple[int, int, str]] = []
        for part in parts:
            if part in moving:
                _keep_run(ctx, unit, reg, run, regulations)
                proposal.recommendations.append(
                    Recommendation(
                        key=ctx.key(unit.id, f"p{part[0]}"),
                        text={"fin": part[2]},
                        text_span=(part[0], part[1]),
                        rationale=[
                            Rationale(
                                "Kappale on kaavasuositus (K13); teksti lähteen mukaisena.",
                                method,
                                "keskitaso",
                                quote=part[2][:120],
                                reference="Opas 2.3.4",
                            )
                        ],
                    )
                )
            else:
                run.append(part)
        _keep_run(ctx, unit, reg, run, regulations)
    proposal.regulations = regulations


def _keep_run(
    ctx: Context,
    unit: SourceUnit,
    reg: Regulation,
    run: list[tuple[int, int, str]],
    regulations: list[Regulation],
) -> None:
    """Contiguous paragraphs that stay a verbal regulation (text = the source span)."""
    if not run:
        return
    start, end = run[0][0], run[-1][1]
    kept = copy.deepcopy(reg)
    kept.key = ctx.key(unit.id, f"s{start}")
    kept.value = Value("LocalizedText", text={"fin": unit.normalized_text[start:end]})
    kept.text_span = (start, end)
    regulations.append(kept)
    run.clear()


def propose(ctx: Context, unit: SourceUnit) -> GroupProposal:
    proposal = propose_general(ctx, unit) if unit.kind == "yleismaarays" else propose_marking(ctx, unit)
    ctx.proposals[unit.id] = proposal
    return proposal


# --------------------------------------------------------------------------------------
# Policy L-05: structured additions to targeted markings


def apply_targeted_additions(ctx: Context, units: list[SourceUnit]) -> None:
    if ctx.policy("L-05") != "sailytys_ja_rakenteinen_lisays":
        return
    additions = ctx.kb.vocabulary.get("kohdistuslisaykset", [])
    groups = [u for u in units if u.proposal and u.proposal.kind == "kaavakohde"]
    for unit in units:
        if unit.kind != "yleismaarays":
            continue
        for hint in match.find_general_targets(unit.normalized_text):
            for addition in additions:
                if addition["ehto"] not in hint.sentence:
                    continue
                for target in groups:
                    code = target.proposal.letter_code
                    if not code or match.base_letter_code(code) not in hint.letter_codes:
                        continue
                    main = next(
                        (r for r in target.proposal.regulations if r.type.value not in VERBAL_TYPES), None
                    )
                    if main is None:
                        continue
                    value = addition["arvo"]
                    uri = f"{URI_PREFIX}{value['koodisto']}/code/{value['koodi']}"
                    main.additional_infos.append(
                        AdditionalInfo(
                            ctx.ref(ADDITIONAL_INFO_TYPE, addition["lisatieto"]),
                            Value("Code", code=CodeRef(uri, ctx.kb.codelist_version(value["koodisto"]))),
                        )
                    )
                    main.rationale.append(
                        Rationale(
                            f"Yleismääräyksen kohdistus: {addition['lisatieto']} = {value['koodisto']} {value['koodi']} "
                            f"({addition['peruste']}); {ctx.describe('L-05')}.",
                            "linjaus",
                            "keskitaso",
                            quote=hint.sentence,
                            reference=f"yksikkö {unit.id}",
                        )
                    )


# --------------------------------------------------------------------------------------
# Project


def convert_units(
    kb: KnowledgeBase,
    units: list[SourceUnit],
    choices: list[PolicyChoice],
    *,
    plan_level: str = "yleiskaava",
    mode: str = "vooka",
    name: str = "muunnos",
    source: SourceDocument | None = None,
    map_title: str | None = None,
    decisions: list[Decision] | None = None,
) -> ConversionProject:
    from kaavamaaraysavustaja.core import decisions as decision_log
    from kaavamaaraysavustaja.core.rules import RuleEngine

    decisions = list(decisions or [])
    ctx = Context(kb, plan_level, mode, {c.id: c for c in choices}, name)
    ctx.answers = decision_log.apply_input_hints(kb, decisions, units)
    engine = RuleEngine(kb)
    for unit in units:
        unit.proposal = propose(ctx, unit)
    add_sub_area_questions(ctx, units)
    apply_targeted_additions(ctx, units)
    source_plans = []
    for unit in units:
        for plan in unit.source_plans:
            if plan not in source_plans:
                source_plans.append(plan)
    meta = Meta(
        plan_level=plan_level,
        mode=mode,
        title=name,
        map=map_title,
        source_plans=source_plans,
        knowledge_version=kb.version,
        codelist_versions={cl: kb.index.version(cl) for cl in kb.index.codelists()},
        rules_version=f"{kb.manifest['saannot']} v{kb.rules['versio']}",
        policy_version=f"{kb.manifest['linjaukset']} v{_policy_file_version(kb)}",
        assistant_version=ASSISTANT_VERSION,
    )
    provenance = Provenance(
        step="saantopohjainen",
        tool_version=ASSISTANT_VERSION,
        at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        knowledge_version=kb.version,
        details={"yksikoita": len(units), "kielimalli": None},
    )
    project = ConversionProject(
        meta=meta,
        sources=[source] if source else [],
        units=units,
        policy_choices=choices,
        provenance=[provenance],
    )
    warnings = decision_log.apply_answers(kb, project, decisions)
    decision_log.record(project, decisions)
    for unit in units:
        apply_recommendations(ctx, unit)
        engine.apply(unit, plan_level=plan_level, mode=mode)
        unit.proposal.confidence, unit.proposal.confidence_basis = overall_confidence(unit.proposal)
    if decisions:
        provenance.details["ratkaisuja"] = len(decisions)
        provenance.details["ratkaisujen_varoitukset"] = warnings + [
            f"ratkaisulle {d.question_id} ({d.heading or d.unit_id}) ei löytynyt yksikköä"
            for d in decision_log.unmatched(decisions, units)
        ]
    return project


def _policy_file_version(kb: KnowledgeBase) -> Any:
    import yaml

    data = yaml.safe_load((kb.directory / kb.manifest["linjaukset"]).read_text(encoding="utf-8"))
    return data.get("versio")


RANK = {"korkea": 2, "keskitaso": 1, "matala": 0}


def overall_confidence(proposal: GroupProposal) -> tuple[str, str]:
    """Plan 6.9: high only with rule-based confirmation, no rule errors and no open questions."""
    if proposal.kind == "ei_maarays":
        return "matala", "informatiivinen merkintä: vahvistettava"
    open_q = proposal.open_questions()
    errors = proposal.results("virhe")
    warnings = proposal.results("varoitus")
    if errors or warnings or open_q:
        reasons = []
        if errors:
            reasons.append(f"{len(errors)} virhettä")
        if warnings:
            reasons.append(f"{len(warnings)} varoitusta")
        if open_q:
            reasons.append("avoin tulkintakysymys: " + ", ".join(q.kind for q in open_q))
        return "matala", "; ".join(reasons)
    parts = [proposal.confidence, *(r.confidence for r in proposal.rationale)]
    parts += [r.confidence for reg in proposal.regulations for r in reg.rationale]
    lowest = min(parts, key=lambda c: RANK.get(c, 0))
    if lowest == "matala":
        return "keskitaso", "osassa perusteluista matala varmuus, ei virheitä eikä avoimia kysymyksiä"
    if lowest == "keskitaso" or proposal.results("huomio"):
        return "keskitaso", "sääntöpohjainen tulos; osa perusteluista keskitasoa tai huomioita"
    return (
        "korkea",
        "sääntöpohjainen tulos (vakioluettelo tai hyväksytty muunnos), ei virheitä eikä avoimia kysymyksiä",
    )
