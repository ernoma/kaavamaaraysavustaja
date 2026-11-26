"""The conversion workflow behind the QGIS dock, without QGIS (ADR-0017).

The dock (``plugin/dock.py``) only collects the input, runs these functions in a ``QgsTask``
and shows the results; everything that can be tested without QGIS is here, in the same shape
as the command line (``kma convert``):

* :func:`rule_based` – input (one regulation or a pasted legend) → rule-based project
* :func:`llm_plan` / :func:`request_preview` – cost estimate and the content to be sent
* :func:`run_llm` – hybrid step with budget, reuse of earlier answers and cancellation
* :func:`decision_for` / :func:`add_decision` – the user's answer to a question (decision log)
* :func:`export` – project, report, Ryhti JSON and optionally the Arho library
* :func:`unit_status` / :func:`detail_html` – what the dock shows for a unit
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
EXPORTS = ("projekti", "markdown", "html", "ryhti", "arho")
USER = "paikkatietoasiantuntija"


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
    legend: bool = False  # True = pasted legend with several markings (ADR-0009 format)
    map: str | None = None  # legend: map id or a part of its title
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
            raise InputError("Selitteestä ei löytynyt yhtään merkintää tai yleismääräystä.")
        return units, list(result.warnings)
    if not request.text.strip() and not (request.heading or "").strip():
        raise InputError("Kirjoita tai liitä määräyksen otsikko ja teksti.")
    unit = single_unit(request.heading, request.text, letter_code=request.letter_code, kind=request.kind)
    return [unit], []


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
    project = convert_units(
        kb,
        units,
        choices,
        plan_level=request.plan_level,
        mode=request.mode,
        name=name,
        source=document,
        map_title=first.map if request.legend and request.map else None,
        decisions=request.decisions,
    )
    if warnings:
        project.provenance[0].details["jasennyksen_varoitukset"] = warnings
    return project


@dataclass(frozen=True)
class PolicyOption:
    id: str
    title: str
    question: str
    options: dict[str, str]  # value -> description (only options the conversion implements)
    default: str
    locked: bool
    basis: str


def policy_options(kb: KnowledgeBase) -> list[PolicyOption]:
    """Policy choices for the dock: defaults first, locked ones fixed (ADR-0008)."""
    library = PolicyLibrary.load(kb.directory / kb.manifest["linjaukset"])
    out = []
    for policy in library.policies.values():
        implemented = IMPLEMENTED.get(policy.id)
        options = {k: v for k, v in policy.options.items() if implemented is None or k in implemented}
        out.append(
            PolicyOption(
                policy.id, policy.title, policy.question, options, policy.default, policy.locked, policy.basis
            )
        )
    return out


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


# --------------------------------------------------------------------------------------
# Language model (ADR-0013): estimate, preview, run


def llm_unavailable_reason(provider: str, key: str | None) -> str | None:
    """Why the model cannot be used (None = it can). Without it the conversion is rule-based."""
    if provider not in SDK:
        return f"Tuntematon kielimalli {provider!r}."
    if not sdk_available(provider):
        return (
            f"Kielimallin {provider} SDK ({SDK[provider]}) puuttuu: asenna se kma_deps-kansioon "
            "(docs/kayttoohje.md). Muunnos tehdään sääntöpohjaisesti."
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
        f"# Kielimallille lähetettävä sisältö ({len(send)} kutsua, kehote {builder.prompts.label})",
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


def export(
    kb: KnowledgeBase,
    project: ConversionProject,
    directory: Path,
    stem: str,
    formats: list[str] | tuple[str, ...] = ("projekti", "markdown", "ryhti"),
    *,
    include_incomplete: bool = False,
) -> dict[str, Path]:
    """Write the chosen outputs; returns label → path. The project is always written first."""
    from kaavamaaraysavustaja.exporters import arho_yaml, report, ryhti_json

    unknown = sorted(set(formats) - set(EXPORTS))
    if unknown:
        raise ValueError(f"Tuntemattomat vientimuodot: {', '.join(unknown)}")
    directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    if "projekti" in formats:
        paths["projekti"] = directory / f"{stem}.kma.json"
        project.save(paths["projekti"])
    if "markdown" in formats:
        paths["markdown"] = directory / f"{stem}_raportti.md"
        paths["markdown"].write_text(report.markdown(project, kb), encoding="utf-8")
    if "html" in formats:
        paths["html"] = directory / f"{stem}_raportti.html"
        paths["html"].write_text(report.html_text(project, kb), encoding="utf-8")
    if "ryhti" in formats:
        paths["ryhti"] = directory / f"{stem}.ryhti.json"
        fragments = ryhti_json.project_fragments(project)
        paths["ryhti"].write_text(
            json.dumps(fragments, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    if "arho" in formats:
        paths["arho"] = directory / f"{stem}.arho.yaml"
        library = arho_yaml.library(project, include_incomplete=include_incomplete)
        paths["arho"].write_text(arho_yaml.dumps(library), encoding="utf-8")
    return paths


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
                [f"{f.rule}: {kb.ryhti_message(f.rule) or f.message}" for f in relevant],
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


def detail_html(kb: KnowledgeBase, unit: SourceUnit) -> str:
    """Proposal in the planner's language, technical view, rationale and rule results (plan 7.1)."""
    from kaavamaaraysavustaja.exporters.report import KIND, plain_structure

    p = unit.proposal
    out = [f"<h3>{_e(unit_label(unit))}</h3>"]
    if p is None:
        return "".join(out)
    out.append(
        f"<p><b>{_e(KIND.get(p.kind, p.kind))}</b> · otsikko <b>{_e(p.title.get('fin', '–'))}</b> · "
        f"kirjaintunnus <b>{_e(p.letter_code or '–')}</b> · geometria {_e(', '.join(p.geometry_types) or '–')}<br>"
        f"Varmuus: <b>{_e(p.confidence)}</b> ({_e(p.confidence_basis)}) · tila: {_e(STATUS_TEXT[unit_status(unit)])}</p>"
    )
    out.append("<h4>Rakenne</h4><ul>")
    out += [f"<li>{_e(line)}</li>" for line in plain_structure(kb, p)] or ["<li>–</li>"]
    for rec in p.recommendations:
        out.append(f'<li>Kaavasuositus: "{_e(rec.text.get("fin", ""))}"</li>')
    out.append("</ul>")
    out.append("<h4>Tekninen näkymä</h4><ul>")
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
        ref = f" – {_e(r.reference)}" if r.reference else ""
        out.append(f"<li>{_e(r.claim)} <small>({_e(r.method)}, {_e(r.confidence)}{ref})</small>{quote}</li>")
    out.append("</ul>" if rationale else "<li>–</li></ul>")
    out.append("<h4>Sääntötarkistus</h4><ul>")
    for r in p.rule_results:
        out.append(f"<li><b>{_e(r.rule_id)} {_e(r.severity)}</b>: {_e(r.message)}</li>")
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
