"""Rule-based recognition (plan 6.5 step 4): approved conversions, Katja annex 4, code names,
heading modifiers, verbal regulation types, numbers and units, targeting hints and law
references. Everything that varies comes from the knowledge base (CLAUDE.md rule 3).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from kaavamaaraysavustaja.knowledge.base import KnowledgeBase
from kaavamaaraysavustaja.knowledge.codelists import REGULATION_TYPE, Code

AREA_RESERVATION = "aluevaraus"
QUANTITY = "suure"


def fold(text: str) -> str:
    """Case-folded, whitespace-collapsed text for comparisons."""
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.casefold().replace("­", "").split())


def words(text: str) -> list[str]:
    return re.findall(r"[0-9a-zåäö]+(?:-[0-9a-zåäö]+)*", fold(text))


# --------------------------------------------------------------------------------------
# Approved conversions (linjauskirjasto)


def find_approved(kb: KnowledgeBase, heading: str | None, letter_code: str | None) -> dict[str, Any] | None:
    if not heading:
        return None
    for entry in kb.approved:
        source = entry.get("lahde", {})
        if fold(source.get("otsikko", "")) == fold(heading) and (source.get("kirjaintunnus") or None) == (
            letter_code or None
        ):
            return entry
    return None


# --------------------------------------------------------------------------------------
# Heading modifiers (määreet)


@dataclass
class Modifier:
    word: str
    info_code: str
    needs_confirmation: bool


def split_modifiers(kb: KnowledgeBase, heading: str) -> tuple[str, list[Modifier]]:
    """``KEHITETTÄVÄ RAUTATIE`` → (``rautatie``, [kehitettava]). Leading words only."""
    table = {fold(m["sana"]): m for m in kb.vocabulary.get("maareet", [])}
    tokens = fold(heading).split()
    found: list[Modifier] = []
    while len(tokens) > 1 and tokens[0] in table:
        entry = table[tokens.pop(0)]
        found.append(Modifier(entry["sana"], entry["lisatieto"], bool(entry.get("vahvistettava"))))
    return " ".join(tokens), found


# --------------------------------------------------------------------------------------
# Katja annex 4


@dataclass
class AnnexMatch:
    row: dict[str, Any]
    how: str  # otsikko | otsikko_maareet | tunnus
    modifiers: list[Modifier] = field(default_factory=list)

    @property
    def reference(self) -> str:
        return f"Katja liite 4 / rivi {self.row['rivi']}: {self.row.get('kirjaintunnus') or '–'} {self.row['otsikko']}"


def _annex_rows(kb: KnowledgeBase, plan_level: str) -> list[dict[str, Any]]:
    return kb.annex.get(plan_level, [])


def base_letter_code(code: str) -> str:
    """``ge-1`` → ``ge``, ``c-2`` → ``c``, ``R(200)`` → ``R``."""
    return re.sub(r"(-\d+|\(\d+\))$", "", code)


def find_annex(
    kb: KnowledgeBase, plan_level: str, heading: str | None, letter_code: str | None
) -> list[AnnexMatch]:
    """Annex 4 rows for a heading, best first. Several rows = several geometries."""
    rows = _annex_rows(kb, plan_level)
    if heading:
        exact = [
            AnnexMatch(r, "otsikko") for r in rows if r.get("otsikko") and fold(r["otsikko"]) == fold(heading)
        ]
        if exact:
            return exact
        stripped, modifiers = split_modifiers(kb, heading)
        if modifiers:
            # Prefer a row whose own title includes the modifier ("Uusi eritasoliittymä" is matched exactly above).
            base = [
                AnnexMatch(r, "otsikko_maareet", modifiers)
                for r in rows
                if r.get("otsikko") and fold(r["otsikko"]) == stripped
            ]
            base = [m for m in base if not _row_has_ymparistomuutos(m.row)]
            if base:
                return base
    if letter_code:
        code = base_letter_code(letter_code)
        by_code = [AnnexMatch(r, "tunnus") for r in rows if r.get("kirjaintunnus") == code]
        if by_code and heading and _shares_word(heading, by_code[0].row["otsikko"]):
            return by_code
    return []


def _row_has_ymparistomuutos(row: dict[str, Any]) -> bool:
    return any(i.get("laji") in ("uusi", "kehitettava", "olemassaOleva") for i in row.get("lisatiedot", []))


def _shares_word(a: str, b: str) -> bool:
    stems_a = {w[:6] for w in words(a) if len(w) >= 5}
    stems_b = {w[:6] for w in words(b) if len(w) >= 5}
    return bool(stems_a & stems_b)


def choose_geometry_row(matches: list[AnnexMatch], hint: str | None) -> AnnexMatch:
    """Pick the annex row for the geometry hint; area first, then point, then line."""
    if hint:
        for match in matches:
            if match.row.get("geometria") == hint:
                return match
    order = {"alue": 0, "viiva": 1, "piste": 2}
    return sorted(matches, key=lambda m: order.get(m.row.get("geometria") or "", 9))[0]


# --------------------------------------------------------------------------------------
# Code names (sanastopohjainen haku koodien nimistä)


@dataclass
class CodeMatch:
    code: Code
    score: float
    how: str  # nimi | nimi_osittain


def find_codes_by_name(kb: KnowledgeBase, plan_level: str, heading: str) -> list[CodeMatch]:
    """Regulation type codes whose Finnish name matches the heading (modifiers removed)."""
    stripped, _ = split_modifiers(kb, heading)
    target = words(stripped)
    if not target:
        return []
    results: list[CodeMatch] = []
    for code in kb.index.usable_codes(REGULATION_TYPE, plan_level, kb.valid_on):
        name = code.name.get("fi", "")
        if not name:
            continue
        name_words = words(name)
        if name_words == target:
            results.append(CodeMatch(code, 1.0, "nimi"))
            continue
        # Every heading word matches a name word up to an inflection ending, e.g.
        # "maatilan talouskeskus" ~ "maatilan talouskeskuksen alue".
        if all(any(same_stem(w, n) for n in name_words) for w in target):
            score = len(target) / max(len(name_words), 1)
            if score >= 0.6:
                results.append(CodeMatch(code, score, "nimi_osittain"))
            continue
        # The name is contained in a longer heading: "luonnonsuojelualue tai -kohde".
        content = [w for w in target if w not in STOP_WORDS]
        name_content = [w for w in name_words if w not in STOP_WORDS] or name_words
        if (
            content
            and all(any(same_stem(n, w) for w in content) for n in name_content)
            and len(content) - len(name_content) <= 2
        ):
            results.append(CodeMatch(code, 0.5 * len(name_content) / len(content), "nimi_sisaltyy"))
    return sorted(results, key=lambda m: -m.score)


STOP_WORDS = {"ja", "tai", "sekä", "kohde", "-kohde", "alue"}


def same_stem(word: str, other: str) -> bool:
    """``talouskeskus`` ~ ``talouskeskuksen``: common prefix covers the word but its last 3 letters."""
    word, other = word.strip("-"), other.strip("-")
    common = 0
    for a, b in zip(word, other, strict=False):
        if a != b:
            break
        common += 1
    return common == len(word) == len(other) or (
        common >= 5 and common >= len(word) - 3 and common >= len(other) - 6
    )


def find_mixed_use(kb: KnowledgeBase, plan_level: str, heading: str) -> list[Code]:
    """K2: ``ASUMISEN JA VIRKISTYKSEN SEKOITTUNUT ALUE`` → [asumisenAlue, virkistysalue]."""
    m = re.match(r"^(.+?) ja (.+?) sekoittunut alue(?: tai kohde)?$", fold(heading))
    if not m:
        return []
    codes = []
    reservations = [
        c
        for c in kb.index.usable_codes(REGULATION_TYPE, plan_level, kb.valid_on)
        if c.in_extension(AREA_RESERVATION, kb.valid_on)
    ]
    for part in m.groups():
        found = [c.code for c in find_codes_by_name(kb, plan_level, f"{part} alue") if c.how == "nimi"]
        if not found:
            stem = part.split()[-1][:7]
            found = sorted(
                (c for c in reservations if fold(c.name.get("fi", "")).startswith(stem)),
                key=lambda c: len(c.name.get("fi", "")),
            )
        if not found:
            return []
        codes.append(found[0])
    return codes


def find_keyword(kb: KnowledgeBase, heading: str) -> dict[str, Any] | None:
    """Fallback heading keyword (otsikon avainsana), e.g. VYÖHYKE → kehittämisvyöhyke (K5)."""
    tokens = words(heading)
    for entry in kb.vocabulary.get("otsikon_avainsanat", []):
        stem = fold(entry["alku"])
        if any(token.endswith(stem) or token.startswith(stem) for token in tokens):
            return entry
    return None


def is_informative(kb: KnowledgeBase, heading: str | None) -> bool:
    if not heading:
        return False
    tokens = set(words(heading))
    return any(fold(entry["sana"]) in tokens for entry in kb.vocabulary.get("informatiiviset", []))


# --------------------------------------------------------------------------------------
# Verbal regulation types (sanallisen määräyksen lajit)


SENTENCE = re.compile(r"[^.!?]+[.!?]?")


def sentence_at(text: str, index: int) -> str:
    for match in SENTENCE.finditer(text):
        if match.start() <= index < match.end():
            return match.group(0).strip()
    return text.strip()


@dataclass
class VerbalTypeHit:
    code: str
    keyword: str
    count: int
    first: int
    quote: str


def find_verbal_types(kb: KnowledgeBase, text: str, limit: int = 3) -> list[VerbalTypeHit]:
    lowered = text.casefold()
    hits: list[VerbalTypeHit] = []
    for code, stems in kb.vocabulary.get("sanallisen_lajit", {}).items():
        positions = []
        keyword = ""
        for stem in stems:
            for match in re.finditer(r"\b\w*" + re.escape(stem.casefold()), lowered):
                positions.append(match.start())
                if not keyword:
                    keyword = stem
        if positions:
            first = min(positions)
            hits.append(VerbalTypeHit(code, keyword, len(positions), first, sentence_at(text, first)))
    hits.sort(key=lambda h: (-h.count, h.first))
    return hits[:limit]


def verbal_regulation_type(kb: KnowledgeBase, text: str, policy_l04: str) -> tuple[str, str | None]:
    """Kaavamääräyslaji of a verbal regulation by policy L-04: (code, matched keyword)."""
    if policy_l04 != "alakoodit":
        return "sanallinenMaarays", None
    lowered = text.casefold()
    best: tuple[int, str, str] | None = None
    for code, stems in kb.vocabulary.get("sanallisen_maarayksen_tyypit", {}).items():
        count = sum(lowered.count(stem.casefold()) for stem in stems)
        if count and (best is None or count > best[0]):
            best = (count, code, next(s for s in stems if s.casefold() in lowered))
    return (best[1], best[2]) if best else ("sanallinenMaarays", None)


# --------------------------------------------------------------------------------------
# Numbers and units (suureet)

NUMBER = r"(?P<number>\d{1,3}(?:[  ]\d{3})+|\d+(?:,\d+)?)"
PLACE_BEFORE = re.compile(
    r"(?:\b(?P<place>[A-ZÄÖÅ][a-zäöå]+(?:-[A-ZÄÖÅ]?[a-zäöå]+)?)(?:ssa|ssä|lla|llä)\b[^.]*?$)"
)
PLACE_LIST = re.compile(r"\b(?P<place>[A-ZÄÖÅ][a-zäöå]+(?:-[A-ZÄÖÅ][a-zäöå]+)?)\s+$")


@dataclass
class NumberHit:
    value: float
    unit: str
    quantity_code: str
    span: tuple[int, int]
    place: str | None
    sentence: str
    data_type: str = "PositiveNumeric"  # Ryhti dataType of the quantity value
    measure: str | None = None  # unitOfMeasure


def find_numbers(kb: KnowledgeBase, text: str) -> list[NumberHit]:
    hits: list[NumberHit] = []
    for entry in kb.vocabulary.get("suureet", []):
        unit = entry["yksikko"]
        if unit.endswith("="):
            pattern = re.compile(re.escape(unit) + r"\s?(?P<number>\d+(?:,\d+)?)")
        else:
            pattern = re.compile(NUMBER + r"\s?" + re.escape(unit))
        for match in pattern.finditer(text):
            raw = match.group("number").replace(" ", "").replace(" ", "").replace(",", ".")
            value = float(raw)
            before = text[max(0, match.start() - 80) : match.start()]
            sentence_start = before.rfind(". ")
            before = before[sentence_start + 2 :] if sentence_start >= 0 else before
            place = None
            m = PLACE_LIST.search(before) or PLACE_BEFORE.search(before)
            if m and not _is_sentence_start(before, m.start("place")):
                place = m.group("place")
            hits.append(
                NumberHit(
                    value,
                    unit,
                    entry["kaavamaarayslaji"],
                    (match.start(), match.end()),
                    place,
                    sentence_at(text, match.start()),
                    entry.get("arvotyyppi")
                    or ("PositiveNumeric" if value.is_integer() else "PositiveDecimal"),
                    entry.get("mittayksikko"),
                )
            )
    return sorted(hits, key=lambda h: h.span)


def _is_sentence_start(text: str, index: int) -> bool:
    return text[:index].strip() == ""


# --------------------------------------------------------------------------------------
# General regulation targeting (yleismääräyksen kohdistus) and law references

TARGETS = re.compile(
    r"(?P<codes>\b[A-ZÄÖ]{1,4}[a-zäö]?(?:\s*(?:,|ja|tai)\s*[A-ZÄÖ]{1,4}[a-zäö]?)*)\s*-alue(?:illa|illa|ille|iden|ita|et)\b"
    r"|\b(?P<lower>[a-zäö]{1,4})-alue(?:illa|ille|iden|ita|et)\b"
)


@dataclass
class TargetHint:
    sentence: str
    letter_codes: list[str]


def find_general_targets(text: str) -> list[TargetHint]:
    hints: dict[str, TargetHint] = {}
    for match in TARGETS.finditer(text):
        raw = match.group("codes") or match.group("lower") or ""
        codes = [c for c in re.split(r"\s*(?:,|\bja\b|\btai\b)\s*", raw) if c]
        sentence = sentence_at(text, match.start())
        hint = hints.setdefault(sentence, TargetHint(sentence, []))
        hint.letter_codes += [c for c in codes if c not in hint.letter_codes]
    return list(hints.values())


@dataclass
class LawReference:
    abbreviation: str
    note: str
    sentence: str


def find_law_references(kb: KnowledgeBase, text: str) -> list[LawReference]:
    found = []
    for entry in kb.vocabulary.get("lakiviittaukset", []):
        for match in re.finditer(r"\b" + re.escape(entry["lyhenne"]) + r"(?=\s?\d|\b)", text):
            found.append(LawReference(entry["lyhenne"], entry["huomio"], sentence_at(text, match.start())))
            break
    return found


def find_sub_areas(text: str) -> list[str]:
    """Sub-area specific parts (K9): "Härmälänojan valuma-alue / teksti" or numbered "1. …"."""
    slash = re.findall(r"(?:^|[.:]\s+)([A-ZÄÖÅ][\wäöå-]+(?:\s[\wäöå-]+){0,3})\s+/\s", text)
    if slash:
        return slash
    # Numbered items in the text: "5. Amuri. Alueen …", "6. Tammela. …"
    numbered = re.findall(r"(?:^|[.\n]\s*)(\d{1,2}\.\s[A-ZÄÖÅ][\wäöå -]{1,40}?)\.\s", text)
    return numbered if len(numbered) > 1 else []


def phrases_in(text: str, phrases: list[str]) -> list[str]:
    """Phrases found as whole words (case and punctuation ignored)."""
    tokens = f" {' '.join(words(text))} "
    return [p for p in phrases if f" {' '.join(words(p))} " in tokens]


def recommendation_words(kb: KnowledgeBase, text: str) -> list[str]:
    """K13 (drafting mode): non-binding expressions such as "suositellaan"."""
    return phrases_in(text, kb.vocabulary.get("suosittelevat_ilmaukset", []))


def binding_words(kb: KnowledgeBase, text: str) -> list[str]:
    """Binding expressions ("tulee", "ei saa" …), punctuation ignored."""
    return phrases_in(text, kb.vocabulary.get("velvoittavat_ilmaukset", []))


def obligation_words(kb: KnowledgeBase, text: str) -> list[str]:
    lowered = f" {fold(text)} "
    return [w for w in kb.vocabulary.get("velvoittavat_ilmaukset", []) if f" {fold(w)} " in lowered]
