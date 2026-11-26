"""Input, normalization and parsing into units (plan 6.5 steps 1–3, ADR-0009).

The core reads **text only**. A PDF is turned into a local text file by
``tools/extract_pdf_text.py`` (development tool, the PDF libraries are not imported here).
The text keeps the line layout of the source legend; the user may correct it before the
conversion and add directive lines (``@sivu 3``, ``@osio MAANKÄYTTÖ`` …, see ADR-0009).

Normalization keeps the raw text untouched and records every change that is not a plain
line break (hyphenation, soft hyphens, zero-width characters, double spaces, suspicious
strings) in a difference list. In VOOKA mode the normalized text confirmed by the user is
what goes into the verbal regulations; ``content_skeleton`` lets rule R-19 check that the
normalization changed nothing but layout and the recorded corrections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kaavamaaraysavustaja.core.model import NormalizationChange, SourcePlan, SourceUnit

SOFT_HYPHEN = "­"
ZERO_WIDTH = "​‌‍⁠﻿"
VOWELS = set("aeiouyäöåAEIOUYÄÖÅ")

GENERAL = {"YLEISMÄÄRÄYS", "YLEISMÄÄRÄYKSET"}
LEGEND_START = re.compile(r"^\s*Kaavamerkinnät ja -määräykset\s*$")
MAP_LINE = re.compile(r"^\s*KARTTA\s+(\d+[a-z]?)\b\s*-?\s*(.*?)\s*$")
COLLECTION_LINE = re.compile(
    r"^\s*([A-ZÄÖÅ -]*YLEISKAAVAYHDISTELMÄ|[A-ZÄÖÅ -]*OSAYLEISKAAVAT|OSA-ALUEIDEN KEHITTÄMISPERIAATTEET)\s*$"
)
DIRECTIVE = re.compile(r"^@(\w+)\s*(.*?)\s*$")
CODE_TOKEN = re.compile(r"^[A-Za-zÄÖÅäöå0-9()\-]{1,12}$")
PLAN_WITH_DATE = re.compile(r"\s*(.+?)\s*\((\d{1,2}\.\d{1,2}\.\d{4})\)\s*,?")

# Section headings (väliotsikot) of the Tampere compilation. They look like markings
# (upper case, no text of their own); ``@osio`` adds others without code changes.
SECTION_HEADINGS = {
    "MAANKÄYTTÖ",
    "LIIKENNEJÄRJESTELMÄ",
    "STRATEGISET KEHITTÄMISPERIAATEMERKINNÄT",
    "ARVOALUEET JA KOHTEET",
    "KESTÄVÄ VESITALOUS",
    "YMPÄRISTÖTERVEYS",
    "YHDYSKUNTATEKNINEN HUOLTO",
    "VIHERYMPÄRISTÖ",
    "KULTTUURIPERINTÖ",
}
# Second-level headings (alaotsikot) under a section heading, e.g. YHDYSKUNTATEKNINEN HUOLTO /
# ENERGIAHUOLTO. They are added to the section path instead of becoming markings.
SUBSECTION_HEADINGS = {
    "ENERGIAHUOLTO",
    "SÄHKÖNJAKELU",
    "VESIHUOLTO",
    "JÄTEHUOLTO",
    "YLEISTEN ALUEIDEN HUOLTO",
}
NUMBERED_HEADING = re.compile(r"^(\d{1,2})\.\s+(?=\S)")
FORCED_CODE = re.compile(r"^[A-ZÄÖÅ][A-Za-zÄÖÅäöå0-9()\-]{0,5}$")


# --------------------------------------------------------------------------------------
# Normalization


@dataclass
class Normalized:
    text: str
    changes: list[NormalizationChange] = field(default_factory=list)


def _clean_line(line: str, lineno: int | None, changes: list[NormalizationChange]) -> str:
    if SOFT_HYPHEN in line:
        changes.append(
            NormalizationChange(
                "pehmea_tavuviiva", line.strip(), line.replace(SOFT_HYPHEN, "").strip(), lineno
            )
        )
        line = line.replace(SOFT_HYPHEN, "")
    if any(ch in line for ch in ZERO_WIDTH):
        cleaned = "".join(ch for ch in line if ch not in ZERO_WIDTH)
        changes.append(NormalizationChange("nollalevea_merkki", repr(line.strip()), cleaned.strip(), lineno))
        line = cleaned
    stripped = line.strip()
    if "  " in stripped:
        collapsed = re.sub(r" {2,}", " ", stripped)
        changes.append(
            NormalizationChange("valilyonti", stripped, collapsed, lineno, "ylimääräinen välilyönti")
        )
        line = line.replace(stripped, collapsed)
    return line


def _join(prev: str, nxt: str, lineno: int | None, changes: list[NormalizationChange]) -> str:
    """Join two text lines, undoing line-end hyphenation."""
    head = prev.rstrip()
    trailing_space = head != prev
    tail = nxt.lstrip()
    if not head:
        return tail
    if not tail:
        return head
    first = tail[0]
    # "käyt -" + "tötarkoituksesta": the compilation's hyphenation is " -" at the line end.
    if head.endswith(" -") and first.isalpha() and (first.islower() or head[:-2].isupper()):
        word_end = head[:-2].rsplit(" ", 1)[-1]
        joined = head[:-2] + tail
        changes.append(
            NormalizationChange(
                "tavutus", f"{word_end} -⏎{tail.split(' ', 1)[0]}", _word_at(joined, len(head) - 2), lineno
            )
        )
        return joined
    if head.endswith("-") and not trailing_space and len(head) > 1 and head[-2].isalpha() and first.isalpha():
        before = head[-2]
        same_case = first.islower() or (head.split(" ")[-1].isupper() and first.isupper())
        if same_case:
            word_end = head.rsplit(" ", 1)[-1]
            if before.lower() == first.lower() and before in VOWELS:
                # vapaa-|ajan: a compound with the same vowel at the boundary keeps its hyphen.
                joined = head + tail
                changes.append(
                    NormalizationChange(
                        "tavutus_yhdysmerkki",
                        f"{word_end}⏎{tail.split(' ', 1)[0]}",
                        _word_at(joined, len(head) - 1),
                        lineno,
                        "yhdysmerkki säilytetty (sama vokaali sanan rajalla)",
                        needs_confirmation=True,
                    )
                )
                return joined
            joined = head[:-1] + tail
            changes.append(
                NormalizationChange(
                    "tavutus", f"{word_end}⏎{tail.split(' ', 1)[0]}", _word_at(joined, len(head) - 1), lineno
                )
            )
            return joined
    return head + " " + tail


def _word_at(text: str, index: int) -> str:
    start = text.rfind(" ", 0, index) + 1
    end = text.find(" ", index)
    return text[start : end if end >= 0 else len(text)]


SUSPICIOUS = [
    # Lower-case l inside an upper-case word: OCR/extraction for I ("ERITASOLllTTYMÄ").
    (
        re.compile(r"\b[A-ZÄÖÅ]{2,}l+[A-ZÄÖÅ]+\b"),
        lambda m: m.group(0).replace("l", "I"),
        "pieni l isossa sanassa",
    ),
]
FLAGS = [
    (re.compile(r"\b[A-ZÄÖÅ]{2,5}\d"), "lyhenne ja numero ilman välilyöntiä"),
    (re.compile(r"(?i)\b\w*([aeiouyäö])\1\1\w*\b"), "kolme samaa vokaalia: puuttuuko yhdysmerkki?"),
    (re.compile(r"(?<!\.)\.\.(?!\.)"), "kaksi pistettä"),
]


def _suspicious(text: str, lineno: int | None, changes: list[NormalizationChange]) -> str:
    for pattern, fix, note in SUSPICIOUS:

        def replace(match: re.Match, fix=fix, note=note) -> str:
            fixed = fix(match)
            changes.append(
                NormalizationChange(
                    "epailyttava_korjaus", match.group(0), fixed, lineno, note, needs_confirmation=True
                )
            )
            return fixed

        text = pattern.sub(replace, text)
    for pattern, note in FLAGS:
        for match in pattern.finditer(text):
            changes.append(
                NormalizationChange(
                    "epailyttava",
                    _word_at(text, match.start()),
                    _word_at(text, match.start()),
                    lineno,
                    note,
                    needs_confirmation=True,
                )
            )
    return text


def is_subtitle(prev: str | None, line: str, nxt: str | None) -> bool:
    """A short mixed-case subtitle inside a text block (``Kulttuuriympäristö``, ``Maalämpö``).

    The previous text ends a sentence, the line has no trailing space (a wrapped line has one)
    and no final punctuation, and the next line starts a new sentence.
    """
    text = line.strip()
    if not text or line != line.rstrip() or text[-1] in ".,:;-–" or not text[0].isupper():
        return False
    if len(text) > 45 or len(text.split()) > 5 or is_upper_heading(text):
        return False
    if prev is not None and not prev.rstrip().endswith((".", ":")):
        return False
    return bool(nxt and nxt.strip()[:1].isupper())


def normalize_lines(lines: list[tuple[int | None, str]]) -> Normalized:
    """Normalize a block of input lines. Empty lines are paragraph breaks (kept as ``\\n\\n``).

    A subtitle inside the block (:func:`is_subtitle`) is kept as a paragraph of its own.
    """
    changes: list[NormalizationChange] = []
    paragraphs: list[str] = []
    current: str | None = None
    for n, (lineno, raw) in enumerate(lines):
        if raw.strip() == "" and raw == "":
            if current is not None:
                paragraphs.append(current)
                current = None
            continue
        if raw.strip() == "":
            continue  # whitespace-only line: a column break in the PDF
        nxt = next((t for _, t in lines[n + 1 :] if t.strip()), None)
        if n > 0 and is_subtitle(current, raw, nxt):
            if current is not None:
                paragraphs.append(current)
            paragraphs.append(_clean_line(raw, lineno, changes).strip())
            current = None
            continue
        line = _clean_line(raw, lineno, changes)
        current = line.lstrip() if current is None else _join(current, line, lineno, changes)
    if current is not None:
        paragraphs.append(current)
    text = "\n\n".join(p.strip() for p in paragraphs)
    first_line = lines[0][0] if lines else None
    text = _suspicious(text, first_line, changes)
    return Normalized(text, changes)


def normalize_text(text: str) -> Normalized:
    return normalize_lines([(None, line) for line in text.split("\n")])


def content_skeleton(text: str) -> str:
    """Text without layout: whitespace, hyphens and invisible characters removed."""
    return re.sub(r"[\s\-" + SOFT_HYPHEN + ZERO_WIDTH + "]", "", text)


CONTENT_CHANGING = {"epailyttava_korjaus", "kaksoistunnus"}


def normalization_preserves_content(raw: str, normalized: str, changes: list[NormalizationChange]) -> bool:
    """True if ``normalized`` differs from ``raw`` only by layout and recorded corrections."""
    skeleton = content_skeleton(raw)
    for change in changes:
        if change.kind in CONTENT_CHANGING and change.part == "teksti":
            skeleton = skeleton.replace(content_skeleton(change.raw), content_skeleton(change.normalized), 1)
    return skeleton == content_skeleton(normalized)


# --------------------------------------------------------------------------------------
# Parsing


def is_upper_heading(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 3:
        return False
    return sum(ch.isupper() for ch in letters) / len(letters) >= 0.8


def is_code_token(token: str) -> bool:
    """Letter code as printed in the legend: c-1, km, R(200), E-jv, Mu, sv-1, Saa-2 …"""
    if not CODE_TOKEN.match(token) or token.endswith("-") or token.startswith("-"):
        return False
    letters = [ch for ch in token if ch.isalpha()]
    if not letters or (token.isalpha() and len(token) > 6):
        return False  # a word such as 'Liikkuminen' is a subtitle, not a letter code
    return any(ch.islower() for ch in letters) or "(" in token


def split_code(line: str) -> tuple[str | None, str]:
    """Split a leading letter code off a heading line. The rest keeps its trailing space,
    which tells that the heading continues on the next line."""
    stripped = line.lstrip()
    parts = stripped.split(" ", 1)
    if len(parts) == 2 and is_code_token(parts[0]) and is_upper_heading(parts[1]):
        return parts[0], parts[1].lstrip()
    return None, stripped


def dedupe_code(code: str) -> tuple[str, bool]:
    """``pvpv`` → ``pv``: the PDF repeats symbol-embedded codes."""
    half = len(code) // 2
    if len(code) >= 4 and len(code) % 2 == 0 and code[:half] == code[half:]:
        return code[:half], True
    return code, False


def map_title(line: str) -> tuple[str, str]:
    """``KARTTA 1 - YHDYSKUNTARAKENNE`` → (``1``, ``Kartta 1 - Yhdyskuntarakenne``)."""
    match = MAP_LINE.match(line)
    assert match
    map_id, name = match.group(1), match.group(2).strip()
    return map_id, f"Kartta {map_id}" + (f" - {name.capitalize()}" if name else "")


def parse_source_plans(text: str) -> list[SourcePlan]:
    plans = [SourcePlan(m.group(1).strip(" ,"), m.group(2)) for m in PLAN_WITH_DATE.finditer(text)]
    return plans or ([SourcePlan(text.strip())] if text.strip() else [])


@dataclass
class _Line:
    no: int
    text: str
    kind: str  # blank, space, text, heading, code, general, directive, map, legend, collection


@dataclass
class ParseResult:
    units: list[SourceUnit]
    maps: dict[str, str]  # map title -> map id (ids repeat across collections)
    warnings: list[str] = field(default_factory=list)


class _Parser:
    def __init__(self, text: str):
        self.raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self.units: list[SourceUnit] = []
        self.maps: dict[str, str] = {}
        self.warnings: list[str] = []
        self.page: int | None = None
        self.map_id: str | None = None
        self.map_title: str | None = None
        self.source_plans: list[SourcePlan] = []
        self.section: str | None = None
        self.subsection: str | None = None
        self.geometry: str | None = None
        self.parent: SourceUnit | None = None  # marking whose numbered sub-areas follow
        self.has_pages = any(line.startswith("@sivu") for line in self.raw_lines)
        self.in_legend = not self.has_pages
        self.explicit_map = False
        self.header_lines: list[str] | None = None

    # -- classification -----------------------------------------------------------------

    def classify(self) -> list[_Line]:
        out: list[_Line] = []
        for no, line in enumerate(self.raw_lines, start=1):
            stripped = line.strip()
            if line.startswith("#"):
                continue
            if line.startswith("@"):
                out.append(_Line(no, line, "directive"))
            elif line == "":
                out.append(_Line(no, line, "blank"))
            elif stripped == "":
                out.append(_Line(no, line, "space"))  # column break in the PDF
            elif MAP_LINE.match(line) and is_upper_heading(line):
                out.append(_Line(no, line, "map"))
            elif LEGEND_START.match(line):
                out.append(_Line(no, line, "legend"))
            elif stripped in GENERAL:
                out.append(_Line(no, line, "general"))
            elif COLLECTION_LINE.match(line):
                out.append(_Line(no, line, "collection"))
            elif is_code_token(stripped):
                out.append(_Line(no, line, "code"))
            elif is_upper_heading(split_code(line)[1]):
                out.append(_Line(no, line, "heading"))
            else:
                out.append(_Line(no, line, "text"))
        return out

    # -- main loop ------------------------------------------------------------------------

    def run(self) -> ParseResult:
        lines = self.classify()
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.kind == "directive":
                i = self.directive(lines, i)
                continue
            if line.kind == "collection":
                self.header_lines = []
                i += 1
                continue
            if line.kind == "map":
                map_id, title = map_title(line.text)
                if self.header_lines is not None:
                    plans_text = " ".join(h.strip() for h in self.header_lines)
                    self.source_plans = parse_source_plans(plans_text)
                    self.header_lines = None
                if title != self.map_title:
                    self.map_id, self.map_title = map_id, title
                    self.maps.setdefault(title, map_id)
                    self.section = None
                    self.subsection = None
                if self.has_pages:
                    self.in_legend = True
                i += 1
                continue
            if self.header_lines is not None and line.kind in ("text", "heading") and not self.in_legend:
                self.header_lines.append(line.text)
                if len(self.header_lines) > 4:  # not a page header after all
                    self.header_lines = None
                i += 1
                continue
            if line.kind == "legend":
                if self.header_lines is not None:
                    self.source_plans = parse_source_plans(" ".join(h.strip() for h in self.header_lines))
                    self.header_lines = None
                self.in_legend = True
                i += 1
                continue
            if not self.in_legend or line.kind in ("blank", "space"):
                i += 1
                continue
            if line.kind == "general":
                i = self.general(lines, i + 1, line.no)
                continue
            if line.kind in ("heading", "code"):
                i = self.marking(lines, i)
                continue
            self.warnings.append(
                f"rivi {line.no}: teksti ilman merkintää ohitettiin: {line.text.strip()[:60]}"
            )
            i += 1
        return ParseResult(self.units, self.maps, self.warnings)

    def directive(self, lines: list[_Line], i: int) -> int:
        match = DIRECTIVE.match(lines[i].text)
        if not match:
            self.warnings.append(f"rivi {lines[i].no}: tuntematon ohje {lines[i].text!r}")
            return i + 1
        key, value = match.group(1).lower(), match.group(2)
        if key == "sivu":
            self.page = int(value) if value.isdigit() else None
            # Pages of a PDF extraction start with the page header; after @kartta the text is legend.
            self.in_legend = self.explicit_map
            self.header_lines = None
        elif key == "kartta":
            self.explicit_map = True
            self.map_id, self.map_title = value.split(" ", 1)[0], value
            self.maps.setdefault(value, self.map_id)
            self.section = None
            self.subsection = None
            self.in_legend = True
        elif key == "lahdekaavat":
            self.source_plans = [
                SourcePlan(*(p.strip().rsplit("|", 1) + [None])[:2]) for p in value.split(";")
            ]
        elif key == "osio":
            self.section = value or None
            self.subsection = None
        elif key == "geometria":
            self.geometry = value or None
        elif key == "merkinta":
            lines[i] = _Line(lines[i].no, value, "heading!")
            return self.marking(lines, i)
        elif key == "yleismaarays":
            return self.general(lines, i + 1, lines[i].no, title=value or "")
        elif key == "teksti":
            self.warnings.append(f"rivi {lines[i].no}: @teksti ilman merkintää")
        else:
            self.warnings.append(f"rivi {lines[i].no}: tuntematon ohje @{key}")
        return i + 1

    # -- blocks ---------------------------------------------------------------------------

    def _text_block(self, lines: list[_Line], i: int) -> tuple[list[tuple[int, str]], int]:
        """Collect text lines (and paragraph breaks) until the next structural line."""
        block: list[tuple[int, str]] = []
        while i < len(lines):
            line = lines[i]
            if line.kind == "text":
                block.append((line.no, line.text))
            elif line.kind == "blank":
                block.append((line.no, ""))
            elif line.kind == "space" and block:
                block.append((line.no, line.text))
            elif line.kind == "directive" and line.text.startswith("@teksti"):
                block.append((line.no, line.text[len("@teksti") :].strip()))
            elif line.kind == "map" and map_title(line.text)[1] == self.map_title:
                pass  # repeated page header inside the legend columns
            else:
                break
            i += 1
        while block and block[-1][1].strip() == "":
            block.pop()
        return block, i

    def marking(self, lines: list[_Line], i: int) -> int:
        start = lines[i].no
        code_raw: str | None = None
        heading_parts: list[tuple[int, str]] = []
        if lines[i].kind == "code":
            code_raw = lines[i].text.strip()
            i += 1
            if i >= len(lines) or lines[i].kind not in ("heading", "heading!"):
                self.warnings.append(f"rivi {start}: kirjaintunnus {code_raw!r} ilman otsikkoa")
                return i
        forced = lines[i].kind == "heading!"
        code, rest = split_code(lines[i].text)
        if forced and not code:
            first, _, tail = lines[i].text.strip().partition(" ")
            if (
                tail
                and FORCED_CODE.match(first)
                and (len(first) <= 3 or "-" in first)
                and is_upper_heading(tail)
            ):
                code, rest = first, tail
        if code and not code_raw:
            code_raw = code
        heading_parts.append((lines[i].no, rest if code else lines[i].text))
        i += 1
        while not forced and i < len(lines):
            if lines[i].kind == "space" and i + 1 < len(lines) and lines[i + 1].kind == "heading":
                i += 1  # column break inside a heading
            if lines[i].kind != "heading":
                break
            prev = heading_parts[-1][1]
            if not (prev.endswith((" ", "-", ",")) or prev.rstrip().endswith((",", "-"))):
                break
            if split_code(lines[i].text)[0]:
                break
            heading_parts.append((lines[i].no, lines[i].text))
            i += 1
        heading_norm = normalize_lines(heading_parts)
        for change in heading_norm.changes:
            change.part = "otsikko"
        heading_raw = "\n".join(text for _, text in heading_parts)
        if heading_norm.text in SECTION_HEADINGS and code_raw is None:
            block, j = self._text_block(lines, i)
            if not block:
                self.section = heading_norm.text
                self.subsection = None
                return j
        if heading_norm.text in SUBSECTION_HEADINGS and code_raw is None:
            block, j = self._text_block(lines, i)
            if not block:
                self.subsection = heading_norm.text
                return j
        block, i = self._text_block(lines, i)
        numbered = NUMBERED_HEADING.match(heading_norm.text)
        sub_index = None
        if numbered and self.parent is not None:
            sub_index = numbered.group(1)
            heading_norm = Normalized(heading_norm.text[numbered.end() :], heading_norm.changes)
        unit = self.add_unit("merkinta", heading_raw, heading_norm, code_raw, block, start)
        if sub_index:
            unit.parent_id, unit.sub_index = self.parent.id, sub_index
            unit.section_path = [*unit.section_path, self.parent.heading or ""]
        else:
            self.parent = unit
        return i

    def general(self, lines: list[_Line], i: int, start: int, title: str | None = None) -> int:
        block, i = self._text_block(lines, i)
        title_lines: list[tuple[int, str]] = []
        if title is None:
            # Title = leading lines without a period, the last one followed by a capital letter.
            for k in range(min(3, len(block))):
                text = block[k][1].rstrip()
                if text.endswith(" -") and k + 1 < len(block) and block[k + 1][1][:1].islower():
                    continue  # the title continues on the next line
                if not text or text.endswith((".", "-", ":")):
                    break
                nxt = block[k + 1][1].lstrip() if k + 1 < len(block) else ""
                if nxt[:1].isupper():
                    title_lines = block[: k + 1]
                    block = block[k + 1 :]
                    break
        heading = normalize_lines(title_lines) if title_lines else (normalize_text(title) if title else None)
        for change in heading.changes if heading else []:
            change.part = "otsikko"
        heading_raw = "\n".join(t for _, t in title_lines) if title_lines else (title or None)
        self.add_unit("yleismaarays", heading_raw, heading, None, block, start)
        return i

    def add_unit(self, kind, heading_raw, heading_norm, code_raw, block, start) -> SourceUnit:
        normalized = normalize_lines(block)
        changes = list(normalized.changes)
        if heading_norm:
            changes = [*heading_norm.changes, *changes]
        code = None
        if code_raw:
            code, doubled = dedupe_code(code_raw)
            if doubled:
                changes.insert(
                    0,
                    NormalizationChange(
                        "kaksoistunnus",
                        code_raw,
                        code,
                        start,
                        "kirjaintunnus toistuu poiminnassa",
                        needs_confirmation=True,
                        part="tunnus",
                    ),
                )
        unit = SourceUnit(
            id=f"u{len(self.units) + 1:03d}",
            kind=kind,
            raw_text="\n".join(text for _, text in block),
            normalized_text=normalized.text,
            normalization_diff=changes,
            heading_raw=heading_raw,
            heading=heading_norm.text if heading_norm else None,
            letter_code_raw=code_raw,
            letter_code=code,
            section_path=[x for x in (self.section, self.subsection) if x],
            map=self.map_title,
            page=self.page,
            line=start,
            source_plans=list(self.source_plans),
            geometry_hint=self.geometry,
        )
        self.geometry = None
        for earlier in self.units:
            if (
                earlier.duplicates_of is None
                and earlier.heading == unit.heading
                and earlier.normalized_text == unit.normalized_text
                and earlier.map != unit.map
            ):
                unit.duplicates_of = earlier.id
                break
        self.units.append(unit)
        if kind != "merkinta":
            self.parent = None
        return unit


def parse(text: str) -> ParseResult:
    """Parse the compilation text into source units (all maps)."""
    return _Parser(text).run()


def single_unit(
    heading: str | None,
    text: str,
    *,
    letter_code: str | None = None,
    kind: str = "merkinta",
    unit_id: str = "u001",
    geometry: str | None = None,
) -> SourceUnit:
    """One unit from a heading and a text typed or pasted by the user (QGIS dock, UC2).

    The text is normalized as in :func:`parse` (line breaks inside a paragraph joined, an
    empty line = paragraph break), the raw text is kept and every change is recorded.
    """
    raw = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    normalized = normalize_lines([(n, line) for n, line in enumerate(raw.split("\n"), 1)])
    title = normalize_text(heading.strip()) if heading and heading.strip() else None
    changes = list(normalized.changes)
    if title:
        for change in title.changes:
            change.part = "otsikko"
        changes = [*title.changes, *changes]
    code = (letter_code or "").strip() or None
    return SourceUnit(
        id=unit_id,
        kind=kind,
        raw_text=raw,
        normalized_text=normalized.text,
        normalization_diff=changes,
        heading_raw=heading.strip() if title else None,
        heading=title.text if title else None,
        letter_code_raw=code,
        letter_code=code,
        line=1,
        geometry_hint=geometry,
    )


def select_map(result: ParseResult, wanted: str | None) -> list[SourceUnit]:
    """Units of one map: ``wanted`` is a map id (``1``, ``1a``) or a part of its title."""
    if not wanted:
        return result.units
    key = wanted.strip().lower().removeprefix("kartta").strip()
    titles = [title for title, mid in result.maps.items() if mid.lower() == key]
    if not titles:
        titles = [title for title in result.maps if wanted.lower() in title.lower()]
    if len(titles) != 1:
        found = "; ".join(result.maps) or "ei karttoja"
        raise ValueError(f"Karttaa {wanted!r} ei löydy yksiselitteisesti. Kartat: {found}")
    return [unit for unit in result.units if unit.map == titles[0]]
