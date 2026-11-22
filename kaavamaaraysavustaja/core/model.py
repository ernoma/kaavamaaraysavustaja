"""Intermediate model (välimalli) of a conversion project, plan chapter 6.4.

Standard library dataclasses only. A project is saved as JSON (``*.kma.json``); keys are
English like the code (ADR-0003: machine-written files). Codes are always stored as URIs
together with the code list version (CLAUDE.md rule 3).

Round trip: ``ConversionProject.from_dict(project.to_dict()) == project``.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1
PROJECT_SUFFIX = ".kma.json"

# Enumerations are plain strings (Finnish, as shown to the user) to keep the JSON readable.
PLAN_LEVELS = ("yleiskaava", "asemakaava", "maakuntakaava")
MODES = ("vooka", "laadinta")  # VOOKA = source-faithful conversion (ADR-0007), laadinta = drafting
UNIT_KINDS = ("merkinta", "yleismaarays")
GROUP_KINDS = ("kaavakohde", "yleismaarays", "ei_maarays")
GEOMETRIES = ("alue", "viiva", "piste")
CONFIDENCE = ("korkea", "keskitaso", "matala")
METHODS = ("vakioluettelo", "linjaus", "hyvaksytty", "sanasto", "koodisto", "saanto", "kielimalli", "kayttaja")
STATUSES = ("ehdotus", "muokattu", "hyvaksytty", "hylatty")
SEVERITIES = ("virhe", "varoitus", "huomio")


@dataclass(frozen=True)
class CodeRef:
    """A code as URI plus the version of its code list (e.g. ``2025-10-07``)."""

    uri: str
    codelist_version: str | None = None

    @property
    def value(self) -> str:
        return self.uri.rstrip("/").rsplit("/", 1)[-1]

    @property
    def codelist(self) -> str:
        # http://uri.suomi.fi/codelist/rytj/<codelist>/code/<value>
        parts = self.uri.rstrip("/").split("/")
        return parts[-3] if len(parts) >= 3 and parts[-2] == "code" else ""

    @property
    def codelist_uri(self) -> str:
        return self.uri.rsplit("/code/", 1)[0]


@dataclass
class Value:
    """Typed value of a regulation or additional information (Ryhti ``AttributeValue``).

    ``data_type`` uses the Ryhti/Arho enumeration spelling (``LocalizedText``, ``Code``,
    ``PositiveNumeric``, ``PositiveDecimal`` …).
    """

    data_type: str
    text: dict[str, str] | None = None
    number: float | int | None = None
    unit: str | None = None
    code: CodeRef | None = None
    code_title: dict[str, str] | None = None


@dataclass
class Rationale:
    """Why a part of the proposal is what it is (plan 6.4/6.9)."""

    claim: str
    method: str
    confidence: str
    quote: str | None = None  # verified substring of the unit text
    reference: str | None = None  # e.g. "Katja liite 4 / yleiskaava / rivi 13"


@dataclass
class AdditionalInfo:
    type: CodeRef
    value: Value | None = None


@dataclass
class Regulation:
    key: str
    type: CodeRef
    value: Value | None = None
    additional_infos: list[AdditionalInfo] = field(default_factory=list)
    verbal_types: list[CodeRef] = field(default_factory=list)
    text_span: tuple[int, int] | None = None  # character span in the unit's normalized text
    rationale: list[Rationale] = field(default_factory=list)


@dataclass
class Recommendation:
    key: str
    text: dict[str, str]
    text_span: tuple[int, int] | None = None
    rationale: list[Rationale] = field(default_factory=list)


@dataclass
class QuestionOption:
    id: str
    description: str
    consequence: str = ""


@dataclass
class InterpretationQuestion:
    """Tulkintakysymys (K1–K15). ``resolved_by`` tells how it was settled, if it was."""

    id: str
    kind: str  # K1 … K15
    question: str
    options: list[QuestionOption] = field(default_factory=list)
    recommendation: str | None = None  # option id
    basis: str = ""
    answer: str | None = None  # chosen option id
    resolved_by: str | None = None  # e.g. "linjaus L-03" or "kayttaja"

    @property
    def is_open(self) -> bool:
        return self.answer is None


@dataclass
class RuleResult:
    rule_id: str
    severity: str
    message: str
    target: str = ""  # e.g. "maaraykset[0].lisatiedot[1]"
    source: str = ""
    ryhti_rules: list[str] = field(default_factory=list)


@dataclass
class GroupProposal:
    key: str
    kind: str
    title: dict[str, str] = field(default_factory=dict)
    letter_code: str | None = None
    geometry_types: list[str] = field(default_factory=list)
    category: str | None = None
    group_number: int | None = None
    color_code: str | None = None
    regulations: list[Regulation] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    rationale: list[Rationale] = field(default_factory=list)
    questions: list[InterpretationQuestion] = field(default_factory=list)
    rule_results: list[RuleResult] = field(default_factory=list)
    confidence: str = "matala"
    confidence_basis: str = ""
    status: str = "ehdotus"

    def open_questions(self) -> list[InterpretationQuestion]:
        return [q for q in self.questions if q.is_open]

    def results(self, severity: str) -> list[RuleResult]:
        return [r for r in self.rule_results if r.severity == severity]


@dataclass
class NormalizationChange:
    """One difference between the raw and the normalized text (plan 6.5 step 2)."""

    kind: str  # tavutus, pehmea_tavuviiva, nollaleveä, valilyonti, epailyttava, kaksoistunnus …
    raw: str
    normalized: str
    line: int | None = None  # 1-based line in the input file
    note: str = ""
    needs_confirmation: bool = False


@dataclass
class SourceDocument:
    id: str
    title: str
    file: str | None = None
    sha256: str | None = None
    date: str | None = None


@dataclass
class SourcePlan:
    """A plan combined in the source compilation (kooste), e.g. Kantakaupungin yleiskaava 2040."""

    name: str
    date: str | None = None


@dataclass
class SourceUnit:
    """Määräysyksikkö: a marking with its text, or a general regulation block."""

    id: str
    kind: str
    raw_text: str
    normalized_text: str
    normalization_diff: list[NormalizationChange] = field(default_factory=list)
    heading_raw: str | None = None
    heading: str | None = None
    letter_code_raw: str | None = None
    letter_code: str | None = None
    section_path: list[str] = field(default_factory=list)
    map: str | None = None
    page: int | None = None
    line: int | None = None
    source_plans: list[SourcePlan] = field(default_factory=list)
    geometry_hint: str | None = None
    duplicates_of: str | None = None
    proposal: GroupProposal | None = None


@dataclass
class PolicyChoice:
    """Linjausvalinta (ADR-0008): which option of a policy decision this conversion uses."""

    id: str  # L-01 …
    option: str
    source: str  # oletus | kayttaja | lukittu
    policy_version: int
    title: str = ""
    decision: dict[str, Any] | None = None  # set when the policy is locked


@dataclass
class Decision:
    question_id: str
    unit_id: str
    option: str
    scope: str = "merkinta"  # merkinta | projekti | linjaus
    by: str | None = None
    at: str | None = None
    basis: str = ""


@dataclass
class Provenance:
    step: str  # e.g. saantopohjainen, kielimalli
    tool_version: str
    at: str
    knowledge_version: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Meta:
    plan_level: str = "yleiskaava"
    mode: str = "vooka"
    language: str = "fin"
    title: str = ""
    map: str | None = None
    source_plans: list[SourcePlan] = field(default_factory=list)
    knowledge_version: str = ""
    codelist_versions: dict[str, str] = field(default_factory=dict)
    rules_version: str | None = None
    policy_version: str | None = None
    assistant_version: str = ""


@dataclass
class ConversionProject:
    meta: Meta = field(default_factory=Meta)
    sources: list[SourceDocument] = field(default_factory=list)
    units: list[SourceUnit] = field(default_factory=list)
    policy_choices: list[PolicyChoice] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    format_version: int = FORMAT_VERSION

    # -- convenience ------------------------------------------------------------------

    def policy(self, policy_id: str) -> str | None:
        for choice in self.policy_choices:
            if choice.id == policy_id:
                return choice.option
        return None

    def unit(self, unit_id: str) -> SourceUnit:
        for unit in self.units:
            if unit.id == unit_id:
                return unit
        raise KeyError(unit_id)

    # -- serialization ----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversionProject:
        version = data.get("format_version", FORMAT_VERSION)
        if version > FORMAT_VERSION:
            raise ValueError(f"Muunnosprojektin muoto {version} on uudempi kuin tämä versio tukee ({FORMAT_VERSION})")
        return _from_plain(cls, data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1) + "\n"

    @classmethod
    def from_json(cls, text: str) -> ConversionProject:
        return cls.from_dict(json.loads(text))

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ConversionProject:
        return cls.from_json(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# Generic (de)serialization for the dataclasses above


def _to_plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _to_plain(value) for key, value in obj.items()}
    return obj


_HINTS: dict[type, dict[str, Any]] = {}


def _hints(cls: type) -> dict[str, Any]:
    if cls not in _HINTS:
        _HINTS[cls] = typing.get_type_hints(cls)
    return _HINTS[cls]


def _from_plain(tp: Any, data: Any) -> Any:
    if data is None:
        return None
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        options = [arg for arg in typing.get_args(tp) if arg is not type(None)]
        return _from_plain(options[0], data) if len(options) == 1 else data
    if origin is list:
        (item,) = typing.get_args(tp)
        return [_from_plain(item, value) for value in data]
    if origin is tuple:
        return tuple(data)
    if origin is dict:
        _, item = typing.get_args(tp)
        return {key: _from_plain(item, value) for key, value in data.items()}
    if dataclasses.is_dataclass(tp):
        hints = _hints(tp)
        known = {f.name for f in dataclasses.fields(tp)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"{tp.__name__}: tuntemattomat kentät {sorted(unknown)}")
        return tp(**{name: _from_plain(hints[name], value) for name, value in data.items()})
    return data
