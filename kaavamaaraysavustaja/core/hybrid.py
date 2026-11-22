"""Hybrid conversion: rule-based → language model → rule engine (plan 6.5 step 5, 6.9, ADR-0013).

Only units the rule-based step did not settle with high confidence go to the model
(:func:`needs_model`). The model gets the phase 1 findings, the open questions, the resolved
items and the policy choices. Its answer is checked before use:

* the verbal text always comes from the source (VOOKA, R-19 is absolute): the model only
  classifies it (verbal regulation types), it never supplies the text;
* every quote must be a substring of the unit's heading or text, otherwise the rationale is
  rejected and the confidence is low;
* the rule engine is run on the result; high confidence requires that the model agrees with
  the rule-based structure, all quotes are found and there are no rule errors, warnings or open
  questions (plan 6.9).

Model questions are merged into the rule-based ones without duplicates (same question type =
same question). A question type marked ``mallin_ratkaistavissa`` may be settled by the model.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kaavamaaraysavustaja import __version__ as ASSISTANT_VERSION
from kaavamaaraysavustaja.core import decisions as decision_log
from kaavamaaraysavustaja.core.convert import (
    VERBAL_TYPES,
    Context,
    Structure,
    apply_title_policy,
    letter_code_for,
    overall_confidence,
    policy_question,
    regulation_from_codes,
)
from kaavamaaraysavustaja.core.evaluation import structure_of
from kaavamaaraysavustaja.core.llm.base import LLMError, StructuredRequest, Usage
from kaavamaaraysavustaja.core.llm.budget import Budget, Estimate, Pricing, estimate
from kaavamaaraysavustaja.core.llm.prompts import PromptSet
from kaavamaaraysavustaja.core.llm.schema import conversion_schema
from kaavamaaraysavustaja.core.model import (
    ConversionProject,
    GroupProposal,
    InterpretationQuestion,
    Provenance,
    QuestionOption,
    Rationale,
    Regulation,
    SourceUnit,
)
from kaavamaaraysavustaja.core.policy import PolicyLibrary
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase
from kaavamaaraysavustaja.knowledge.codelists import (
    ADDITIONAL_INFO_TYPE,
    REGULATION_TYPE,
    VERBAL_REGULATION_TYPE,
)

GEOMETRIES = ("alue", "viiva", "piste")
QUOTE_STRIP = " \t\n\"'“”„«»…."


# --------------------------------------------------------------------------------------
# Selection and keys


def needs_model(unit: SourceUnit) -> bool:
    """Units the rule-based step did not settle with high confidence (informative markings stay with the user)."""
    proposal = unit.proposal
    return bool(proposal and proposal.kind != "ei_maarays" and proposal.confidence != "korkea")


def unit_key(unit: SourceUnit) -> str:
    """Stable key of a unit's content (for replay and re-runs; not the unit id)."""
    raw = json.dumps(
        [unit.kind, unit.heading, unit.letter_code, unit.normalized_text, unit.geometry_hint],
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------------------
# Quotes


def _collapse(text: str) -> str:
    return " ".join(text.split())


def quote_found(quote: str | None, unit: SourceUnit) -> bool:
    """A quote must be a substring of the heading or text (whitespace collapsed). Empty = no quote."""
    if not quote or not quote.strip(QUOTE_STRIP):
        return True
    needle = _collapse(quote.strip(QUOTE_STRIP)).casefold()
    haystacks = [
        unit.normalized_text or "",
        unit.heading or "",
        f"{unit.letter_code or ''} {unit.heading or ''}",
    ]
    return any(needle in _collapse(h).casefold() for h in haystacks)


# --------------------------------------------------------------------------------------
# Settings and results


@dataclass
class HybridSettings:
    provider: Any  # LLMProvider
    model: str
    budget: Budget
    quality: str = "medium"
    reuse: dict[str, dict[str, Any]] = field(default_factory=dict)  # unit key -> earlier response
    progress: Callable[[str], None] | None = None


@dataclass
class UnitOutcome:
    unit_id: str
    key: str
    status: str  # kielimalli | uudelleenkaytetty | ohitettu_budjetti | virhe
    usage: Usage = field(default_factory=Usage)
    cost: float = 0.0
    seconds: float = 0.0
    agreement: bool | None = None
    rejected_quotes: int = 0
    message: str = ""
    response: dict[str, Any] | None = None
    model: str = ""


@dataclass
class HybridReport:
    outcomes: list[UnitOutcome] = field(default_factory=list)
    estimate: Estimate | None = None

    def totals(self) -> dict[str, Any]:
        called = [o for o in self.outcomes if o.status == "kielimalli"]
        tokens = {
            "syote": sum(o.usage.input_tokens for o in called),
            "tuloste": sum(o.usage.output_tokens for o in called),
            "valimuisti_luku": sum(o.usage.cache_read_input_tokens for o in called),
            "valimuisti_kirjoitus": sum(o.usage.cache_creation_input_tokens for o in called),
        }
        return {
            "kasiteltyja": len(self.outcomes),
            "kutsuja": len(called),
            "uudelleenkaytettyja": sum(o.status == "uudelleenkaytetty" for o in self.outcomes),
            "budjetin_takia_ohitettuja": sum(o.status == "ohitettu_budjetti" for o in self.outcomes),
            "virheita": sum(o.status == "virhe" for o in self.outcomes),
            "tokenit": tokens,
            "kustannus_usd": round(sum(o.cost for o in self.outcomes), 4),
            "kesto_s": round(sum(o.seconds for o in called), 1),
            "yhtapitavia": sum(bool(o.agreement) for o in self.outcomes),
            "hylattyja_lainauksia": sum(o.rejected_quotes for o in self.outcomes),
        }


# --------------------------------------------------------------------------------------
# Requests


class RequestBuilder:
    def __init__(self, kb: KnowledgeBase, project: ConversionProject, prompts: PromptSet):
        self.kb = kb
        self.project = project
        self.prompts = prompts
        plan_level, mode = project.meta.plan_level, project.meta.mode
        self.schema = conversion_schema(kb.index, plan_level, kb.valid_on)
        self.static_context = prompts.static_context(kb, plan_level, mode, project.policy_choices)

    def resolved_items(self, unit: SourceUnit) -> list[dict[str, str]]:
        proposal = unit.proposal
        return (
            [decision_log.resolved_for_model(q) for q in proposal.questions if not q.is_open]
            if proposal
            else []
        )

    def task(self, unit: SourceUnit) -> str:
        return self.prompts.task_input(self.kb, unit, unit.proposal, self.resolved_items(unit))

    def request(self, unit: SourceUnit, quality: str) -> StructuredRequest:
        return StructuredRequest(
            system=self.prompts.system,
            static_context=self.static_context,
            task_input=self.task(unit),
            json_schema=self.schema,
            quality=quality,  # type: ignore[arg-type]
            metadata={
                "avain": unit_key(unit),
                "yksikko": unit.id,
                "otsikko": unit.heading or "",
                "kehote": self.prompts.label,
                "tietopohja": self.kb.version,
            },
        )


def plan_units(project: ConversionProject) -> tuple[list[SourceUnit], dict[str, SourceUnit]]:
    """Units to send and duplicates resolved through their original (same key, one call)."""
    send: list[SourceUnit] = []
    by_key: dict[str, SourceUnit] = {}
    duplicates: dict[str, SourceUnit] = {}
    for unit in project.units:
        if not needs_model(unit):
            continue
        key = unit_key(unit)
        if key in by_key:
            duplicates[unit.id] = by_key[key]
            continue
        by_key[key] = unit
        send.append(unit)
    return send, duplicates


def estimate_run(
    kb: KnowledgeBase,
    project: ConversionProject,
    model: str,
    *,
    cached: bool,
    reuse: dict[str, dict[str, Any]] | None = None,
) -> Estimate:
    prompts = PromptSet.load(kb)
    builder = RequestBuilder(kb, project, prompts)
    send, _ = plan_units(project)
    send = [u for u in send if unit_key(u) not in (reuse or {})]
    tasks = [builder.task(u) for u in send]
    return estimate(
        Pricing.load(kb),
        model,
        prompts.system + builder.static_context,
        tasks,
        cached=cached,
        schema_text=json.dumps(builder.schema, ensure_ascii=False),
    )


# --------------------------------------------------------------------------------------
# Mapping the model answer to a proposal


def _verbal_types(kb: KnowledgeBase, values: list[str]) -> list[str]:
    seen = []
    for value in values:
        code = kb.index.get(VERBAL_REGULATION_TYPE, value)
        if code and code.is_valid and not code.header_level and value not in seen:
            seen.append(value)
    return seen


def _usable(kb: KnowledgeBase, codelist: str, value: str | None) -> bool:
    code = kb.index.get(codelist, value or "")
    return bool(code and code.is_valid and not code.header_level)


def proposal_from_model(
    ctx: Context,
    unit: SourceUnit,
    rule_proposal: GroupProposal,
    data: dict[str, Any],
    prompts: PromptSet,
) -> tuple[GroupProposal, int, bool]:
    """Build the hybrid proposal. Returns (proposal, rejected quotes, agreement with the rules)."""
    kb = ctx.kb
    groups = [g for g in data.get("ryhmat", []) if isinstance(g, dict)]
    group = groups[0] if groups else {}
    proposal = GroupProposal(
        key=rule_proposal.key,
        kind=rule_proposal.kind,
        title=dict(rule_proposal.title),
        category=rule_proposal.category,
    )
    rationale: list[Rationale] = []
    rejected = 0

    def add_rationale(claim: str, quote: str | None, reference: str, confidence: str) -> None:
        nonlocal rejected
        if quote_found(quote, unit):
            rationale.append(
                Rationale(
                    claim,
                    "kielimalli",
                    confidence,
                    quote=(quote or "").strip(QUOTE_STRIP) or None,
                    reference=reference,
                )
            )
        else:
            rejected += 1
            rationale.append(
                Rationale(
                    f"Hylätty perustelu (lainaus ei löydy lähdetekstistä): {claim} [lainaus: {quote}]",
                    "kielimalli",
                    "matala",
                    reference=reference,
                )
            )

    # -- non-verbal regulations ------------------------------------------------------
    regulations: list[Regulation] = []
    model_verbal: list[str] = []
    model_verbal_type: str | None = None
    texts: list[str] = []
    for n, item in enumerate(group.get("maaraykset", []) or []):
        laji = item.get("laji")
        if laji in VERBAL_TYPES:
            model_verbal += item.get("sanallisen_lajit", []) or []
            model_verbal_type = model_verbal_type or laji
            if item.get("arvo"):
                texts.append(str(item["arvo"]))
            for quote in item.get("tekstiviitteet", []) or []:
                if not quote_found(quote, unit):
                    rejected += 1
            continue
        if not _usable(kb, REGULATION_TYPE, laji):
            rationale.append(
                Rationale(
                    f"Kielimallin koodi {laji!r} ei ole käytettävissä; ohitettu.", "kielimalli", "matala"
                )
            )
            continue
        infos = []
        for info in item.get("lisatiedot", []) or []:
            info_type = info.get("laji")
            if not _usable(kb, ADDITIONAL_INFO_TYPE, info_type):
                rationale.append(
                    Rationale(
                        f"Kielimallin lisätieto {info_type!r} ei ole käytettävissä; ohitettu.",
                        "kielimalli",
                        "matala",
                    )
                )
                continue
            value = info.get("arvo")
            if value and _usable(kb, REGULATION_TYPE, value):
                infos.append((ADDITIONAL_INFO_TYPE, info_type, (REGULATION_TYPE, value)))
            else:
                if value:
                    rationale.append(
                        Rationale(
                            f"Lisätiedon {info_type} arvo {value!r} ei ole kaavamääräyslaji; arvo ohitettu.",
                            "kielimalli",
                            "matala",
                        )
                    )
                infos.append((ADDITIONAL_INFO_TYPE, info_type, None))
        regulation = regulation_from_codes(ctx, unit, len(regulations), laji, infos)
        regulation.key = ctx.key(unit.id, f"k{n}")
        for quote in item.get("tekstiviitteet", []) or []:
            if not quote_found(quote, unit):
                rejected += 1
                rationale.append(
                    Rationale(f"Hylätty tekstiviite määräykselle {laji}: {quote}", "kielimalli", "matala")
                )
        regulations.append(regulation)

    # -- verbal regulations: the source text, classified by the model ---------------------
    verbal = [copy.deepcopy(r) for r in rule_proposal.regulations if r.type.value in VERBAL_TYPES]
    types = _verbal_types(kb, model_verbal)
    for reg in verbal:
        if types:
            reg.verbal_types = [ctx.ref(VERBAL_REGULATION_TYPE, v) for v in types]
            reg.rationale = [r for r in reg.rationale if r.method != "sanasto"]
            reg.rationale.append(
                Rationale(
                    f"Sanallisen määräyksen lajit kielimallin mukaan: {', '.join(types)}.",
                    "kielimalli",
                    "keskitaso",
                )
            )
        if ctx.policy("L-04") == "alakoodit" and model_verbal_type in VERBAL_TYPES:
            reg.type = ctx.ref(REGULATION_TYPE, model_verbal_type)
        if ctx.policy("L-04") == "kehittamisvyohyke_suunnittelumaarays" and any(
            r.type.value == "kehittamisvyohyke" for r in regulations
        ):
            reg.type = ctx.ref(REGULATION_TYPE, "suunnittelumaarays")
    if texts and _collapse("\n\n".join(texts)) != _collapse(unit.normalized_text):
        rationale.append(
            Rationale(
                "Kielimallin palauttama teksti poikkesi lähteestä; ryhmään on otettu lähdeteksti merkki merkiltä (R-19).",
                "saanto",
                "keskitaso",
                reference="Periaate P2",
            )
        )
    proposal.regulations = regulations + verbal

    # -- geometry ----------------------------------------------------------------------
    geometry = [g for g in group.get("geometria", []) or [] if g in GEOMETRIES]
    if unit.geometry_hint:
        proposal.geometry_types = [unit.geometry_hint]
    elif geometry:
        proposal.geometry_types = sorted(set(geometry), key=GEOMETRIES.index)
    else:
        proposal.geometry_types = list(rule_proposal.geometry_types)
    if proposal.kind == "yleismaarays":
        proposal.geometry_types = []

    # -- rationales and alternatives ---------------------------------------------------
    for item in data.get("perustelut", []) or []:
        add_rationale(
            str(item.get("vaite", "")),
            item.get("lainaus"),
            str(item.get("tietopohjaviite", "")),
            item.get("varmuus") if item.get("varmuus") in ("korkea", "keskitaso", "matala") else "keskitaso",
        )
    for item in data.get("vaihtoehdot", []) or []:
        rationale.append(
            Rationale(
                f"Hylätty vaihtoehto: {item.get('kuvaus')} – {item.get('miksi_ei_ensisijainen')}",
                "kielimalli",
                "keskitaso",
            )
        )

    # -- questions ---------------------------------------------------------------------
    questions = [copy.deepcopy(q) for q in rule_proposal.questions]
    resolvable = prompts.model_resolvable()
    model_kinds = {q.get("tyyppi") for q in data.get("tulkintakysymykset", []) or []}
    solved = {str(s.get("tunnus", "")): s for s in data.get("ratkaistut_kysymykset", []) or []}
    main_uses = sum(
        any(i.type.value == "paakayttotarkoitus" for i in r.additional_infos) for r in regulations
    )
    for q in questions:
        if not q.is_open or q.kind not in resolvable:
            continue
        answer = solved.get(q.id) or next((s for k, s in solved.items() if k.endswith(f"-{q.kind}")), None)
        option, basis, quote = None, "", None
        if answer:
            option, basis, quote = (
                str(answer.get("valinta", "")),
                str(answer.get("peruste", "")),
                answer.get("lainaus"),
            )
            if q.options and option not in {o.id for o in q.options}:
                option = None
        elif q.kind not in model_kinds:
            if q.kind == "K8" and geometry:
                option, basis = geometry[0], "geometria kielimallin ehdotuksesta"
            elif q.kind == "K5" and regulations:
                option, basis = "lahin_koodi", "kielimalli ehdotti lähimmän koodin"
            elif q.kind == "K2" and regulations:
                option = "yhdistelma" if main_uses > 1 else "yksi_ja_kohdistus"
                basis = "kielimallin ehdottama rakenne"
        if option is None:
            continue
        if not quote_found(quote, unit):
            rejected += 1
            continue
        q.answer = option
        q.resolved_by = "kielimalli"
        q.basis = (q.basis + " " if q.basis else "") + f"Kielimalli: {basis}".strip()

    policies = PolicyLibrary.load(kb.directory / kb.manifest["linjaukset"])
    by_policy = {k: p.id for p in policies.policies.values() for k in p.question_types}
    for item in data.get("tulkintakysymykset", []) or []:
        kind = item.get("tyyppi")
        if not kind:
            continue
        existing = next((q for q in questions if q.kind == kind), None)
        view = f"Kielimalli: {item.get('kysymys', '')} Suositus: {item.get('suositus', '')}. {item.get('peruste', '')}"
        if existing is not None:
            if existing.is_open:
                existing.basis = (existing.basis + " " if existing.basis else "") + view.strip()
            continue
        policy_id = by_policy.get(kind)
        if policy_id and policy_id in ctx.choices:
            questions.append(
                policy_question(ctx, unit, kind, policy_id, str(item.get("kysymys", "")), view.strip())
            )
            continue
        options = [
            QuestionOption(f"v{n}", str(o.get("kuvaus", "")), str(o.get("seuraus", "")))
            for n, o in enumerate(item.get("vaihtoehdot", []) or [], 1)
        ]
        recommendation = next((o.id for o in options if o.description == item.get("suositus")), None)
        questions.append(
            InterpretationQuestion(
                id=f"{unit.id}-{kind}",
                kind=kind,
                question=str(item.get("kysymys", "")),
                options=options,
                recommendation=recommendation,
                basis=view.strip(),
            )
        )

    # -- title and letter code ---------------------------------------------------------
    agreement = structure_of(proposal) == structure_of(rule_proposal) and (
        bool(structure_of(rule_proposal)) or proposal.kind == "yleismaarays"
    )
    if agreement:
        proposal.letter_code = rule_proposal.letter_code
        proposal.title = dict(rule_proposal.title)
    elif proposal.kind == "kaavakohde":
        structure = Structure(regulations=regulations, geometry=proposal.geometry_types, method="koodisto")
        proposal.letter_code = letter_code_for(ctx, unit, structure, questions, rationale)
        apply_title_policy(ctx, unit, proposal, rationale)
    questions = _dedupe(questions)
    rationale.insert(
        0,
        Rationale(
            "Rakenne on sama kuin sääntöpohjaisessa ehdotuksessa."
            if agreement
            else "Kielimallin rakenne poikkeaa sääntöpohjaisesta ehdotuksesta: "
            + (", ".join(structure_of(rule_proposal)) or "ei rakennetta")
            + " → "
            + (", ".join(structure_of(proposal)) or "ei rakennetta")
            + ".",
            "kielimalli",
            "korkea" if agreement else "keskitaso",
        ),
    )
    proposal.questions = questions
    proposal.rationale = rationale
    proposal.confidence = str(data.get("kokonaisvarmuus") or "keskitaso")
    return proposal, rejected, agreement


def _dedupe(questions: list[InterpretationQuestion]) -> list[InterpretationQuestion]:
    seen: dict[str, InterpretationQuestion] = {}
    for q in questions:
        if q.kind not in seen:
            seen[q.kind] = q
    return list(seen.values())


def hybrid_confidence(
    proposal: GroupProposal, rejected: int, agreement: bool, model_confidence: str
) -> tuple[str, str]:
    """Plan 6.9 for model proposals."""
    open_q = proposal.open_questions()
    errors = proposal.results("virhe")
    warnings = proposal.results("varoitus")
    reasons = []
    if errors:
        reasons.append(f"{len(errors)} virhettä")
    if warnings:
        reasons.append(f"{len(warnings)} varoitusta")
    if open_q:
        reasons.append("avoin tulkintakysymys: " + ", ".join(q.kind for q in open_q))
    if rejected:
        reasons.append(f"{rejected} lainausta ei löydy lähteestä")
    if reasons:
        return "matala", "; ".join(reasons)
    if agreement and model_confidence != "matala":
        return (
            "korkea",
            "kielimalli ja sääntöpohjainen vaihe ovat yhtä mieltä; ei virheitä eikä avoimia kysymyksiä",
        )
    if not agreement:
        return (
            "keskitaso",
            "kielimallin ehdotus ilman sääntöpohjaista vahvistusta; ei virheitä eikä avoimia kysymyksiä",
        )
    return "keskitaso", "kielimalli arvioi varmuuden matalaksi"


# --------------------------------------------------------------------------------------
# Run


def run_hybrid(
    kb: KnowledgeBase,
    project: ConversionProject,
    settings: HybridSettings,
    decisions: list | None = None,
) -> HybridReport:
    """Run the model on the units that need it. Mutates ``project`` and returns a report."""
    from kaavamaaraysavustaja.core.rules import RuleEngine

    prompts = PromptSet.load(kb)
    builder = RequestBuilder(kb, project, prompts)
    pricing = Pricing.load(kb)
    prices = pricing.prices(settings.model) if settings.model in pricing.models else None
    cached = bool(getattr(settings.provider, "supports_prompt_caching", True))
    report = HybridReport(
        estimate=estimate_run(kb, project, settings.model, cached=cached, reuse=settings.reuse)
        if prices
        else None
    )
    ctx = Context(
        kb,
        project.meta.plan_level,
        project.meta.mode,
        {c.id: c for c in project.policy_choices},
        project.meta.title,
    )
    engine = RuleEngine(kb)
    send, duplicates = plan_units(project)
    responses: dict[str, tuple[dict[str, Any], UnitOutcome]] = {}
    first_cost = report.estimate.first_call_usd if report.estimate else 0.0
    next_cost = report.estimate.next_call_usd if report.estimate else 0.0
    first_call = True

    def say(text: str) -> None:
        if settings.progress:
            settings.progress(text)

    for n, unit in enumerate(send, 1):
        key = unit_key(unit)
        outcome = UnitOutcome(unit.id, key, "kielimalli", model=settings.model)
        if key in settings.reuse:
            entry = settings.reuse[key]
            outcome.status, outcome.response, outcome.model = (
                "uudelleenkaytetty",
                entry["vastaus"],
                entry.get("malli", ""),
            )
        else:
            expected = first_cost if first_call else next_cost
            if not settings.budget.allows(expected):
                outcome.status, outcome.message = "ohitettu_budjetti", "budjettiraja"
                settings.budget.stopped.append(unit.id)
                report.outcomes.append(outcome)
                say(f"{n}/{len(send)} {unit.id} {unit.heading}: ohitettu (budjettiraja)")
                continue
            request = builder.request(unit, settings.quality)
            started = time.monotonic()
            try:
                response = settings.provider.generate_structured(request)
            except LLMError as error:
                outcome.status, outcome.message = "virhe", str(error)
                report.outcomes.append(outcome)
                say(f"{n}/{len(send)} {unit.id} {unit.heading}: virhe: {error}")
                continue
            first_call = False
            outcome.seconds = round(time.monotonic() - started, 1)
            replay_duration = getattr(settings.provider, "duration", None)
            if callable(replay_duration):
                outcome.seconds = replay_duration(key)
            outcome.usage = response.usage
            outcome.cost = prices.cost(response.usage) if prices else 0.0
            outcome.model = response.model_id
            outcome.response = response.data
            outcome.message = "; ".join(response.warnings)
            settings.budget.add(outcome.cost)
        responses[key] = (outcome.response, outcome)
        _apply(ctx, engine, unit, outcome, prompts, project)
        report.outcomes.append(outcome)
        say(
            f"{n}/{len(send)} {unit.id} {unit.heading}: {outcome.status}, varmuus {unit.proposal.confidence}"
            + (f", {outcome.cost:.3f} $, tokenit {outcome.usage.__dict__}" if outcome.cost else "")
        )

    for unit_id, original in duplicates.items():
        unit = project.unit(unit_id)
        found = responses.get(unit_key(original))
        if not found:
            continue
        outcome = UnitOutcome(
            unit.id, unit_key(unit), "uudelleenkaytetty", response=found[0], model=found[1].model
        )
        _apply(ctx, engine, unit, outcome, prompts, project)
        report.outcomes.append(outcome)

    totals = report.totals()
    project.provenance.append(
        Provenance(
            step="kielimalli",
            tool_version=ASSISTANT_VERSION,
            at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            knowledge_version=kb.version,
            details={
                "toimittaja": settings.provider.name,
                "malli": settings.model,
                "laatu": settings.quality,
                "kehote": prompts.label,
                "valimuisti": cached,
                "arvio_usd": round(report.estimate.usd, 4) if report.estimate else None,
                "budjetti": settings.budget.as_dict(),
                **totals,
                "yksikot": [
                    {
                        "yksikko": o.unit_id,
                        "avain": o.key,
                        "tila": o.status,
                        "malli": o.model,
                        "kaytto": o.usage.__dict__,
                        "kustannus_usd": round(o.cost, 5),
                        "kesto_s": o.seconds,
                        "yhtapitava": o.agreement,
                        "hylattyja_lainauksia": o.rejected_quotes,
                        "viesti": o.message,
                        "vastaus": o.response,
                    }
                    for o in report.outcomes
                ],
            },
        )
    )
    if decisions:
        decision_log.apply_answers(kb, project, decisions)
        for unit in project.units:
            if unit.proposal:
                engine.apply(unit, plan_level=project.meta.plan_level, mode=project.meta.mode)
                _confidence(unit)
    return report


def _apply(ctx: Context, engine, unit: SourceUnit, outcome: UnitOutcome, prompts: PromptSet, project) -> None:
    rule_proposal = unit.proposal
    proposal, rejected, agreement = proposal_from_model(
        ctx, unit, rule_proposal, outcome.response or {}, prompts
    )
    outcome.rejected_quotes, outcome.agreement = rejected, agreement
    proposal.model_check = {
        "malli": outcome.model,
        "yhtapitava": agreement,
        "hylattyja_lainauksia": rejected,
        "kokonaisvarmuus": proposal.confidence,
    }
    unit.proposal = proposal
    engine.apply(unit, plan_level=project.meta.plan_level, mode=project.meta.mode)
    _confidence(unit)
    proposal.status = "ehdotus"


def _confidence(unit: SourceUnit) -> None:
    proposal = unit.proposal
    check = proposal.model_check
    if check:
        proposal.confidence, proposal.confidence_basis = hybrid_confidence(
            proposal,
            int(check["hylattyja_lainauksia"]),
            bool(check["yhtapitava"]),
            str(check["kokonaisvarmuus"]),
        )
    else:
        proposal.confidence, proposal.confidence_basis = overall_confidence(proposal)


def reuse_from_project(
    project: ConversionProject, prompt_label: str | None = None
) -> dict[str, dict[str, Any]]:
    """Model responses stored in an earlier project (same prompt version), by unit key."""
    found: dict[str, dict[str, Any]] = {}
    for step in project.provenance:
        if step.step != "kielimalli":
            continue
        if prompt_label and step.details.get("kehote") != prompt_label:
            continue
        for item in step.details.get("yksikot", []):
            if item.get("vastaus") is not None and item.get("tila") in ("kielimalli", "uudelleenkaytetty"):
                found[item["avain"]] = {"vastaus": item["vastaus"], "malli": item.get("malli", "")}
    return found
