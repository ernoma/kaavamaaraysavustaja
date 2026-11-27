"""The conversion workflow behind the QGIS dock, without QGIS (ADR-0017).

The dock (``plugin/dock.py``) only collects the input, runs these functions in a ``QgsTask``
and shows the results; everything that can be tested without QGIS is here, in the same shape
as the command line (``kma convert``):

* :func:`rule_based` – input (one regulation or a pasted legend) → rule-based project;
  :func:`legend_maps` – the maps of a pasted legend for the map choice
* :func:`policy_options` / :func:`policy_overrides` / :func:`set_policy` – policy choices
* :func:`llm_plan` / :func:`request_preview` – cost estimate and the content to be sent
* :func:`run_llm` – hybrid step with budget, reuse of earlier answers and cancellation
* :func:`decision_for` / :func:`add_decision` / :func:`remove_decision` – the user's answer
  to a question (decision log)
* :func:`export` – project, report, Ryhti JSON and optionally the Arho library; existing files
  are kept unless overwriting is chosen; :func:`suggested_stem` – the file name
* :func:`unit_status` / :func:`detail_html` / :func:`question_view` / :func:`ryhti_view` – what
  the dock shows, in plain language (:func:`plain_text`, feedback round 1, P1-01)
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from kaavamaaraysavustaja.core import decisions as decision_log
from kaavamaaraysavustaja.core.convert import convert_units
from kaavamaaraysavustaja.core.ingest import parse, select_map, single_unit
from kaavamaaraysavustaja.core.llm.providers import DEFAULT_MODELS, SDK, sdk_available
from kaavamaaraysavustaja.core.model import (
    ConversionProject,
    Decision,
    InterpretationQuestion,
    SourceDocument,
    SourceUnit,
)
from kaavamaaraysavustaja.core.policy import IMPLEMENTED, PolicyLibrary
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase

STATUS_ICONS = {
    "valmis": "✔",
    "kysymys": "?",
    "varoitus": "⚠",
    "virhe": "✖",
    "ei_maarays": "–",
    "kasittelyssa": "⏳",
}
STATUS_TEXT = {
    "valmis": "valmis (ei avoimia kysymyksiä, virheitä eikä varoituksia)",
    "kysymys": "avoin tulkintakysymys",
    "varoitus": "sääntövaroitus",
    "virhe": "sääntövirhe",
    "ei_maarays": "ei kaavamääräys (vahvistettava)",
    "kasittelyssa": "käsittelyssä",
}
# Export format -> file name ending; the order is the order of writing (project first).
EXPORT_SUFFIXES = {
    "projekti": ".kma.json",
    "markdown": "_raportti.md",
    "html": "_raportti.html",
    "ryhti": ".ryhti.json",
    "arho": ".arho.yaml",
}
EXPORTS = tuple(EXPORT_SUFFIXES)
USER = "paikkatietoasiantuntija"
MODE_TEXT = {"laadinta": "Uusi määräys (laadinta)", "vooka": "Voimassa oleva määräys (VOOKA)"}
MONTHS = (
    "tammikuu",
    "helmikuu",
    "maaliskuu",
    "huhtikuu",
    "toukokuu",
    "kesäkuu",
    "heinäkuu",
    "elokuu",
    "syyskuu",
    "lokakuu",
    "marraskuu",
    "joulukuu",
)
# The pasted text format (P1-05): shown in the dock and tested to parse as one marking.
LEGEND_EXAMPLE = "c-1 TÄYDENTYVÄ KESKUSTA\nAluetta kehitetään täydennettävänä keskustatoimintojen alueena."
LEGEND_FORMAT = (
    "Kirjoita merkinnän otsikko omalle rivilleen ISOIN KIRJAIMIN ja kirjaintunnus otsikon alkuun "
    "(esim. ”c-1 TÄYDENTYVÄ KESKUSTA”) ja määräysteksti seuraaville riveille. Yhden määräyksen voi "
    "syöttää myös valinnalla ”Yksi määräys”, jolloin otsikko kirjoitetaan omaan kenttäänsä."
)


class InputError(ValueError):
    """The input text cannot be converted (empty, no units, unknown map …)."""


# --------------------------------------------------------------------------------------
# Input and the rule-based conversion


@dataclass
class ConversionRequest:
    text: str
    heading: str | None = None
    letter_code: str | None = None
    kind: str = "merkinta"  # merkinta | yleismaarays (one regulation)
    legend: bool = False  # True = pasted text with one or more markings (ADR-0009 format)
    map: str | None = None  # legend: map title from legend_maps() (or its id / a part of it)
    mode: str = "vooka"
    plan_level: str = "yleiskaava"
    overrides: dict[str, str] = field(default_factory=dict)  # policy choices L-nn → option
    decisions: list[Decision] = field(default_factory=list)
    name: str | None = None


def build_units(request: ConversionRequest) -> tuple[list[SourceUnit], list[str]]:
    """Units of the input and parser warnings."""
    if request.legend:
        result = parse(request.text)
        try:
            units = select_map(result, request.map or None)
        except ValueError as error:
            raise InputError(str(error)) from error
        if not units:
            skipped = f" Ohitetut rivit: {'; '.join(result.warnings[:3])}." if result.warnings else ""
            raise InputError(f"Tekstistä ei löytynyt merkintää eikä yleismääräystä. {LEGEND_FORMAT}{skipped}")
        return units, list(result.warnings)
    if not request.text.strip() and not (request.heading or "").strip():
        raise InputError("Kirjoita tai liitä määräyksen otsikko ja teksti.")
    unit = single_unit(request.heading, request.text, letter_code=request.letter_code, kind=request.kind)
    return [unit], []


def legend_maps(text: str) -> list[str]:
    """Map titles of a pasted text (``@kartta`` lines or ``KARTTA 1 - …`` headings), in order."""
    return list(parse(text).maps)


def map_hint(maps: list[str]) -> str:
    """Why the map choice is shown (P1-02): only when the pasted text has several maps."""
    if len(maps) < 2:
        return ""
    return (
        f"Tekstissä on {len(maps)} karttaa. Valitse muunnettava kartta tai muunna kaikki. Kartan nimi "
        "kirjataan muunnosraporttiin ja Arho-kirjaston kuvaukseen."
    )


def rule_based(kb: KnowledgeBase, request: ConversionRequest) -> ConversionProject:
    units, warnings = build_units(request)
    library = PolicyLibrary.load(kb.directory / kb.manifest["linjaukset"])
    choices = library.resolve(request.overrides)
    data = request.text.encode("utf-8")
    first = units[0]
    name = request.name or (
        request.heading.strip()
        if request.heading and request.heading.strip()
        else (first.map if request.legend and first.map else "Telakan muunnos")
    )
    document = SourceDocument(
        id="s1",
        title="Telakan syöte",
        sha256=hashlib.sha256(data).hexdigest(),
        date=datetime.now(UTC).date().isoformat(),
    )
    maps = list(dict.fromkeys(u.map for u in units if u.map))
    project = convert_units(
        kb,
        units,
        choices,
        plan_level=request.plan_level,
        mode=request.mode,
        name=name,
        source=document,
        map_title=maps[0] if request.legend and len(maps) == 1 else None,
        decisions=request.decisions,
    )
    if warnings:
        project.provenance[0].details["jasennyksen_varoitukset"] = warnings
    return project


def input_warnings(project: ConversionProject) -> list[str]:
    """Lines of the pasted text that the parser skipped (shown to the user, P1-05)."""
    if not project.provenance:
        return []
    return list(project.provenance[0].details.get("jasennyksen_varoitukset") or [])


def summary_text(project: ConversionProject) -> str:
    from kaavamaaraysavustaja.exporters.report import summary

    s = summary(project)
    units = s["yksikoita"]
    open_q = sum(s["avoimet"].values())
    return (
        f"{units} {'yksikkö' if units == 1 else 'yksikköä'}, hyväksyttävissä sellaisenaan "
        f"{s['automaatioehdokkaat']}, avoimia kysymyksiä {open_q}."
    )


# --------------------------------------------------------------------------------------
# Policy choices (ADR-0008, P1-04)


@dataclass(frozen=True)
class PolicyOption:
    id: str
    title: str
    question: str
    options: dict[str, str]  # value -> description (only options the conversion implements)
    default: str
    locked: bool
    basis: str
    explanation: str = ""  # plain language: what the policy decides
    labels: dict[str, str] = field(default_factory=dict)  # value -> short plain name
    effects: dict[str, str] = field(default_factory=dict)  # value -> what choosing it does
    decision: dict[str, Any] | None = None  # locked: who decided and when

    def label(self, value: str) -> str:
        return self.labels.get(value) or value.replace("_", " ")

    def effect(self, value: str) -> str:
        return self.effects.get(value) or self.options.get(value, "")

    @property
    def changeable(self) -> bool:
        return not self.locked and len(self.options) > 1

    @property
    def lock_reason(self) -> str:
        return lock_text(self.decision) if self.locked else ""


def policy_options(kb: KnowledgeBase) -> list[PolicyOption]:
    """Policy choices for the dock: defaults first, locked ones fixed (ADR-0008)."""
    library = PolicyLibrary.load(kb.directory / kb.manifest["linjaukset"])
    out = []
    for policy in library.policies.values():
        implemented = IMPLEMENTED.get(policy.id)
        options = {k: v for k, v in policy.options.items() if implemented is None or k in implemented}
        out.append(
            PolicyOption(
                policy.id,
                policy.title,
                policy.question,
                options,
                policy.default,
                policy.locked,
                policy.basis,
                explanation=policy.explanation,
                labels=dict(policy.labels),
                effects=dict(policy.effects),
                decision=policy.decision,
            )
        )
    return out


def _date_text(value: Any) -> str:
    if isinstance(value, date):
        return f"{value.day}.{value.month}.{value.year}"
    try:
        return _date_text(date.fromisoformat(str(value)))
    except ValueError:
        return str(value or "")


def lock_text(decision: dict[str, Any] | None) -> str:
    """Why a locked policy cannot be changed, in plain language."""
    decision = decision or {}
    when, who = _date_text(decision.get("paivamaara")), decision.get("hyvaksyja")
    text = (
        "Tampere on päättänyt tästä linjauksesta"
        + (f" {when}" if when else "")
        + (f" ({who})" if who else "")
    )
    reason = " ".join(str(decision.get("perustelu") or "").split())
    return f"{text}." + (f" {reason}" if reason else "") + " Lukittua linjausta ei voi muuttaa muunnoksessa."


def policy_overrides(options: list[PolicyOption], selected: dict[str, str]) -> dict[str, str]:
    """Only real changes: a default stays a default ("suositeltu oletus") in the project."""
    out = {}
    for option in options:
        value = selected.get(option.id)
        if value is not None and not option.locked and value != option.default and value in option.options:
            out[option.id] = value
    return out


def set_policy(
    options: list[PolicyOption], overrides: dict[str, str], policy_id: str, value: str
) -> dict[str, str]:
    """A policy changed from a question card: a choice of this conversion (ADR-0008)."""
    option = next((o for o in options if o.id == policy_id), None)
    if option is None:
        raise InputError(f"Tuntematon linjaus {policy_id}.")
    if option.locked:
        raise InputError(f"Linjaus {option.title} on lukittu. {option.lock_reason}")
    if value not in option.options:
        raise InputError(
            f"Linjauksen {option.title} vaihtoehto {value!r} ei ole käytettävissä tässä versiossa."
        )
    result = {k: v for k, v in overrides.items() if k != policy_id}
    if value != option.default:
        result[policy_id] = value
    return result


def policy_summary(options: list[PolicyOption], overrides: dict[str, str]) -> str:
    changed = [o for o in options if overrides.get(o.id) not in (None, o.default)]
    if not changed:
        return "kaikki suositellussa oletuksessa"
    return f"muutettu {len(changed)}: " + ", ".join(
        f"{o.title} ({o.label(overrides[o.id])})" for o in changed
    )


# --------------------------------------------------------------------------------------
# Plain language (P1-01): identifiers only secondary and with a short explanation


@dataclass(frozen=True)
class Glossary:
    """Names behind the identifiers that the core writes into its texts."""

    policies: dict[str, str] = field(default_factory=dict)  # L-06 -> Kirjaintunnukset
    option_labels: dict[str, dict[str, str]] = field(default_factory=dict)  # L-06 -> value -> name
    questions: dict[str, str] = field(default_factory=dict)  # K14 -> Kirjaintunnus
    question_help: dict[str, str] = field(default_factory=dict)  # K14 -> when the question is asked
    rules: dict[str, str] = field(default_factory=dict)  # R-15 -> what the rule checks


def glossary(kb: KnowledgeBase) -> Glossary:
    from kaavamaaraysavustaja.core.llm.prompts import PromptSet

    library = PolicyLibrary.load(kb.directory / kb.manifest["linjaukset"])
    try:
        types = PromptSet.load(kb).question_types
    except (KeyError, ValueError, OSError):
        types = []
    return Glossary(
        policies={p.id: p.title for p in library.policies.values()},
        option_labels={p.id: dict(p.labels) for p in library.policies.values()},
        questions={str(q["tyyppi"]): str(q.get("nimi", "")) for q in types},
        question_help={str(q["tyyppi"]): " ".join(str(q.get("kuvaus", "")).split()) for q in types},
        rules={str(r["tunnus"]): str(r.get("otsikko", "")) for r in (kb.rules or {}).get("saannot", [])},
    )


# References the core stores with its results (provenance), named for the user.
REFERENCES = {
    "Periaate P2": "lähdeuskollisuus",
    "knowledge/org/tampere/linjaukset.yaml": "linjauskirjasto",
    "knowledge/org/tampere/hyvaksytyt.yaml": "hyväksytyt muunnokset",
    "knowledge/katja/annex4_corrections.yaml": "liitteen 4 korjaukset",
    "docs/laaturaportti_liite3.md": "liitteen 3 laaturaportti",
    "docs/kayttoohje.md": "käyttöohje",
}
METHOD_TEXT = {
    "vakioluettelo": "Katja-asetuksen liite 4",
    "linjaus": "linjaus",
    "hyvaksytty": "hyväksytty muunnos",
    "sanasto": "sanasto",
    "koodisto": "koodisto",
    "saanto": "sääntö",
    "kielimalli": "kielimalli",
    "kayttaja": "käyttäjä",
}
_ADR = re.compile(r"(?:\s*[;,]\s*|\s+)?\bADR-\d{4}\b(?:\s*:)?")
_EMPTY_PARENS = re.compile(r"\s*\(\s*\)")
_PHASE = re.compile(r"\(vaihe \d+[a-z]?\)")
_POLICY = re.compile(r"(?P<word>\b[Ll]injaus\s+)?\b(?P<id>L-\d{2})\b(?P<option>:\s*(?P<value>[A-Za-z_]+)\b)?")
_QUESTION = re.compile(
    r"(?:\bsuunnitelma 6\.10 |(?P<word>\b[Tt]ulkintakysymys )|(?<![\w-]))(?P<id>K\d{1,2})\b(?P<colon>:)?"
)
_RULE = re.compile(r"(?:\b[Ss]ääntö\s+)?\b(?P<id>R-\d{2})\b")
_QUESTION_LIST = re.compile(r"\b(?P<word>[Aa]voin tulkintakysymys): (?P<ids>K\d{1,2}(?:, K\d{1,2})*)\b")


def _sentence_start(text: str, index: int) -> bool:
    before = text[:index].rstrip()
    return not before or before.endswith((".", "!", "?", "\n"))


def plain_text(text: str | None, g: Glossary) -> str:
    """Identifiers in texts written by the core, explained (P1-01). Never for source text.

    ``L-06: alkuperaiset`` → ``linjaus Kirjaintunnukset (L-06): lähteen tunnus``,
    ``K14:`` → ``Kirjaintunnus (tulkintakysymys K14):``, ``(R-04)`` → ``(tarkistussääntö
    R-04)``; ADR references are removed and file references named.
    """
    if not text:
        return ""
    for reference, name in REFERENCES.items():
        text = text.replace(reference, name)
    text = _EMPTY_PARENS.sub("", _ADR.sub("", text))
    text = _PHASE.sub("(myöhemmässä versiossa)", text)

    def policy(m: re.Match) -> str:
        title = g.policies.get(m["id"])
        if not title or m.string[: m.start()].endswith(f"{title} ("):  # unknown or explained already
            return m.group()
        word = m["word"] or ""
        capital = word.startswith("L") or (not word and _sentence_start(m.string, m.start()))
        out = f"{'L' if capital else 'l'}injaus {title} ({m['id']})"
        if m["option"]:
            label = g.option_labels.get(m["id"], {}).get(m["value"])
            out += f": {label}" if label else m["option"]
        return out

    def question(m: re.Match) -> str:
        name = g.questions.get(m["id"])
        prefixed = m.group().startswith(("suunnitelma", "tulkintakysymys", "Tulkintakysymys"))
        if not name or not (m["colon"] or prefixed) or m.string[: m.start()].endswith(f"{name} ("):
            return m.group()  # e.g. a letter code K1: only known forms are explained, once
        if m["colon"]:
            return f"{m.group()[: -len(m['id']) - 1]}{name} (tulkintakysymys {m['id']}):"
        word = "Tulkintakysymys" if (m["word"] or "").startswith("T") else "tulkintakysymys"
        return f"{word} {name} ({m['id']})"

    def rule(m: re.Match) -> str:
        if m.string[: m.start()].lower().endswith("tarkistussääntö ") or (g.rules and m["id"] not in g.rules):
            return m.group()
        word = "Tarkistussääntö" if _sentence_start(m.string, m.start()) else "tarkistussääntö"
        return f"{word} {m['id']}"

    def question_list(m: re.Match) -> str:  # "avoin tulkintakysymys: K1, K14" (confidence basis)
        ids = m["ids"].split(", ")
        names = ", ".join(f"{g.questions[i]} ({i})" if g.questions.get(i) else i for i in ids)
        word = m["word"] if len(ids) == 1 else f"{m['word'][0]}voimia tulkintakysymyksiä"
        return f"{word}: {names}"

    text = _POLICY.sub(policy, text)
    text = _QUESTION_LIST.sub(question_list, text)
    text = _QUESTION.sub(question, text)
    text = _RULE.sub(rule, text)
    values = {v: label for labels in g.option_labels.values() for v, label in labels.items() if "_" in v}
    if values:
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(v) for v in sorted(values, key=len, reverse=True)) + r")\b"
        )
        text = pattern.sub(lambda m: f"”{values[m.group()]}”", text)
    return re.sub(r"\s{2,}", " ", text).strip(" ;,")


def knowledge_label(manifest: dict[str, Any]) -> tuple[str, str]:
    """``Koodistot ja säännöt: marraskuu 2026`` and the details (identifiers) for a tooltip."""
    valid = date.fromisoformat(str(manifest["voimassa_alkaen"]))
    prompts = str((manifest.get("kehotteet") or {}).get("hakemisto", ""))
    version = prompts.rsplit("/", 1)[-1].removeprefix("v") if prompts else ""
    text = f"Koodistot ja säännöt: {MONTHS[valid.month - 1]} {valid.year}"
    details = (
        f"Tietopohja {manifest['tietopohja']}, voimassa {_date_text(valid)} alkaen. Tietopohja on "
        "avustajan käyttämä kokonaisuus: koodistot, Katja-asetuksen liite 4, tarkistussäännöt, "
        "linjaukset ja kielimallin ohjeet"
        + (f" (kielimallin ohjeiden eli kehotteen versio {version})" if version else "")
        + ". Tunnus kirjataan muunnosprojektiin ja raporttiin, jotta tuloksen voi toistaa."
    )
    return text, details


def header(kb: KnowledgeBase, mode: str) -> tuple[str, str]:
    """The dock's header line and its tooltip."""
    text, details = knowledge_label(kb.manifest)
    return f"<b>{_e(MODE_TEXT.get(mode, mode))}</b> · {_e(text)} ✓", details


# --------------------------------------------------------------------------------------
# Decisions (ADR-0014)


def decision_for(
    unit: SourceUnit,
    question: InterpretationQuestion,
    option: str,
    *,
    scope: str = "merkinta",
    basis: str = "",
) -> Decision:
    """The user's answer; the unit is identified by heading and letter code for re-runs."""
    if scope not in decision_log.SCOPES:
        raise ValueError(f"laajuus on merkinta tai projekti, saatiin {scope!r}")
    return Decision(
        question_id=question.id,
        unit_id=unit.id,
        option=option,
        scope=scope,
        by=USER,
        at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        basis=basis,
        kind=question.kind,
        heading=unit.heading or "",
        letter_code=unit.letter_code,
    )


def add_decision(decisions: list[Decision], decision: Decision) -> list[Decision]:
    """A newer answer to the same question replaces the older one."""
    return decision_log.merge_decisions(decisions, [decision])


def find_decision(decisions: Iterable[Decision], unit: SourceUnit, kind: str) -> Decision | None:
    """The user's own answer made for this unit (not one made for a similar unit)."""
    return next((d for d in decisions if d.kind == kind and decision_log.targets(d, unit)), None)


def remove_decision(decisions: list[Decision], unit: SourceUnit, kind: str) -> list[Decision]:
    """Remove the user's answer: the question is open again after a re-run (P1-06)."""
    return [d for d in decisions if not (d.kind == kind and decision_log.targets(d, unit))]


def _decision_key(d: Decision) -> tuple:
    return (d.kind, d.heading or "", d.letter_code or "", d.unit_id if not d.heading else "")


def pending_decisions(project: ConversionProject, decisions: Iterable[Decision]) -> int:
    """Saved or removed answers that the project does not show yet (needs a re-run)."""
    applied = {_decision_key(d): (d.option, d.scope) for d in project.decisions}
    wanted = {_decision_key(d): (d.option, d.scope) for d in decisions}
    changed = sum(1 for key, value in wanted.items() if applied.get(key) != value)
    return changed + sum(1 for key in applied if key not in wanted)


# --------------------------------------------------------------------------------------
# Language model (ADR-0013): estimate, preview, run


def llm_unavailable_reason(provider: str, key: str | None) -> str | None:
    """Why the model cannot be used (None = it can). Without it the conversion is rule-based."""
    if provider not in SDK:
        return f"Tuntematon kielimalli {provider!r}."
    if not sdk_available(provider):
        return (
            f"Kielimallin {provider} SDK ({SDK[provider]}) puuttuu: asenna se kma_deps-kansioon "
            "(käyttöohje, luku 1). Muunnos tehdään sääntöpohjaisesti."
        )
    if not key:
        return (
            f"API-avain puuttuu ({provider}): tallenna se kohdassa Avaimet… "
            "(QGISin tunnistetietovarasto). Muunnos tehdään sääntöpohjaisesti."
        )
    return None


@dataclass
class LLMPlan:
    provider: str
    model: str
    estimate: Any  # core.llm.budget.Estimate
    reuse: dict[str, dict[str, Any]]
    prompt_label: str


def llm_plan(
    kb: KnowledgeBase,
    project: ConversionProject,
    provider: str,
    *,
    model: str | None = None,
    previous: ConversionProject | None = None,
) -> LLMPlan:
    """Cost estimate before sending (only units the rule-based step did not settle)."""
    from kaavamaaraysavustaja.core.hybrid import estimate_run, reuse_from_project
    from kaavamaaraysavustaja.core.llm.prompts import PromptSet

    model = model or DEFAULT_MODELS[provider]
    label = PromptSet.load(kb).label
    reuse = reuse_from_project(previous, label) if previous else {}
    estimate = estimate_run(kb, project, model, cached=provider == "claude", reuse=reuse)
    return LLMPlan(provider, model, estimate, reuse, label)


def request_preview(kb: KnowledgeBase, project: ConversionProject, *, reuse: dict | None = None) -> str:
    """Everything that would be sent to the model (plan 6.13: shown on request before sending)."""
    from kaavamaaraysavustaja.core.hybrid import RequestBuilder, plan_units, unit_key
    from kaavamaaraysavustaja.core.llm.prompts import PromptSet

    builder = RequestBuilder(kb, project, PromptSet.load(kb))
    send = [u for u in plan_units(project)[0] if unit_key(u) not in (reuse or {})]
    parts = [
        f"# Kielimallille lähetettävä sisältö ({len(send)} kutsua; kielimallin ohjeet eli kehote "
        f"{builder.prompts.label})",
        "",
        "Vain määräysteksti ja tietopohjasta koottu konteksti; ei PDF:iä, kuvia eikä avaimia.",
        "",
        "## Järjestelmäohje (sama jokaisessa kutsussa)",
        "",
        builder.system,
        "",
        "## Staattinen konteksti (sama jokaisessa kutsussa, välimuistitetaan)",
        "",
        builder.static_context,
    ]
    for unit in send:
        parts += ["", f"## Tehtävä: {unit.id} {unit.heading or ''}".rstrip(), "", builder.task(unit)]
    if not send:
        parts += ["", "(Ei lähetettävää: kaikki yksiköt on ratkaistu tai vastaukset käytetään uudelleen.)"]
    return "\n".join(parts) + "\n"


def run_llm(
    kb: KnowledgeBase,
    project: ConversionProject,
    provider: Any,
    model: str,
    *,
    budget: float | None,
    quality: str = "medium",
    reuse: dict[str, dict[str, Any]] | None = None,
    decisions: list[Decision] | None = None,
    should_stop: Callable[[], bool] | None = None,
    progress: Callable[[str], None] | None = None,
):
    """Hybrid step; mutates ``project`` and returns the ``HybridReport``."""
    from kaavamaaraysavustaja.core.hybrid import HybridSettings, run_hybrid
    from kaavamaaraysavustaja.core.llm.budget import Budget

    settings = HybridSettings(
        provider,
        model,
        Budget(budget),
        quality=quality,
        reuse=dict(reuse or {}),
        progress=progress,
        should_stop=should_stop,
    )
    return run_hybrid(kb, project, settings, decisions or None)


# --------------------------------------------------------------------------------------
# Export and checks


def schema_problems(kb: KnowledgeBase, project: ConversionProject) -> dict[str, list[str]]:
    from kaavamaaraysavustaja.exporters import ryhti_json
    from kaavamaaraysavustaja.validation.schema import SchemaValidatorUnavailable, validate_fragments

    try:
        return validate_fragments(ryhti_json.project_fragments(project), kb.load_schema())
    except SchemaValidatorUnavailable as error:
        return {"skeema": [f"skeemavalidointi ohitettu ({error})"]}


def ryhti_text(project: ConversionProject) -> str:
    """The Ryhti JSON of the whole conversion exactly as the export writes it."""
    from kaavamaaraysavustaja.exporters import ryhti_json

    return json.dumps(ryhti_json.project_fragments(project), ensure_ascii=False, indent=1) + "\n"


def file_stem(text: str) -> str:
    """A safe start of a file name (letters, digits, - and _)."""
    text = re.sub(r"[^0-9A-Za-zÅÄÖåäö_-]+", "_", text.strip()).strip("_")
    return text[:60] or "muunnos"


def suggested_stem(project: ConversionProject) -> str:
    """File name from the first group's title, or its letter code (P1-08)."""
    from kaavamaaraysavustaja.exporters import ryhti_json

    units = ryhti_json.exported_units(project) or [u for u in project.units if u.proposal]
    for unit in units:
        proposal = unit.proposal
        title = (proposal.title or {}).get("fin")
        if title or proposal.letter_code:
            return file_stem(title or proposal.letter_code)
    return "muunnos"


def stem_after_conversion(
    current: str, previous_suggestion: str | None, project: ConversionProject
) -> tuple[str, str]:
    """(file name for the field, the new suggestion): a name typed by the user is kept."""
    suggestion = suggested_stem(project)
    edited = bool(current.strip()) and current.strip() != (previous_suggestion or "")
    return (current if edited else suggestion), suggestion


def export_paths(directory: Path, stem: str, formats: Iterable[str]) -> dict[str, Path]:
    wanted = set(formats)
    return {key: directory / f"{stem}{suffix}" for key, suffix in EXPORT_SUFFIXES.items() if key in wanted}


def existing_exports(directory: Path, stem: str, formats: Iterable[str]) -> list[Path]:
    return [path for path in export_paths(directory, stem, formats).values() if path.exists()]


def free_stem(directory: Path, stem: str, formats: Iterable[str]) -> str:
    """``stem``, or ``stem_2``, ``stem_3`` …: the first with none of the files existing."""
    formats = list(formats)
    if not existing_exports(directory, stem, formats):
        return stem
    number = 2
    while existing_exports(directory, f"{stem}_{number}", formats):
        number += 1
    return f"{stem}_{number}"


@dataclass
class ExportResult:
    paths: dict[str, Path]  # label -> written file
    stem: str  # the start of the file names used
    requested_stem: str
    replaced: list[Path] = field(default_factory=list)  # files overwritten (overwrite=True)

    @property
    def renamed(self) -> bool:
        return self.stem != self.requested_stem


def export(
    kb: KnowledgeBase,
    project: ConversionProject,
    directory: Path,
    stem: str,
    formats: list[str] | tuple[str, ...] = ("projekti", "markdown", "ryhti"),
    *,
    include_incomplete: bool = False,
    overwrite: bool = False,
) -> ExportResult:
    """Write the chosen outputs; the project first.

    Existing files are never replaced unless ``overwrite`` is set: by default a running
    number is added to the file names (``uusi_2.kma.json``, P1-09).
    """
    from kaavamaaraysavustaja.exporters import arho_yaml, report

    unknown = sorted(set(formats) - set(EXPORTS))
    if unknown:
        raise ValueError(f"Tuntemattomat vientimuodot: {', '.join(unknown)}")
    if not formats:
        raise InputError("Valitse vähintään yksi vietävä tiedosto.")
    requested = file_stem(stem)
    directory.mkdir(parents=True, exist_ok=True)
    used = requested if overwrite else free_stem(directory, requested, formats)
    paths = export_paths(directory, used, formats)
    replaced = [path for path in paths.values() if path.exists()]
    if "projekti" in paths:
        project.save(paths["projekti"])
    if "markdown" in paths:
        paths["markdown"].write_text(report.markdown(project, kb), encoding="utf-8")
    if "html" in paths:
        paths["html"].write_text(report.html_text(project, kb), encoding="utf-8")
    if "ryhti" in paths:
        paths["ryhti"].write_text(ryhti_text(project), encoding="utf-8")
    if "arho" in paths:
        library = arho_yaml.library(project, include_incomplete=include_incomplete)
        paths["arho"].write_text(arho_yaml.dumps(library), encoding="utf-8")
    return ExportResult(paths, used, requested, replaced)


@dataclass
class SykeLine:
    unit_id: str
    title: str
    status: str
    findings: list[str]


def syke_validate(
    kb: KnowledgeBase,
    project: ConversionProject,
    key: str,
    *,
    unit_ids: list[str] | None = None,
    limit: int = 5,
    env: str = "test",
    should_stop: Callable[[], bool] | None = None,
) -> list[SykeLine]:
    """Syke public validation API (test environment): one synthetic plan per group (ADR-0011)."""
    from kaavamaaraysavustaja.exporters import ryhti_json
    from kaavamaaraysavustaja.validation.syke_public_api import validate_plan

    units = ryhti_json.exported_units(project)
    if unit_ids:
        units = [u for u in units if u.id in unit_ids]
    lines = []
    for unit in units[:limit]:
        if should_stop and should_stop():
            break
        plan = ryhti_json.synthetic_plan([unit.proposal], name=f"{project.meta.title}/{unit.id}")
        result = validate_plan(plan, key=key, env=env)
        relevant = result.regulation_findings()
        lines.append(
            SykeLine(
                unit.id,
                unit.proposal.title.get("fin", ""),
                "OK" if result.status == 200 else f"HTTP {result.status}",
                [f"{kb.ryhti_message(f.rule) or f.message} (Ryhdin sääntö {f.rule})" for f in relevant],
            )
        )
    return lines


# --------------------------------------------------------------------------------------
# What the dock shows


def unit_status(unit: SourceUnit) -> str:
    p = unit.proposal
    if p is None:
        return "kasittelyssa"
    if p.kind == "ei_maarays":
        return "ei_maarays"
    if p.results("virhe"):
        return "virhe"
    if p.open_questions():
        return "kysymys"
    if p.results("varoitus"):
        return "varoitus"
    return "valmis"


def unit_label(unit: SourceUnit) -> str:
    title = unit.heading or ("Yleismääräys" if unit.kind == "yleismaarays" else unit.id)
    code = f"{unit.letter_code} " if unit.letter_code else ""
    return f"{STATUS_ICONS[unit_status(unit)]} {code}{title}"


def _e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def detail_html(kb: KnowledgeBase, unit: SourceUnit, g: Glossary | None = None) -> str:
    """Proposal in the planner's language, technical view, rationale and rule results (plan 7.1).

    Texts written by the core are shown with :func:`plain_text`; the source text as it is.
    """
    from kaavamaaraysavustaja.exporters.report import KIND, plain_structure

    g = g or glossary(kb)
    p = unit.proposal
    out = [f"<h3>{_e(unit_label(unit))}</h3>"]
    if p is None:
        return "".join(out)
    out.append(
        f"<p><b>{_e(KIND.get(p.kind, p.kind))}</b> · otsikko <b>{_e(p.title.get('fin', '–'))}</b> · "
        f"kirjaintunnus <b>{_e(p.letter_code or '–')}</b> · geometria {_e(', '.join(p.geometry_types) or '–')}<br>"
        f"Varmuus: <b>{_e(p.confidence)}</b> ({_e(plain_text(p.confidence_basis, g))}) · "
        f"tila: {_e(STATUS_TEXT[unit_status(unit)])}</p>"
    )
    out.append("<h4>Rakenne</h4><ul>")
    out += [f"<li>{_e(line)}</li>" for line in plain_structure(kb, p)] or ["<li>–</li>"]
    out.append("</ul>")
    out.append(
        "<h4>Tekninen näkymä</h4><p><small>Koodit ja niiden URIt Ryhdin koodistoissa, samat kuin "
        "Ryhti-JSONissa.</small></p><ul>"
    )
    for reg in p.regulations:
        value = ""
        if reg.value and reg.value.number is not None:
            value = f" = {reg.value.number}{' ' + reg.value.unit if reg.value.unit else ''} ({reg.value.data_type})"
        elif reg.value and reg.value.data_type:
            value = f" ({reg.value.data_type})"
        out.append(f"<li><code>{_e(reg.type.value)}</code>{_e(value)}<br><small>{_e(reg.type.uri)}</small>")
        items = [
            f"lisätieto <code>{_e(i.type.value)}</code>"
            + (f" = <code>{_e(i.value.code.value)}</code>" if i.value and i.value.code else "")
            + f" <small>{_e(i.type.uri)}</small>"
            for i in reg.additional_infos
        ] + [f"laji <code>{_e(v.value)}</code> <small>{_e(v.uri)}</small>" for v in reg.verbal_types]
        if items:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
        out.append("</li>")
    out.append("</ul>")
    rationale = [*p.rationale, *(r for reg in p.regulations for r in reg.rationale)]
    rationale += [r for rec in p.recommendations for r in rec.rationale]
    out.append("<h4>Perustelut</h4><ul>")
    for r in rationale:
        quote = f'<br><i>"{_e(r.quote)}"</i>' if r.quote else ""
        ref = plain_text(r.reference, g)
        source = ", ".join(
            x for x in (METHOD_TEXT.get(r.method, r.method), f"varmuus {r.confidence}", ref) if x
        )
        out.append(f"<li>{_e(plain_text(r.claim, g))} <small>({_e(source)})</small>{quote}</li>")
    out.append("</ul>" if rationale else "<li>–</li></ul>")
    out.append(
        "<h4>Sääntötarkistus</h4><p><small>Virhe estää Ryhdin hyväksynnän, varoitus kannattaa "
        "tarkistaa, huomio on tiedoksi.</small></p><ul>"
    )
    for r in p.rule_results:
        title = g.rules.get(r.rule_id, "")
        name = f"{title} (tarkistussääntö {r.rule_id})" if title else f"tarkistussääntö {r.rule_id}"
        out.append(f"<li><b>{_e(r.severity)}</b> – {_e(name)}: {_e(plain_text(r.message, g))}</li>")
    out.append("</ul>" if p.rule_results else "<li>ei havaintoja</li></ul>")
    if p.model_check:
        c = p.model_check
        out.append(
            f"<p><small>Kielimalli {_e(c.get('malli'))}: yhtäpitävä sääntöpohjaisen kanssa "
            f"{'kyllä' if c.get('yhtapitava') else 'ei'}, hylättyjä lainauksia {_e(c.get('hylattyja_lainauksia'))}."
            "</small></p>"
        )
    out.append("<h4>Lähdeteksti</h4>")
    out.append("<p>" + _e(unit.normalized_text or "(ei tekstiä)").replace("\n\n", "</p><p>") + "</p>")
    pending = [c for c in unit.normalization_diff if c.needs_confirmation]
    if pending:
        out.append(
            "<p><small>Vahvistettavat normalisoinnit: "
            + "; ".join(f"{_e(c.raw)} → {_e(c.normalized)}" for c in pending)
            + "</small></p>"
        )
    return "".join(out)


# -- question card (P1-06) -------------------------------------------------------------------


RESOLVER_TEXT = {
    "avoin": "Avoin kysymys",
    "kayttaja": "Ratkaisija: sinä",
    "kielimalli": "Ratkaisija: kielimalli",
    "linjaus": "Ratkaisija: linjaus",
    "lukittu": "Ratkaisija: lukittu linjaus 🔒",
    "tila": "Ratkaisija: muunnostila",
    "muu": "Ratkaistu",
}


@dataclass(frozen=True)
class QuestionView:
    """A question card: what is asked, who resolved it and how the answer can be changed."""

    id: str
    kind: str
    title: str  # the question, plain language (the list line)
    tooltip: str  # the question type with its identifier (secondary)
    basis: str
    resolver: str  # avoin | kayttaja | kielimalli | linjaus | lukittu | tila | muu
    status: str  # short state for the list line
    answer: str  # the answer in plain language ("" when open)
    explanation: str  # who resolved the question and with what
    how_to_change: str
    editable: bool  # the user can save an own answer in the card
    policy_id: str | None = None
    policy_switchable: bool = False
    policy_choices: tuple[tuple[str, str], ...] = ()  # (value, plain name) for the in-card switch
    policy_value: str | None = None
    own_decision: bool = False  # the user's answer for this unit exists (can be removed)
    pending: str = ""  # a saved answer that a re-run has not applied yet


def question_view(
    kb: KnowledgeBase,
    project: ConversionProject,
    unit: SourceUnit,
    q: InterpretationQuestion,
    *,
    decisions: Iterable[Decision] = (),
    options: list[PolicyOption] | None = None,
    g: Glossary | None = None,
) -> QuestionView:
    g = g or glossary(kb)
    name = g.questions.get(q.kind, "")
    tooltip = f"Tulkintakysymys {q.kind}" + (f" – {name}" if name else "")
    if g.question_help.get(q.kind):
        tooltip += f": {plain_text(g.question_help[q.kind], g)}"
    described = {o.id: o.description for o in q.options}
    answer = described.get(q.answer or "", q.answer or "")
    own = find_decision(list(decisions), unit, q.kind)
    pending = ""
    if own is not None and own.option != q.answer:
        pending = f"Tallennettu ratkaisu {described.get(own.option, own.option)} näkyy, kun ajat muunnoksen uudelleen."
    base = dict(
        id=q.id,
        kind=q.kind,
        title=plain_text(q.question, g),
        tooltip=tooltip,
        basis=plain_text(q.basis, g),
        own_decision=own is not None,
        pending=pending,
    )
    resolved_by = q.resolved_by or ""
    has_options = bool(q.options)
    rerun = "Muutos näkyy ehdotuksessa, kun painat Aja uudelleen ratkaisuin."
    if q.is_open:
        how = (
            f"Valitse vaihtoehto ja laajuus ja paina Tallenna ratkaisu. {rerun}"
            if has_options
            else "Tähän kysymykseen ei ole valmiita vaihtoehtoja: tarkista syöte ja aja muunnos uudelleen."
        )
        return QuestionView(
            **base,
            resolver="avoin",
            status="avoin",
            answer="",
            explanation="Avustaja ei voinut ratkaista tätä varmasti. Sen suositus on valmiiksi valittuna.",
            how_to_change=how,
            editable=has_options,
        )
    if resolved_by.startswith("kayttaja"):
        origin_id = re.search(r"\((u\d+)\)", resolved_by)
        if origin_id:
            origin = next((u for u in project.units if u.id == origin_id.group(1)), None)
            origin_name = (
                " ".join(x for x in (origin.letter_code, origin.heading) if x)
                if origin
                else origin_id.group(1)
            )
            explanation = (
                f"Ratkaisit tämän samankaltaiselle merkinnälle {origin_name} laajuudella ”kaikki "
                f"samankaltaiset”: {answer}."
            )
            how = (
                "Voit tallentaa tälle merkinnälle oman ratkaisun, joka ohittaa samankaltaisen merkinnän "
                f"ratkaisun, tai muuttaa ratkaisua merkinnän {origin_name} kortissa. {rerun}"
            )
        else:
            explanation = f"Ratkaisit tämän itse: {answer}."
            how = f"Omat ratkaisusi ovat aina muutettavissa: valitse toinen vaihtoehto ja tallenna, tai poista ratkaisu. {rerun}"
        return QuestionView(
            **base,
            resolver="kayttaja",
            status="ratkaisit itse",
            answer=answer,
            explanation=explanation,
            how_to_change=how,
            editable=has_options,
        )
    if resolved_by == "kielimalli":
        return QuestionView(
            **base,
            resolver="kielimalli",
            status="kielimalli ratkaisi",
            answer=answer,
            explanation=f"Kielimalli ratkaisi tämän: {answer}.",
            how_to_change=f"Voit korvata ratkaisun omallasi: valitse vaihtoehto ja tallenna. {rerun}",
            editable=has_options,
        )
    if resolved_by.startswith("linjaus"):
        policy_id = resolved_by.split()[-1]
        options = options if options is not None else policy_options(kb)
        option = next((o for o in options if o.id == policy_id), None)
        choice = next((c for c in project.policy_choices if c.id == policy_id), None)
        value = choice.option if choice else q.answer or ""
        title = option.title if option else g.policies.get(policy_id, policy_id)
        label = option.label(value) if option else g.option_labels.get(policy_id, {}).get(value, value)
        what = f"Ratkaistu linjauksella {title}: {label}"
        locked = (choice is not None and choice.source == "lukittu") or (option is not None and option.locked)
        if locked:
            reason = lock_text(
                choice.decision if choice and choice.decision else option.decision if option else None
            )
            return QuestionView(
                **{**base, "answer": label},
                resolver="lukittu",
                status="ratkaistu lukitulla linjauksella",
                explanation=f"{what} (lukittu linjaus).",
                how_to_change=f"{reason} Jos ratkaisu ei sovi, ota yhteys linjauksista vastaavaan.",
                editable=False,
                policy_id=policy_id,
                policy_value=value,
            )
        source = (
            " (valitsit tämän tälle muunnokselle)"
            if choice and choice.source == "kayttaja"
            else " (suositeltu oletus)"
        )
        explanation = f"{what}{source}." + (f" {option.explanation}" if option and option.explanation else "")
        switchable = option is not None and option.changeable
        how = (
            "Linjaus koskee koko muunnosta, ei vain tätä merkintää. Voit vaihtaa sen tästä tai Syöte-välilehden "
            "linjausvalinnoista: valinta tallentuu tämän muunnoksen linjausvalinnaksi, ja muunnos ajetaan uudelleen."
            if switchable
            else "Linjaus koskee koko muunnosta. Siitä on tässä versiossa käytettävissä vain yksi vaihtoehto."
        )
        return QuestionView(
            **{**base, "answer": label},
            resolver="linjaus",
            status="ratkaistu linjauksella",
            explanation=explanation,
            how_to_change=how,
            editable=False,
            policy_id=policy_id,
            policy_switchable=switchable,
            policy_choices=tuple((v, option.label(v)) for v in option.options) if switchable else (),
            policy_value=value,
        )
    if resolved_by.startswith("tila"):
        return QuestionView(
            **base,
            resolver="tila",
            status="ratkaistu tilan mukaan",
            answer=answer,
            explanation=(
                f"Ratkaistu muunnostilan mukaan: voimassa olevan määräyksen teksti säilyy merkki merkiltä, joten {answer.lower()}."
            ),
            how_to_change=(
                "Voimassa olevan määräyksen tekstiä ei muuteta, joten tätä ratkaisua ei voi vaihtaa tässä tilassa. "
                "Jos laadit tekstin uudelleen, valitse Syöte-välilehdellä tila Uusi määräys (laadinta)."
            ),
            editable=False,
        )
    return QuestionView(
        **base,
        resolver="muu",
        status="ratkaistu",
        answer=answer,
        explanation=f"Ratkaistu: {answer}.",
        how_to_change="",
        editable=has_options,
    )


# -- Ryhti JSON view (P1-07) ---------------------------------------------------------------


@dataclass(frozen=True)
class RyhtiView:
    text: str  # JSON as in the exported file ("" when the unit is not exported)
    notes: tuple[str, ...]  # open questions, rule errors, answers waiting for a re-run
    open_questions: int
    included: bool


def _not_exported(unit: SourceUnit) -> str:
    p = unit.proposal
    if p is None:
        return "Yksikköä ei ole vielä muunnettu."
    if p.kind == "ei_maarays":
        return (
            "Avustajan mukaan tämä ei ole kaavamääräys, joten sitä ei viedä Ryhti-JSONiin. Jos se on "
            "määräys, ratkaise tulkintakysymys ja aja muunnos uudelleen."
        )
    if unit.duplicates_of:
        return f"Sama merkintä on jo toisella kartalla ({unit.duplicates_of}), joten se viedään vain kerran."
    if p.status == "hylatty":
        return "Ehdotus on hylätty, joten sitä ei viedä."
    return "Ryhmässä ei ole määräyksiä eikä suosituksia, joten sitä ei viedä."


def ryhti_view(
    project: ConversionProject, unit_id: str | None = None, *, decisions: Iterable[Decision] | None = None
) -> RyhtiView:
    """The Ryhti JSON of one unit or of the whole conversion, made by the exporter (P1-07)."""
    units = project.units if unit_id is None else [project.unit(unit_id)]
    open_here = sum(len(u.proposal.open_questions()) for u in units if u.proposal)
    open_all = sum(len(u.proposal.open_questions()) for u in project.units if u.proposal)
    errors = sum(len(u.proposal.results("virhe")) for u in units if u.proposal)
    notes = []
    if open_all:
        where = f" (tässä yksikössä {open_here})" if unit_id is not None else ""
        notes.append(
            f"Avoimia tulkintakysymyksiä {open_all}{where}: JSON perustuu avustajan suosituksiin, kunnes "
            "ratkaiset kysymykset ja ajat muunnoksen uudelleen."
        )
    else:
        notes.append("Ei avoimia tulkintakysymyksiä.")
    if errors:
        notes.append(
            f"Sääntövirheitä {errors}: Ryhti hylkää ryhmän todennäköisesti, kunnes virhe on korjattu."
        )
    else:  # P2-02: say plainly that nothing blocks Ryhti, and what notes and warnings mean
        warnings = sum(len(u.proposal.results("varoitus")) for u in units if u.proposal)
        remarks = sum(len(u.proposal.results("huomio")) for u in units if u.proposal)
        extra = [f"varoituksia {warnings} (kannattaa tarkistaa)"] if warnings else []
        extra += [f"huomioita {remarks} (tiedoksi, ei korjattavaa)"] if remarks else []
        notes.append(
            "Avustajan tarkistussäännöt: ei virheitä" + (", " + ", ".join(extra) if extra else "") + ". "
            "Ryhdin oman tarkistuksen voit tehdä kohdassa 3 Vienti → Validoi Syken testiympäristössä."
        )
    if decisions is not None:
        waiting = pending_decisions(project, decisions)
        if waiting:
            notes.append(
                f"Tallennettuja ratkaisuja, jotka eivät vielä näy JSONissa: {waiting}. Paina Aja uudelleen ratkaisuin."
            )
    text = ryhti_text(project)
    if unit_id is None:
        notes.append(
            "Sama JSON kuin viedyssä tiedostossa (.ryhti.json): kaavamääräysryhmät ilman kaavan tietoja."
        )
        return RyhtiView(text, tuple(notes), open_here, True)
    whole = json.loads(text)
    unit = units[0]
    key = unit.proposal.key if unit.proposal else None
    groups = whole["planRegulationGroups"] + whole["generalRegulationGroups"]
    group = next(
        (
            x
            for x in groups
            if key and key in (x.get("planRegulationGroupKey"), x.get("generalRegulationGroupKey"))
        ),
        None,
    )
    if group is None:
        return RyhtiView("", (*notes, _not_exported(unit)), open_here, False)
    notes.append("Sama ryhmä kuin viedyssä Ryhti-JSONissa.")
    return RyhtiView(json.dumps(group, ensure_ascii=False, indent=1) + "\n", tuple(notes), open_here, True)
