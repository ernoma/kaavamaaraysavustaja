"""Conversion report (muunnosraportti): Markdown and CSV, optionally HTML (plan 6.12)."""

from __future__ import annotations

import csv
import html
import io
from collections import Counter
from typing import Any

from kaavamaaraysavustaja.core.model import ConversionProject, GroupProposal, SourceUnit
from kaavamaaraysavustaja.core.policy import describe_choice
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase

KIND = {
    "kaavakohde": "kaavamääräysryhmä",
    "yleismaarays": "yleismääräysryhmä",
    "ei_maarays": "ei kaavamääräys",
}


def is_automatable(proposal: GroupProposal | None) -> bool:
    """Candidate for acceptance as such: no open questions, no errors, no warnings."""
    return bool(
        proposal
        and proposal.kind != "ei_maarays"
        and proposal.confidence != "matala"
        and not proposal.open_questions()
        and not proposal.results("virhe")
        and not proposal.results("varoitus")
    )


def summary(project: ConversionProject) -> dict[str, Any]:
    units = project.units
    proposals = [u.proposal for u in units if u.proposal]
    questions = [q for p in proposals for q in p.questions]
    results = [r for p in proposals for r in p.rule_results]
    r19 = [r for r in results if r.rule_id == "R-19" and r.severity == "virhe"]
    return {
        "yksikoita": len(units),
        "tyypit": Counter(p.kind for p in proposals),
        "varmuus": Counter(p.confidence for p in proposals),
        "automaatioehdokkaat": sum(is_automatable(p) for p in proposals),
        "avoimet": Counter(q.kind for q in questions if q.is_open),
        "ratkaistut": Counter(q.kind for q in questions if not q.is_open),
        "saannot": Counter((r.rule_id, r.severity) for r in results),
        "tekstimuutokset": len(r19),
        "kaksoiskappaleet": sum(1 for u in units if u.duplicates_of),
    }


def code_list(proposal: GroupProposal) -> str:
    parts = []
    for reg in proposal.regulations:
        infos = []
        for info in reg.additional_infos:
            value = f"={info.value.code.value}" if info.value and info.value.code else ""
            infos.append(info.type.value + value)
        verbal = ",".join(v.value for v in reg.verbal_types)
        parts.append(
            reg.type.value
            + (f" [{', '.join(infos)}]" if infos else "")
            + (f" {{{verbal}}}" if verbal else "")
        )
    return " | ".join(parts)


def plain_structure(kb: KnowledgeBase | None, proposal: GroupProposal) -> list[str]:
    """The structure in the planner's language (plan 7.1: 'Pääkäyttötarkoitus: …')."""

    def name(uri: str, fallback: str) -> str:
        code = kb.index.by_uri(uri) if kb else None
        return code.name.get("fi", fallback) if code else fallback

    lines = []
    for reg in proposal.regulations:
        title = name(reg.type.uri, reg.type.value)
        infos = []
        for info in reg.additional_infos:
            text = name(info.type.uri, info.type.value)
            if info.value and info.value.code:
                text += f" → {name(info.value.code.uri, info.value.code.value)}"
            infos.append(text)
        if reg.value and reg.value.text:
            text = reg.value.text.get("fin", "")
            short = text if len(text) <= 120 else text[:117] + "…"
            kinds = ", ".join(name(v.uri, v.value) for v in reg.verbal_types) or "–"
            lines.append(f'{title}: "{short}" (lajit: {kinds})')
        elif reg.value and reg.value.number is not None:
            number = f"{reg.value.number:g}".replace(".", ",")
            lines.append(f"{title}: {number}{' ' + reg.value.unit if reg.value.unit else ''}")
        else:
            lines.append(title + (f" ({'; '.join(infos)})" if infos else ""))
    for rec in proposal.recommendations:
        text = rec.text.get("fin", "")
        lines.append(f'Kaavasuositus: "{text if len(text) <= 120 else text[:117] + "…"}"')
    return lines


def units_of(project: ConversionProject) -> list[SourceUnit]:
    return [u for u in project.units if u.proposal]


def markdown(project: ConversionProject, kb: KnowledgeBase | None = None) -> str:
    meta = project.meta
    s = summary(project)
    out = [
        f"# Muunnosraportti: {meta.title}",
        "",
        "*Sääntöpohjainen muunnos (vaihe 1). Ehdotukset ovat tarkistamattomia: ihminen hyväksyy aina muunnoksen.*",
        "",
        "| | |",
        "|---|---|",
        f"| Kartta | {meta.map or '–'} |",
        f"| Kaavataso / tila | {meta.plan_level} / {meta.mode} |",
        f"| Lähdekaavat | {'; '.join(p.name + (f' ({p.date})' if p.date else '') for p in meta.source_plans) or '–'} |",
        f"| Tietopohja | {meta.knowledge_version} |",
        f"| Koodistot | {', '.join(f'{k} {v}' for k, v in sorted(meta.codelist_versions.items()))} |",
        f"| Säännöt / linjaukset | {meta.rules_version} / {meta.policy_version} |",
        f"| Avustaja | {meta.assistant_version} |",
        f"| Ajettu | {project.provenance[-1].at if project.provenance else '–'} |",
        "",
        "## Linjausvalinnat",
        "",
        *[f"- {describe_choice(c)} – {c.title}" for c in project.policy_choices],
        "",
        "## Yhteenveto",
        "",
        f"- Yksiköitä: {s['yksikoita']} ({', '.join(f'{KIND.get(k, k)} {n}' for k, n in s['tyypit'].items())}); "
        f"kaksoiskappaleita muilla kartoilla: {s['kaksoiskappaleet']}",
        f"- Varmuus: {', '.join(f'{k} {n}' for k, n in sorted(s['varmuus'].items()))}",
        f"- Hyväksyttävissä sellaisenaan (ei avoimia kysymyksiä, virheitä eikä varoituksia): "
        f"{s['automaatioehdokkaat']} / {s['yksikoita']}",
        f"- Avoimet tulkintakysymykset: {', '.join(f'{k} {n}' for k, n in sorted(s['avoimet'].items())) or 'ei'}",
        f"- Linjauksella tai tilalla ratkaistut: {', '.join(f'{k} {n}' for k, n in sorted(s['ratkaistut'].items())) or 'ei'}",
        f"- Sanallisen tekstin poikkeamat lähteestä (R-19 virhe): {s['tekstimuutokset']}",
        *(
            [
                f"- Käyttäjän rakennemuokkaukset (lisätiedot): {len(project.edits)}; muokatut ryhmät "
                f"{sum(1 for u in units_of(project) if u.proposal.status == 'muokattu')}, perustelut yksiköittäin"
            ]
            if project.edits
            else []
        ),
        "",
        "| Sääntö | Vakavuus | Kpl |",
        "|---|---|---:|",
        *[f"| {rule} | {sev} | {n} |" for (rule, sev), n in sorted(s["saannot"].items())],
        "",
        "## Yksiköt",
    ]
    for unit in project.units:
        out += unit_markdown(unit, kb)
    return "\n".join(out) + "\n"


def unit_markdown(unit: SourceUnit, kb: KnowledgeBase | None) -> list[str]:
    p = unit.proposal
    heading = " ".join(
        x
        for x in [
            unit.letter_code_raw,
            unit.heading or ("YLEISMÄÄRÄYS" if unit.kind == "yleismaarays" else ""),
        ]
        if x
    )
    out = ["", f"### {unit.id} {heading}", ""]
    where = [f"sivu {unit.page}" if unit.page else None, " > ".join(unit.section_path) or None]
    if unit.duplicates_of:
        where.append(f"sama kuin {unit.duplicates_of}")
    out.append(f"*{', '.join(w for w in where if w) or 'sijainti tuntematon'}*")
    if unit.normalized_text:
        out += ["", "> " + unit.normalized_text.replace("\n\n", "\n>\n> ")]
    pending = [c for c in unit.normalization_diff if c.needs_confirmation]
    if pending:
        out += ["", "Vahvistettavat normalisoinnit:"]
        out += [f"- {c.part}: `{c.raw}` → `{c.normalized}` ({c.note or c.kind})" for c in pending]
    if p is None:
        return out
    out += [
        "",
        f"**Ehdotus** ({KIND.get(p.kind, p.kind)}, varmuus {p.confidence}: {p.confidence_basis})",
        "",
        f"- Otsikko: {p.title.get('fin', '–')}; kirjaintunnus: {p.letter_code or '–'}; "
        f"geometria: {', '.join(p.geometry_types) or '–'}",
        *[f"- {line}" for line in plain_structure(kb, p)],
        f"- Tekninen: `{code_list(p) or '–'}`",
    ]
    rationale = [*p.rationale, *(r for reg in p.regulations for r in reg.rationale)]
    rationale += [r for rec in p.recommendations for r in rec.rationale]
    if rationale:
        out += ["", "Perustelut:"]
        for r in rationale:
            extra = "; ".join(x for x in [f'lainaus: "{r.quote}"' if r.quote else None, r.reference] if x)
            out.append(f"- {r.claim} *({r.method}, {r.confidence}{'; ' + extra if extra else ''})*")
    if p.questions:
        out += ["", "Tulkintakysymykset:"]
        for q in p.questions:
            state = (
                f"ratkaistu: {q.answer} ({q.resolved_by})"
                if not q.is_open
                else f"**avoin**, suositus {q.recommendation or '–'}"
            )
            options = "; ".join(f"{o.id} = {o.description}" for o in q.options)
            out.append(
                f"- {q.kind} {q.question} – {state}"
                + (f". Vaihtoehdot: {options}" if options else "")
                + (f". Peruste: {q.basis}" if q.basis and q.is_open else "")
            )
    if p.rule_results:
        out += ["", "Sääntötarkistus:"]
        for r in p.rule_results:
            ryhti = ""
            if r.ryhti_rules:
                ids = ", ".join(f"`{rid}`" for rid in r.ryhti_rules)
                message = kb.ryhti_message(r.ryhti_rules[0]) if kb else None
                ryhti = f" Ryhti: {ids}" + (f' – "{message}"' if message else "")
            out.append(
                f"- {r.rule_id} {r.severity}: {r.message}{' (' + r.target + ')' if r.target else ''}.{ryhti}"
            )
    return out


CSV_FIELDS = [
    "yksikko",
    "sivu",
    "kartta",
    "osio",
    "lahteen_otsikko",
    "lahteen_tunnus",
    "ryhmatyyppi",
    "otsikko",
    "kirjaintunnus",
    "geometria",
    "rakenne",
    "varmuus",
    "sellaisenaan",
    "avoimet_kysymykset",
    "ratkaistut_kysymykset",
    "virheet",
    "varoitukset",
    "huomiot",
    "vahvistettavat_normalisoinnit",
    "kaksoiskappale",
]


def csv_text(project: ConversionProject) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for unit in project.units:
        p = unit.proposal
        row = {
            "yksikko": unit.id,
            "sivu": unit.page or "",
            "kartta": unit.map or "",
            "osio": " > ".join(unit.section_path),
            "lahteen_otsikko": unit.heading or "",
            "lahteen_tunnus": unit.letter_code or "",
            "vahvistettavat_normalisoinnit": sum(1 for c in unit.normalization_diff if c.needs_confirmation),
            "kaksoiskappale": unit.duplicates_of or "",
        }
        if p:
            row.update(
                ryhmatyyppi=p.kind,
                otsikko=p.title.get("fin", ""),
                kirjaintunnus=p.letter_code or "",
                geometria=",".join(p.geometry_types),
                rakenne=code_list(p),
                varmuus=p.confidence,
                sellaisenaan="kyllä" if is_automatable(p) else "ei",
                avoimet_kysymykset=",".join(q.kind for q in p.open_questions()),
                ratkaistut_kysymykset=",".join(q.kind for q in p.questions if not q.is_open),
                virheet="; ".join(f"{r.rule_id}: {r.message}" for r in p.results("virhe")),
                varoitukset="; ".join(f"{r.rule_id}: {r.message}" for r in p.results("varoitus")),
                huomiot="; ".join(f"{r.rule_id}: {r.message}" for r in p.results("huomio")),
            )
        writer.writerow(row)
    return buffer.getvalue()


def html_text(project: ConversionProject, kb: KnowledgeBase | None = None) -> str:
    """Minimal standalone HTML: the Markdown report in a readable page."""
    body = []
    in_list = False
    for line in markdown(project, kb).splitlines():
        if line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{html.escape(line[2:])}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            body.append(f"<h{level}>{html.escape(line.lstrip('# '))}</h{level}>")
        elif line.startswith(">"):
            body.append(f"<blockquote>{html.escape(line.lstrip('> '))}</blockquote>")
        elif line.strip():
            body.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        body.append("</ul>")
    title = html.escape(f"Muunnosraportti: {project.meta.title}")
    return (
        '<!doctype html>\n<html lang="fi"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>body{{font-family:sans-serif;max-width:60rem;margin:auto}}"
        "blockquote{color:#333;border-left:3px solid #ccc;padding-left:1em}</style></head><body>\n"
        + "\n".join(body)
        + "\n</body></html>\n"
    )
