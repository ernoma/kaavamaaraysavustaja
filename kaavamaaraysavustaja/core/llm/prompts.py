"""Prompts as data (``knowledge/prompts/v<n>/``, plan 6.8, ADR-0013, ADR-0017).

The request is split into a stable, cached part (system instructions and the static context
generated from the knowledge base: codes, annex 4, question types K1–K15 and the policy
choices of the run) and a varying task part (the regulation unit, the phase 1 findings, open
questions, resolved items and the most similar examples found by a vocabulary search).
Only regulation text and this context are sent to the model, never PDFs (CLAUDE.md rule 5).

From v3 on the drafting mode (laadinta) has its own system instructions and a context section
(placeholder ``{{LAADINTAOHJE}}``), and examples marked ``tila: laadinta`` are used only in that
mode, so the VOOKA request stays the same as in v2.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import yaml

from kaavamaaraysavustaja.core import match
from kaavamaaraysavustaja.core.llm.schema import code_enums
from kaavamaaraysavustaja.core.model import GroupProposal, InterpretationQuestion, PolicyChoice, SourceUnit
from kaavamaaraysavustaja.core.policy import describe_choice
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase
from kaavamaaraysavustaja.knowledge.codelists import (
    ADDITIONAL_INFO_TYPE,
    REGULATION_TYPE,
    VERBAL_REGULATION_TYPE,
)

DESCRIPTION_CHARS = 160


def _first_sentence(text: str, limit: int = DESCRIPTION_CHARS) -> str:
    text = " ".join((text or "").split())
    text = re.sub(r"^Ilmaisee, että ", "", text)
    end = text.find(". ")
    if 0 < end < limit:
        return text[: end + 1]
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


@dataclass(frozen=True)
class PromptSet:
    directory: str  # e.g. prompts/v1
    version: int
    system: str
    context_template: str
    question_types: list[dict[str, Any]]
    examples: list[dict[str, Any]]
    max_examples: int
    stem_length: int
    drafting_system: str = ""  # system instructions in drafting mode ("" = same as VOOKA)
    drafting_context: str = ""  # replaces {{LAADINTAOHJE}} in drafting mode

    @property
    def label(self) -> str:
        """Prompt version stored in provenance, e.g. ``prompts/v1 v1``."""
        return f"{self.directory} v{self.version}"

    @classmethod
    def load(cls, kb: KnowledgeBase, directory: str | None = None) -> PromptSet:
        """The active prompt version, or ``directory`` (e.g. ``prompts/v2``) for comparisons."""
        info = kb.manifest.get("kehotteet") or {}
        if not info and directory is None:
            raise ValueError("Tietopohjassa ei ole kehotteita (manifest: kehotteet).")
        directory = directory or info["hakemisto"]
        base = kb.directory / directory
        meta = yaml.safe_load((base / "kehote.yaml").read_text(encoding="utf-8"))
        types = yaml.safe_load((base / meta["kysymystyypit"]).read_text(encoding="utf-8"))
        examples = yaml.safe_load((base / meta["esimerkit"]).read_text(encoding="utf-8"))

        def optional(key: str) -> str:
            name = meta.get(key)
            return (base / name).read_text(encoding="utf-8").strip() if name else ""

        return cls(
            directory=directory,
            version=int(meta["versio"]),
            system=(base / meta["jarjestelmaohje"]).read_text(encoding="utf-8").strip(),
            context_template=(base / meta["konteksti"]).read_text(encoding="utf-8"),
            question_types=types["kysymystyypit"],
            examples=examples.get("esimerkit", []),
            max_examples=int(meta.get("esimerkkeja_enintaan", 3)),
            stem_length=int(meta.get("haun_sanan_alku", 6)),
            drafting_system=optional("jarjestelmaohje_laadinta"),
            drafting_context=optional("laadintaohje"),
        )

    def system_for(self, mode: str) -> str:
        """System instructions of the conversion mode (VOOKA or drafting)."""
        return self.drafting_system if mode == "laadinta" and self.drafting_system else self.system

    # -- question types -------------------------------------------------------------------

    def model_resolvable(self) -> set[str]:
        return {q["tyyppi"] for q in self.question_types if q.get("mallin_ratkaistavissa")}

    def question_type(self, kind: str) -> dict[str, Any] | None:
        return next((q for q in self.question_types if q["tyyppi"] == kind), None)

    # -- static context (cached) ----------------------------------------------------------

    def static_context(
        self, kb: KnowledgeBase, plan_level: str, mode: str, choices: list[PolicyChoice]
    ) -> str:
        enums = code_enums(kb.index, plan_level, kb.valid_on)

        def code_line(codelist: str, value: str) -> str:
            code = kb.index.get(codelist, value)
            flags = []
            if code and code.in_extension(match.AREA_RESERVATION, kb.valid_on):
                flags.append("[aluevaraus]")
            if code and code.in_extension(match.QUANTITY, kb.valid_on):
                flags.append("[suure]")
            name = code.name.get("fi", "") if code else ""
            description = _first_sentence(code.description.get("fi", "")) if code else ""
            return f"- {value}: {name} {' '.join(flags)} – {description}".replace("  ", " ")

        annex_lines = []
        for row in kb.annex.get(plan_level, []):
            codes = [
                str(c if isinstance(c, str) else c.get("koodi")) for c in row.get("kaavamaarayslajit", [])
            ]
            infos = []
            for info in row.get("lisatiedot", []):
                laji = info.get("laji")
                laji = laji if isinstance(laji, str) else (laji or {}).get("koodi")
                value = info.get("arvo")
                value = value if isinstance(value, str) or value is None else value.get("koodi")
                infos.append(f"{laji}={value}" if value else str(laji))
            annex_lines.append(
                f"- {row.get('kirjaintunnus') or '–'} {row.get('otsikko')} [{row.get('geometria') or '?'}]: "
                + " + ".join(codes + infos)
            )

        question_lines = []
        for q in self.question_types:
            question_lines.append(
                f"- {q['tyyppi']} {q['nimi']}: {' '.join(q['kuvaus'].split())} "
                f"Ei tätä: {' '.join(str(q.get('ei_tata', '')).split())} "
                f"Esimerkki: {q.get('esimerkki', '')}. Suositus: {' '.join(str(q.get('suositus', '')).split())} "
                f"Kielimalli saa ratkaista: {'kyllä' if q.get('mallin_ratkaistavissa') else 'ei'}."
            )

        policy_lines = []
        library = _policy_descriptions(kb)
        for choice in choices:
            option_text = library.get(choice.id, {}).get(choice.option, "")
            policy_lines.append(f"- {describe_choice(choice)} {choice.title}: {option_text}".rstrip())

        values = {
            "{{KAAVATASO}}": plan_level,
            "{{TILA}}": "VOOKA (lähdeuskollinen muunnos)" if mode == "vooka" else "laadinta",
            "{{KYSYMYSTYYPIT}}": "\n".join(question_lines),
            "{{LINJAUKSET}}": "\n".join(policy_lines),
            "{{KAAVAMAARAYSLAJIT}}": "\n".join(
                code_line(REGULATION_TYPE, v) for v in enums["regulation_types"]
            ),
            "{{LISATIEDON_LAJIT}}": "\n".join(
                code_line(ADDITIONAL_INFO_TYPE, v) for v in enums["additional_info_types"]
            ),
            "{{SANALLISEN_LAJIT}}": "\n".join(
                code_line(VERBAL_REGULATION_TYPE, v) for v in enums["verbal_types"]
            ),
            "{{LIITE4}}": "\n".join(annex_lines),
            "{{LAADINTAOHJE}}": self.drafting_context if mode == "laadinta" else "",
        }
        text = self.context_template
        for key, value in values.items():
            text = text.replace(key, value)
        return text.strip() + "\n"

    # -- examples (vocabulary search) -----------------------------------------------------

    def _terms(self, *texts: str | None) -> set[str]:
        terms = set()
        for text in texts:
            for word in match.words(text or ""):
                if len(word) >= 3:
                    terms.add(word[: self.stem_length])
        return terms

    def all_examples(self, kb: KnowledgeBase, mode: str = "vooka") -> list[dict[str, Any]]:
        approved = []
        for entry in kb.approved:
            source = entry.get("lahde", {})
            approved.append(
                {
                    "tunnus": f"hyväksytty: {source.get('otsikko')}",
                    "periaate": "Tampereen hyväksymä muunnos",
                    "yksikko": {
                        "tyyppi": "merkinta",
                        "otsikko": source.get("otsikko"),
                        "kirjaintunnus": source.get("kirjaintunnus"),
                        "teksti": "",
                    },
                    "tulos": entry.get("ryhma", {}),
                }
            )
        return approved + [e for e in self.examples if e.get("tila", mode) == mode]

    def select_examples(
        self, kb: KnowledgeBase, unit: SourceUnit, mode: str = "vooka"
    ) -> list[dict[str, Any]]:
        """The most similar examples by shared word stems (heading weighted twice)."""
        heading_terms = self._terms(unit.heading)
        text_terms = self._terms(unit.normalized_text)
        scored = []
        for n, example in enumerate(self.all_examples(kb, mode)):
            source = example.get("yksikko", {})
            e_heading = self._terms(source.get("otsikko"))
            e_text = self._terms(source.get("teksti"))
            union = (heading_terms | text_terms) | (e_heading | e_text)
            if not union:
                continue
            score = (
                2 * len(heading_terms & e_heading) + len((heading_terms | text_terms) & (e_heading | e_text))
            ) / len(union)
            if source.get("tyyppi", "merkinta") == unit.kind:
                score += 0.01  # same kind first among equals
            scored.append((score, -n, example))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        chosen = [e for score, _, e in scored if score > 0.011][: self.max_examples]
        if not chosen and scored:
            chosen = [scored[0][2]]
        return chosen

    # -- task (not cached) ----------------------------------------------------------------

    def task_input(
        self,
        kb: KnowledgeBase,
        unit: SourceUnit,
        proposal: GroupProposal,
        resolved: list[dict[str, str]],
        mode: str = "vooka",
    ) -> str:
        from kaavamaaraysavustaja.core.evaluation import structure_of

        def question_dict(q: InterpretationQuestion) -> dict[str, Any]:
            return {
                "tunnus": q.id,
                "tyyppi": q.kind,
                "kysymys": q.question,
                "vaihtoehdot": [
                    {"tunnus": o.id, "kuvaus": o.description, "seuraus": o.consequence} for o in q.options
                ],
                "suositus": q.recommendation,
                "peruste": q.basis,
            }

        verbal_hints = sorted({v.value for reg in proposal.regulations for v in reg.verbal_types})
        task = {
            "yksikko": {
                "tunnus": unit.id,
                "tyyppi": unit.kind,
                "otsikko": unit.heading,
                "kirjaintunnus": unit.letter_code,
                "kartta": unit.map,
                "valiotsikko": " > ".join(unit.section_path) or None,
                "geometriavihje": unit.geometry_hint,
                "teksti": unit.normalized_text,
            },
            "vaihe1": {
                "rakenne": structure_of(proposal),
                "otsikko": proposal.title.get("fin"),
                "kirjaintunnus": proposal.letter_code,
                "geometria": proposal.geometry_types,
                "sanallisen_lajit_vihjeet": verbal_hints,
                "varmuus": proposal.confidence,
                "perustelut": [r.claim for r in proposal.rationale][:8],
                "saannot": [
                    {"tunnus": r.rule_id, "vakavuus": r.severity, "viesti": r.message}
                    for r in proposal.rule_results
                    if r.rule_id != "R-19"
                ],
            },
            "avoimet_kysymykset": [question_dict(q) for q in proposal.questions if q.is_open],
            "ratkaistut": resolved,
            "esimerkit": [
                {
                    "periaate": " ".join(str(e.get("periaate", "")).split()),
                    "yksikko": e["yksikko"],
                    "tulos": e["tulos"],
                }
                for e in self.select_examples(kb, unit, mode)
            ],
        }
        return json.dumps(task, ensure_ascii=False, indent=1)


def _policy_descriptions(kb: KnowledgeBase) -> dict[str, dict[str, str]]:
    data = yaml.safe_load((kb.directory / kb.manifest["linjaukset"]).read_text(encoding="utf-8"))
    return {
        p["tunnus"]: {o["arvo"]: " ".join(str(o.get("kuvaus", "")).split()) for o in p["vaihtoehdot"]}
        for p in data["linjaukset"]
    }
