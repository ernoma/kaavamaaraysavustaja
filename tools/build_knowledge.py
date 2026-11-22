"""Build the knowledge base (tietopohja) into ``knowledge/`` from ``lahtoaineistot/``.

Usage::

    python tools/build_knowledge.py           # (re)build knowledge/ and the quality report
    python tools/build_knowledge.py --check   # fail if committed files differ from a fresh build

Outputs (plan chapter 6.6):

* ``knowledge/codelists/<codelist>/<date>.json`` – koodistot.suomi.fi exports as such
* ``knowledge/codelists/index.json`` – code list index (codes, names, hierarchy, status,
  extension memberships, header-level codes)
* ``knowledge/katja/annex4_katja-ii_393-2025.yaml`` – standard regulation list (Katja annex 4)
  from the LIITE 3 workbook, with ``knowledge/katja/annex4_corrections.yaml`` applied
* ``docs/laaturaportti_liite3.md`` – quality report: LIITE 3 codes checked against code lists
* ``knowledge/ryhti/schema_<release>.json`` – JSON Schema for regulation-related Ryhti schemas
* ``knowledge/ryhti/validation_messages.csv`` – Ryhti validation rules and messages (via Arho)
* ``knowledge/manifest.yaml`` – versions and sha256 checksums

The build is deterministic (no timestamps), so ``--check`` can run in CI. ``openpyxl`` is
needed only here; the runtime core never imports it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE_VERSION = "TP-2026.11-1"
VALID_FROM = "2026-11-22"
RYHTI_RELEASE = "2026-release-11"
ANNEX4_FILE = "katja/annex4_katja-ii_393-2025.yaml"
CORRECTIONS_FILE = "katja/annex4_corrections.yaml"
QUALITY_REPORT = "docs/laaturaportti_liite3.md"
SCHEMA_FILE = f"ryhti/schema_{RYHTI_RELEASE}.json"
MESSAGES_FILE = "ryhti/validation_messages.csv"
INDEX_FILE = "codelists/index.json"

CODELIST_SOURCES = "lahtoaineistot/koodistot/codelist_*.json"
ANNEX_SOURCE = "lahtoaineistot/katja/LIITE 3*.xlsx"
OPENAPI_SOURCE = "lahtoaineistot/ryhti-openapi/planService_openapi.json"
MESSAGES_SOURCE = "lahtoaineistot/arho/validointisaantojen_paluuarvot.csv"
MESSAGES_ORIGIN = {
    "sailo": "https://github.com/GispoCoding/arho-qgis-plugin",
    "polku": "arho_feature_template/resources/configs/validointisaantojen_paluuarvot.csv",
    "commit": "507633d005b4193ccd3a53a1a0f20dc70f41b2b9",
    "haettu": "2026-11-22",
    "lisenssi": "GPL-2.0",
    "komento": (
        "gh api -H 'Accept: application/vnd.github.raw' 'repos/GispoCoding/arho-qgis-plugin/contents/"
        "arho_feature_template/resources/configs/validointisaantojen_paluuarvot.csv"
        "?ref=507633d005b4193ccd3a53a1a0f20dc70f41b2b9'"
    ),
}

URI_PREFIX = "http://uri.suomi.fi/codelist/rytj/"
URI_RE = re.compile(r"^http://uri\.suomi\.fi/codelist/rytj/([^/]+)/code/([^/\s]+)$")
REGULATION_TYPE = "RY_Kaavamaarayslaji"
ADDITIONAL_INFO_TYPE = "RY_Kaavamaarayksen_Lisatiedonlaji"
VERBAL_REGULATION_TYPE = "RY_Sanallisen_Kaavamaarayksen_Laji"
HEADER_MARKER = "otsikkotason koodi"

SHEETS = {"Asemakaava": "asemakaava", "Yleiskaava": "yleiskaava", "Maakuntakaava": "maakuntakaava"}

SCHEMA_ROOTS = [
    "PlanRegulationGroup",
    "PlanRegulation",
    "AdditionalInformation",
    "GeneralRegulationGroup",
    "PlanRecommendation",
    "CodeValue",
    "NumericValue",
    "NumericRange",
    "PositiveNumericValue",
    "PositiveNumericRange",
    "DecimalValue",
    "DecimalRange",
    "PositiveDecimalValue",
    "PositiveDecimalRange",
    "LocalizedTextValue",
    "TextValue",
    "IdentifierValue",
    "SpotElevation",
    "TimePeriodValue",
    "TimePeriodDateOnlyValue",
]
DROPPED_OPENAPI_KEYS = {"discriminator", "example", "examples", "xml", "externalDocs"}

# Finding categories. COUNTED categories are "ristiriitaiset koodiarvot" in the report.
PARSE = "jäsentymätön arvo"
UNKNOWN_CODELIST = "koodisto ei tietopohjassa"
UNKNOWN_CODE = "tuntematon koodi"
WRONG_COLUMN = "väärä sarake"
RETIRED = "poistunut koodi"
HEADER = "otsikkotason koodi"
COUNTED = [PARSE, UNKNOWN_CODELIST, UNKNOWN_CODE, WRONG_COLUMN, RETIRED, HEADER]
WHITESPACE = "ylimääräinen tyhjämerkki"
NOT_IN_EXTENSION = "ei kaavalajin määrityshierarkiassa"
STRUCTURE = "arvo ilman lisätiedon lajia"


# --------------------------------------------------------------------------------------
# Helpers


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def yaml_bytes(data: Any, header: str = "") -> bytes:
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    return (header + text).encode("utf-8")


def single(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"Odotettiin yksi tiedosto kuviolle {pattern!r}, löytyi {len(matches)}")
    return matches[0]


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def lang(values: dict[str, str] | None, languages=("fi", "sv")) -> dict[str, str]:
    values = values or {}
    return {key: values[key] for key in languages if values.get(key)}


# --------------------------------------------------------------------------------------
# a) Code list index


def codelist_version(raw: dict[str, Any]) -> str:
    stamps = [raw.get("modified"), raw.get("contentModified")]
    return max(stamp for stamp in stamps if stamp)[:10]


def build_codelist(raw: dict[str, Any], source_relpath: str) -> dict[str, Any]:
    memberships: dict[str, dict[str, dict[str, str | None]]] = {}
    extensions = {}
    for extension in raw.get("extensions", []):
        name = extension["codeValue"]
        members = extension.get("members", [])
        for member in members:
            memberships.setdefault(member["code"]["codeValue"], {})[name] = {
                "start": member.get("startDate"),
                "end": member.get("endDate"),
            }
        extensions[name] = {
            "uri": extension["uri"],
            "name": lang(extension.get("prefLabel")),
            "status": extension.get("status"),
            "member_count": len(members),
            "ended_member_count": sum(1 for m in members if m.get("endDate")),
        }

    codes = {}
    for code in raw["codes"]:
        value = code["codeValue"]
        description = lang(code.get("description"))
        codes[value] = {
            "uri": code["uri"],
            "name": lang(code.get("prefLabel")),
            "description": description,
            "short_name": code.get("shortName"),
            "parent": (code.get("broaderCode") or {}).get("codeValue"),
            "level": code.get("hierarchyLevel"),
            "order": code.get("order"),
            "status": code["status"],
            "start_date": code.get("startDate"),
            "end_date": code.get("endDate"),
            "header_level": HEADER_MARKER in description.get("fi", "").lower(),
            "memberships": memberships.get(value, {}),
        }
    return {
        "uri": raw["uri"],
        "name": lang(raw.get("prefLabel")),
        "version": codelist_version(raw),
        "source": source_relpath,
        "status": raw.get("status"),
        "extensions": extensions,
        "codes": codes,
    }


# --------------------------------------------------------------------------------------
# b, c) Katja annex 4 (LIITE 3 workbook) and quality report


@dataclass
class Finding:
    sheet: str
    row: int
    column: str
    value: str
    category: str
    message: str
    correction_ids: list[str] = field(default_factory=list)
    resolved: bool = False


def column_kind(header: str) -> str | None:
    if header.startswith("kaavamaarayslaji_koodi"):
        return "type"
    if header.startswith("lisatiedonlajin") and header.endswith("koodiarvo"):
        return "value"
    if header.startswith("lisatiedonlaji_koodi"):
        return "info"
    return None


def additional_info_pairs(headers: list[str]) -> list[tuple[str, str | None]]:
    """Pair lisätiedon laji columns with their value columns (if any)."""
    pairs = []
    for header in headers:
        if column_kind(header) != "info":
            continue
        suffix = header.removeprefix("lisatiedonlaji_koodi")  # "" or "_2"
        number = suffix.lstrip("_")
        value_header = f"lisatiedonlajin_{number}_koodiarvo" if number else "lisatiedonlajin_koodiarvo"
        pairs.append((header, value_header if value_header in headers else None))
    return pairs


class CodeChecker:
    def __init__(self, index: dict[str, Any], openapi_uris: set[str]):
        self.index = index
        self.openapi_uris = openapi_uris

    def check(self, sheet: str, row: int, column: str, value: str) -> list[Finding]:
        kind = column_kind(column)
        extension = SHEETS[sheet]
        match = URI_RE.match(value)

        def finding(category: str, message: str) -> list[Finding]:
            return [Finding(sheet, row, column, value, category, message)]

        if not match:
            return finding(PARSE, "Arvo ei ole koodiston URI-tunnus.")
        codelist, code_value = match.groups()
        if codelist not in self.index:
            note = (
                " Koodi on Ryhdin OpenAPI:n enumeraatiossa."
                if value in self.openapi_uris
                else " Koodia ei löydy myöskään Ryhdin OpenAPI:sta."
            )
            return finding(UNKNOWN_CODELIST, f"Koodistoa {codelist} ei ole tietopohjassa.{note}")
        code = self.index[codelist]["codes"].get(code_value)
        if code is None:
            return finding(UNKNOWN_CODE, f"Koodia {code_value} ei ole koodistossa {codelist}.")
        expected = {"type": [REGULATION_TYPE], "info": [ADDITIONAL_INFO_TYPE]}.get(kind)
        if expected and codelist not in expected:
            return finding(
                WRONG_COLUMN, f"Sarakkeeseen kuuluu koodiston {expected[0]} koodi, nyt {codelist}."
            )
        if kind == "value" and codelist in (ADDITIONAL_INFO_TYPE, VERBAL_REGULATION_TYPE):
            return finding(WRONG_COLUMN, f"Arvosarakkeessa on lisätiedon lajin koodi ({codelist}).")
        if code["status"] != "VALID":
            return finding(RETIRED, f"Koodin tila {code['status']}, päättynyt {code.get('end_date')}.")
        if code["header_level"]:
            return finding(HEADER, "Otsikkotason koodia ei käytetä kaavamääräyksissä.")
        if kind in ("type", "info"):
            membership = code["memberships"].get(extension)
            if membership is None or (membership["end"] and membership["end"] < VALID_FROM):
                ended = f" (jäsenyys päättyi {membership['end']})" if membership else ""
                return finding(NOT_IN_EXTENSION, f"Koodi ei kuulu laajennukseen '{extension}'{ended}.")
        return []


def cell_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value) if not isinstance(value, float) or not value.is_integer() else str(int(value))
    return text if text.strip() else None


def code_ref(value: str, expected: str | None) -> Any:
    match = URI_RE.match(value)
    if not match:
        return {"raaka": value}
    codelist, code = match.groups()
    if codelist == expected:
        return code
    return {"koodisto": codelist, "koodi": code}


def read_annex(path: Path, checker: CodeChecker, corrections: list[dict[str, Any]]):
    import openpyxl  # development-only dependency

    by_cell = {(c["valilehti"], c["rivi"], c["sarake"]): c for c in corrections}
    used_corrections: set[str] = set()
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    annex: dict[str, list[dict[str, Any]]] = {}
    findings: list[Finding] = []
    row_counts: dict[str, int] = {}

    for sheet, plan_level in SHEETS.items():
        rows = list(workbook[sheet].iter_rows(values_only=True))
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        code_columns = [h for h in headers if column_kind(h)]
        entries = []
        count = 0
        for row_number, raw_row in enumerate(rows[1:], start=2):
            cells = {h: cell_text(v) for h, v in zip(headers, raw_row, strict=False) if h}
            if not any(cells.get(h) for h in ["Kaavamääräyksen otsikko", *code_columns]):
                continue
            count += 1
            corrected = dict(cells)
            row_corrections = []
            open_notes = []
            for column in code_columns:
                original = cells.get(column)
                if original is not None and original != original.strip():
                    findings.append(
                        Finding(
                            sheet,
                            row_number,
                            column,
                            original,
                            WHITESPACE,
                            "Arvon alussa tai lopussa on tyhjämerkki; poistettu automaattisesti.",
                            resolved=True,
                        )
                    )
                    original = original.strip()
                    corrected[column] = original
                cell_findings = checker.check(sheet, row_number, column, original) if original else []
                correction = by_cell.get((sheet, row_number, column))
                if correction:
                    if correction["alkuperainen"] != original:
                        raise SystemExit(
                            f"Korjaus {correction['id']}: solun {sheet}!{column}{row_number} arvo on "
                            f"{original!r}, korjaustiedostossa {correction['alkuperainen']!r}"
                        )
                    value = correction["korjattu"]
                    corrected[column] = value
                    used_corrections.add(correction["id"])
                    row_corrections.append(correction["id"])
                    # A correction resolves a finding only if the corrected value passes the check.
                    remaining = checker.check(sheet, row_number, column, value) if value else []
                    remaining_categories = {r.category for r in remaining}
                    for item in cell_findings:
                        item.correction_ids.append(correction["id"])
                        item.resolved = item.category not in remaining_categories
                    for item in remaining:
                        if item.category not in {f.category for f in cell_findings}:
                            item.message += " (korjatussa arvossa)"
                            item.correction_ids.append(correction["id"])
                            cell_findings.append(item)
                    open_counted = [r for r in remaining if r.category in COUNTED]
                else:
                    open_counted = [f for f in cell_findings if f.category in COUNTED]
                findings.extend(cell_findings)
                open_notes += [f"{column}: {f.category} – {f.message}" for f in open_counted]
            for info_column, value_column in additional_info_pairs(headers):
                if value_column and corrected.get(value_column) and not corrected.get(info_column):
                    findings.append(
                        Finding(
                            sheet,
                            row_number,
                            value_column,
                            corrected[value_column],
                            STRUCTURE,
                            "Arvosarakkeessa on arvo, mutta lisätiedon laji puuttuu.",
                        )
                    )

            entry: dict[str, Any] = {
                "rivi": row_number,
                "luokka": cells.get("Luokka"),
                "geometria": (cells.get("Geometria") or "").strip().lower() or None,
                "kirjaintunnus": (cells.get("Esitystavan kirjoitusasu") or "").strip() or None,
                "otsikko": (cells.get("Kaavamääräyksen otsikko") or "").strip() or None,
                "kaavamaarayslajit": [
                    code_ref(corrected[h], REGULATION_TYPE)
                    for h in code_columns
                    if column_kind(h) == "type" and corrected.get(h)
                ],
                "lisatiedot": [],
            }
            for info_column, value_column in additional_info_pairs(headers):
                info = corrected.get(info_column)
                value = corrected.get(value_column) if value_column else None
                if not info and not value:
                    continue
                item: dict[str, Any] = {"laji": code_ref(info, ADDITIONAL_INFO_TYPE) if info else None}
                if value:
                    item["arvo"] = code_ref(value, None)
                entry["lisatiedot"].append(item)
            if cells.get("Kommentti"):
                entry["kommentti"] = cells["Kommentti"].strip()
            if row_corrections:
                entry["korjaukset"] = row_corrections
            if open_notes:
                entry["avoimet_havainnot"] = open_notes
            entries.append(entry)
        annex[plan_level] = entries
        row_counts[sheet] = count

    unused = sorted({c["id"] for c in corrections} - used_corrections)
    if unused:
        raise SystemExit(f"Korjauksia ei voitu kohdistaa mihinkään soluun: {', '.join(unused)}")
    return annex, findings, row_counts


def short(value: str) -> str:
    match = URI_RE.match(value)
    if match:
        codelist, code = match.groups()
        return f"`{code}` ({codelist})" if codelist != REGULATION_TYPE else f"`{code}`"
    return f"`{value}`"


def quality_report(findings: list[Finding], row_counts: dict[str, int], source: str, source_sha: str) -> str:
    lines = [
        "# Laaturaportti: Katja-asetuksen liitteen 4 taulukko (LIITE 3)",
        "",
        "*Generoitu tiedosto (`python tools/build_knowledge.py`), älä muokkaa käsin.*",
        "",
        f"- Lähde: `{source}`",
        f"- Lähteen sha256: `{source_sha}`",
        f"- Tietopohja: {KNOWLEDGE_VERSION} (koodistot ks. `knowledge/manifest.yaml`)",
        f"- Korjaukset: `knowledge/{CORRECTIONS_FILE}` (alkuperäistä taulukkoa ei muokata)",
        f"- Määrityshierarkioiden voimassaolo tarkistettu päivälle {VALID_FROM}",
        "",
        "Taulukon jokainen koodisarake (kaavamääräyslajit, lisätiedon lajit ja lisätietojen",
        "koodiarvot) on tarkistettu koodistoja vasten. **Ristiriitaisiksi koodiarvoiksi** lasketaan:",
        "",
        f"- *{PARSE}*: arvo ei ole koodin URI (esim. selainosoite tai värikoodi)",
        f"- *{UNKNOWN_CODELIST}*: URI viittaa koodistoon, jota tietopohjassa ei ole",
        f"- *{UNKNOWN_CODE}*: koodia ei ole koodistossa",
        f"- *{WRONG_COLUMN}*: koodi on väärän koodiston koodi sarakkeen tarkoitukseen nähden",
        f"- *{RETIRED}*: koodi on poistettu käytöstä",
        f"- *{HEADER}*: koodistoa jäsentävä otsikkotason koodi",
        "",
        f"Huomioina (ei ristiriitoja) raportoidaan *{WHITESPACE}* (korjataan automaattisesti),",
        f"*{NOT_IN_EXTENSION}* (koodi ei kuulu välilehden kaavalajin laajennukseen, vrt. Ryhdin",
        "suositus `rec-codelist-spatialplanregulationtype-plantype-conformity`) ja",
        f"*{STRUCTURE}*.",
        "",
        "## Yhteenveto",
        "",
        "| Välilehti | Rivejä | Ristiriitaiset koodiarvot | Korjattu | Avoinna | Huomioita |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sheet in SHEETS:
        sheet_findings = [f for f in findings if f.sheet == sheet]
        counted = [f for f in sheet_findings if f.category in COUNTED]
        fixed = [f for f in counted if f.resolved]
        notes = [f for f in sheet_findings if f.category not in COUNTED]
        lines.append(
            f"| {sheet} | {row_counts[sheet]} | {len(counted)} | {len(fixed)} | "
            f"{len(counted) - len(fixed)} | {len(notes)} |"
        )
    for sheet in SHEETS:
        sheet_findings = [f for f in findings if f.sheet == sheet]
        counted = [f for f in sheet_findings if f.category in COUNTED]
        lines += ["", f"## {sheet}", ""]
        by_category = Counter(f.category for f in counted)
        if counted:
            summary = ", ".join(f"{category} {n}" for category, n in by_category.items())
            lines += [f"Ristiriitaiset koodiarvot: {len(counted)} ({summary}).", ""]
            lines += ["| Rivi | Sarake | Arvo | Luokka | Selitys | Korjaus |", "|---:|---|---|---|---|---|"]
            for f in counted:
                fix = ", ".join(f.correction_ids) if f.correction_ids else "–"
                state = "korjattu" if f.resolved else "**avoinna**"
                lines.append(
                    f"| {f.row} | {f.column} | {short(f.value)} | {f.category} | {f.message} | {fix} ({state}) |"
                )
        else:
            lines.append("Ei ristiriitaisia koodiarvoja.")
        notes = [f for f in sheet_findings if f.category not in COUNTED]
        if notes:
            lines += [
                "",
                f"### Huomiot ({sheet})",
                "",
                "| Rivi | Sarake | Arvo | Huomio | Selitys |",
                "|---:|---|---|---|---|",
            ]
            for f in notes:
                lines.append(
                    f"| {f.row} | {f.column} | {short(f.value.strip())} | {f.category} | {f.message} |"
                )
    lines += [
        "",
        "## Tarkistukset, joita rakentaja ei tee",
        "",
        "- **Semanttinen vastaavuus**: koodi voi olla voimassa ja oikeassa sarakkeessa, mutta",
        "  vastata otsikkoa huonosti (esim. suunnitelmassa mainittu *LV Venesatama → kanava*).",
        "  Nämä tarkistetaan käsin linjauspalavereissa ja kirjataan korjaustiedostoon.",
        "- **Esitystavan tyylitiedot** (värit, viivat, fontit) eivät kuulu vakiomääräysluetteloon.",
        "- Koodiston `oikeusvaik_YK` arvot (esim. 11 ja 12 lisätiedolla *rakennusluvanPeruste*)",
        "  löytyvät Ryhdin OpenAPI:n enumeraatiosta ja vastaavat oppaan alaviitettä 12; ne",
        "  merkitään avoimiksi, kunnes koodisto lisätään tietopohjaan (vaihe 1).",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# d) Ryhti OpenAPI -> JSON Schema


def schema_refs(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for value in node.values():
            found |= schema_refs(value)
    elif isinstance(node, list):
        for value in node:
            found |= schema_refs(value)
    return found


def convert_schema(node: Any) -> Any:
    """Convert an OpenAPI 3.0 schema object to JSON Schema 2020-12."""
    if isinstance(node, list):
        return [convert_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {k: v for k, v in node.items() if k not in DROPPED_OPENAPI_KEYS}
    # Value classes inherit the abstract AttributeValue (additionalProperties: false) via
    # allOf; combined with their own properties that would reject every valid value.
    if "allOf" in node and "properties" in node:
        node["allOf"] = [
            part for part in node["allOf"] if part.get("$ref") != "#/components/schemas/AttributeValue"
        ]
        if not node["allOf"]:
            del node["allOf"]
    nullable = node.pop("nullable", False)
    result = {}
    for key, value in node.items():
        if key == "$ref":
            result[key] = value.replace("#/components/schemas/", "#/$defs/")
        elif key in ("properties", "patternProperties", "$defs"):
            result[key] = {name: convert_schema(sub) for name, sub in value.items()}
        else:
            result[key] = convert_schema(value)
    if nullable:
        if isinstance(result.get("type"), str):
            result["type"] = [result["type"], "null"]
            if "enum" in result:
                result["enum"] = [*result["enum"], None]
        else:
            annotations = {k: result.pop(k) for k in ("description", "readOnly") if k in result}
            result = {"anyOf": [result, {"type": "null"}], **annotations}
    return result


def build_schema(openapi: dict[str, Any], source: str, source_sha: str) -> dict[str, Any]:
    schemas = openapi["components"]["schemas"]
    wanted: set[str] = set()
    pending = list(SCHEMA_ROOTS)
    while pending:
        name = pending.pop()
        if name in wanted:
            continue
        wanted.add(name)
        pending.extend(schema_refs(schemas[name]) - wanted)
    defs = {name: convert_schema(copy.deepcopy(schemas[name])) for name in sorted(wanted)}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://github.com/ernoma/kaavamaaraysavustaja/knowledge/{SCHEMA_FILE}",
        "title": "Ryhti planService: kaavamääräyksiin liittyvät skeemat",
        "$comment": (
            f"Generoitu tiedostosta {source} (sha256 {source_sha}, OpenAPI {openapi.get('openapi')}, "
            f"info.version {openapi['info'].get('version')}) työkalulla tools/build_knowledge.py. "
            "Juuriskeemat: " + ", ".join(SCHEMA_ROOTS) + ". Viittaa muotoon #/$defs/<Nimi>."
        ),
        "$defs": defs,
    }


def openapi_code_uris(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "enum" and isinstance(value, list):
                found |= {v for v in value if isinstance(v, str) and v.startswith(URI_PREFIX)}
            else:
                found |= openapi_code_uris(value)
    elif isinstance(node, list):
        for value in node:
            found |= openapi_code_uris(value)
    return found


# --------------------------------------------------------------------------------------
# Build


@dataclass
class BuildResult:
    files: dict[str, bytes]  # path relative to the repository root -> content
    findings: list[Finding]
    row_counts: dict[str, int]


def build(root: Path = ROOT) -> BuildResult:
    files: dict[str, bytes] = {}
    sources: dict[str, str] = {}
    knowledge = "knowledge/"

    # a) code lists
    index: dict[str, Any] = {"format_version": 1, "tietopohja": KNOWLEDGE_VERSION, "codelists": {}}
    codelist_manifest = {}
    for path in sorted(root.glob(CODELIST_SOURCES)):
        data = path.read_bytes()
        sources[rel(root, path)] = sha256_bytes(data)
        raw = json.loads(data)
        name = raw["codeValue"]
        target = f"codelists/{name}/{codelist_version(raw)}.json"
        files[knowledge + target] = data
        index["codelists"][name] = build_codelist(raw, target)
        codelist_manifest[name] = {"versio": codelist_version(raw), "tiedosto": target, "uri": raw["uri"]}
    files[knowledge + INDEX_FILE] = json_bytes(index)

    # d) OpenAPI -> JSON Schema (also used to recognise code lists not in the knowledge base)
    openapi_path = root / OPENAPI_SOURCE
    openapi_data = openapi_path.read_bytes()
    sources[OPENAPI_SOURCE] = sha256_bytes(openapi_data)
    openapi = json.loads(openapi_data)
    files[knowledge + SCHEMA_FILE] = json_bytes(
        build_schema(openapi, OPENAPI_SOURCE, sources[OPENAPI_SOURCE])
    )

    # b, c) annex 4 + quality report
    corrections_path = root / knowledge / CORRECTIONS_FILE
    corrections_data = corrections_path.read_bytes()
    corrections = yaml.safe_load(corrections_data)["korjaukset"]
    files[knowledge + CORRECTIONS_FILE] = corrections_data
    annex_path = single(root, ANNEX_SOURCE)
    annex_source = rel(root, annex_path)
    sources[annex_source] = sha256_bytes(annex_path.read_bytes())
    checker = CodeChecker(index["codelists"], openapi_code_uris(openapi))
    annex, findings, row_counts = read_annex(annex_path, checker, corrections)
    annex_doc = {
        "tietopohja": KNOWLEDGE_VERSION,
        "katja": {"asetus": "311/2024", "muutokset": ["393/2025"], "liite": 4},
        "lahde": {"tiedosto": annex_source, "sha256": sources[annex_source]},
        "korjaukset": CORRECTIONS_FILE,
        "laaturaportti": QUALITY_REPORT,
        "kaavalajit": annex,
    }
    header = (
        "# Katja-asetuksen liitteen 4 vakiomääräysluettelo (generoitu, älä muokkaa käsin).\n"
        "# Rakentaja: tools/build_knowledge.py; korjaukset: knowledge/katja/annex4_corrections.yaml\n"
        "# Koodit ovat koodiarvoja (codeValue); muun koodiston arvo on muodossa {koodisto, koodi}.\n"
    )
    files[knowledge + ANNEX4_FILE] = yaml_bytes(annex_doc, header)
    files[QUALITY_REPORT] = quality_report(findings, row_counts, annex_source, sources[annex_source]).encode(
        "utf-8"
    )

    # e) validation messages (copied as such from Arho)
    messages = (root / MESSAGES_SOURCE).read_bytes()
    sources[MESSAGES_SOURCE] = sha256_bytes(messages)
    files[knowledge + MESSAGES_FILE] = messages

    # f) manifest
    manifest = {
        "tietopohja": KNOWLEDGE_VERSION,
        "voimassa_alkaen": VALID_FROM,
        "rakentaja": "tools/build_knowledge.py",
        "katja": {
            "asetus": "311/2024",
            "muutokset": ["393/2025"],
            "liite4": ANNEX4_FILE,
            "korjaukset": CORRECTIONS_FILE,
            "laaturaportti": QUALITY_REPORT,
        },
        "opas": {"versio": "luonnos 16.2.2026"},
        "koodistot": codelist_manifest,
        "koodistoindeksi": INDEX_FILE,
        "ryhti": {
            "julkaisu": RYHTI_RELEASE,
            "skeema": SCHEMA_FILE,
            "validointiviestit": MESSAGES_FILE,
            "validointiviestien_lahde": MESSAGES_ORIGIN,
        },
        "saannot": None,
        "kehotteet": None,
        "linjaukset": None,
        "lahteet": dict(sorted(sources.items())),
        "tiedostot": {
            path.removeprefix(knowledge): sha256_bytes(content)
            for path, content in sorted(files.items())
            if path.startswith(knowledge)
        },
    }
    manifest_header = (
        "# Tietopohjan manifesti (generoitu: python tools/build_knowledge.py).\n"
        "# 'tiedostot' = knowledge/-kansion tiedostot tarkistussummineen (eheystarkistus),\n"
        "# 'lahteet' = lähdeaineistot, joista tietopohja on rakennettu.\n"
        "# saannot, kehotteet ja linjaukset lisätään vaiheissa 1-2.\n"
    )
    files[knowledge + "manifest.yaml"] = yaml_bytes(manifest, manifest_header)
    return BuildResult(files, findings, row_counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="vertaa säilön tiedostoja uuteen rakennukseen")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = build(args.root)
    if args.check:
        stale = [
            p
            for p, c in result.files.items()
            if not (args.root / p).exists() or (args.root / p).read_bytes() != c
        ]
        if stale:
            print("Tietopohja ei ole ajan tasalla, aja python tools/build_knowledge.py:", *stale, sep="\n  ")
            return 1
        print(f"Tietopohja {KNOWLEDGE_VERSION} on ajan tasalla ({len(result.files)} tiedostoa).")
        return 0
    for path, content in result.files.items():
        target = args.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != content:
            target.write_bytes(content)
            print("kirjoitettu", path)
    counted = Counter(f.sheet for f in result.findings if f.category in COUNTED)
    print(f"Tietopohja {KNOWLEDGE_VERSION}: ristiriitaiset koodiarvot {dict(counted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
