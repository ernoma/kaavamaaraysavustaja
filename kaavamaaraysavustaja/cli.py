"""Command line: ``kma convert`` and ``kma validate``.

Examples::

    kma convert work/kooste.txt --kartta 1
    kma convert work/kooste.txt --kartta 1 --linjaus L-03=kappaleittain --ulos work/k1
    kma convert work/kooste.txt --kartta 1 --kielimalli claude --arvio
    kma convert work/kooste.txt --kartta 1 --kielimalli claude --budjetti 3 --asetukset valinnat.yaml
    kma convert work/kooste.txt --kartta 1 --projekti work/k1/kooste.kma.json --asetukset valinnat.yaml
    kma validate work/k1/kooste.kma.json --syke --yksikot u003,u004

Without ``--kielimalli`` (default ``ei``) the conversion is rule-based and needs no SDK.

The module is QGIS-free (it only uses the core, knowledge, exporters and validation).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from kaavamaaraysavustaja import __version__
from kaavamaaraysavustaja.core.model import ConversionProject, SourceDocument

EXIT_OK, EXIT_ERROR, EXIT_USAGE = 0, 1, 2


def _print(*parts: object) -> None:
    text = " ".join(str(p) for p in parts)
    try:
        print(text)
    except UnicodeEncodeError:  # Windows console with a legacy code page
        print(text.encode(sys.stdout.encoding or "ascii", "replace").decode(sys.stdout.encoding or "ascii"))


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


# --------------------------------------------------------------------------------------
# convert


def cmd_convert(args: argparse.Namespace) -> int:
    from kaavamaaraysavustaja.core import decisions as decision_log
    from kaavamaaraysavustaja.core import edits as edit_log
    from kaavamaaraysavustaja.core.convert import convert_units
    from kaavamaaraysavustaja.core.ingest import parse, select_map
    from kaavamaaraysavustaja.core.policy import (
        PolicyError,
        PolicyLibrary,
        describe_choice,
        load_settings,
        parse_overrides,
    )
    from kaavamaaraysavustaja.exporters import arho_yaml, report, ryhti_json
    from kaavamaaraysavustaja.knowledge.base import KnowledgeBase

    source: Path = args.syote
    if not source.exists():
        _print(f"Syötetiedostoa ei löydy: {source}")
        return EXIT_USAGE
    previous = None
    if args.projekti:
        if not args.projekti.exists():
            _print(f"Muunnosprojektia ei löydy: {args.projekti}")
            return EXIT_USAGE
        previous = ConversionProject.load(args.projekti)
    try:
        settings = load_settings(args.asetukset) if args.asetukset else {"linjaukset": {}}
        overrides = {**settings["linjaukset"], **parse_overrides(args.linjaus)}
        kb = KnowledgeBase.load()
        choices = PolicyLibrary.load(kb.directory / kb.manifest["linjaukset"]).resolve(overrides)
        decisions = decision_log.merge_decisions(
            previous.decisions if previous else [], decision_log.parse_decisions(settings.get("ratkaisut"))
        )
        edits = edit_log.merge(
            previous.edits if previous else [], edit_log.parse_edits(kb, settings.get("muokkaukset"))
        )
    except PolicyError as error:
        _print(f"Virhe linjausvalinnoissa: {error}")
        return EXIT_USAGE
    except decision_log.DecisionError as error:
        _print(f"Virhe ratkaisuissa: {error}")
        return EXIT_USAGE
    except edit_log.EditError as error:
        _print(f"Virhe muokkauksissa: {error}")
        return EXIT_USAGE
    llm_name = args.kielimalli or settings.get("kielimalli") or "ei"
    if llm_name not in ("ei", "claude", "mistral"):
        _print(f"Tuntematon kielimalli {llm_name!r}: ei, claude tai mistral.")
        return EXIT_USAGE
    budget_limit = args.budjetti if args.budjetti is not None else settings.get("budjetti", 2.0)
    plan_level = args.kaavataso or settings.get("kaavataso") or "yleiskaava"
    mode = args.tila or settings.get("tila") or "vooka"
    wanted_map = args.kartta or settings.get("kartta")

    data = source.read_bytes()
    result = parse(data.decode("utf-8-sig"))
    try:
        units = select_map(result, str(wanted_map) if wanted_map else None)
    except ValueError as error:
        _print(error)
        return EXIT_USAGE
    if not units:
        _print("Syötteestä ei löytynyt yhtään määräysyksikköä.")
        return EXIT_ERROR
    map_title = units[0].map if wanted_map else None
    name = args.nimi or settings.get("nimi") or (f"{source.stem} – {map_title}" if map_title else source.stem)
    document = SourceDocument(
        id="s1", title=source.name, file=source.name, sha256=hashlib.sha256(data).hexdigest()
    )
    project = convert_units(
        kb,
        units,
        choices,
        plan_level=plan_level,
        mode=mode,
        name=name,
        source=document,
        map_title=map_title,
        decisions=decisions,
        edits=edits,
    )
    hybrid_report = None
    if llm_name != "ei":
        outcome = _hybrid(args, settings, kb, project, previous, llm_name, float(budget_limit), decisions)
        if isinstance(outcome, int):
            return outcome
        hybrid_report = outcome

    out: Path = args.ulos or source.parent / f"{source.stem}_muunnos"
    out.mkdir(parents=True, exist_ok=True)
    stem = args.tiedostonimi or source.stem
    paths = {
        "projekti": out / f"{stem}.kma.json",
        "arho": out / f"{stem}.arho.yaml",
        "ryhti": out / f"{stem}.ryhti.json",
        "raportti": out / f"{stem}_raportti.md",
        "csv": out / f"{stem}_raportti.csv",
        "ratkaisupohja": out / f"{stem}_ratkaisut.yaml",
    }
    project.save(paths["projekti"])
    library = arho_yaml.library(project, name=args.kirjaston_nimi, include_incomplete=args.myos_keskeneraiset)
    paths["arho"].write_text(arho_yaml.dumps(library), encoding="utf-8")
    fragments = ryhti_json.project_fragments(project)
    paths["ryhti"].write_text(json.dumps(fragments, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    paths["raportti"].write_text(report.markdown(project, kb), encoding="utf-8")
    paths["csv"].write_text(report.csv_text(project), encoding="utf-8-sig")
    paths["ratkaisupohja"].write_text(decision_log.template(project), encoding="utf-8")
    if args.html:
        paths["html"] = out / f"{stem}_raportti.html"
        paths["html"].write_text(report.html_text(project, kb), encoding="utf-8")

    s = report.summary(project)
    _print(f"Muunnettu {s['yksikoita']} yksikköä ({map_title or 'kaikki kartat'}), tietopohja {kb.version}.")
    for warning in result.warnings:
        _print(f"  jäsennys: {warning}")
    _print("Linjaukset: " + "; ".join(describe_choice(c) for c in choices))
    _print(
        f"Varmuus: {dict(sorted(s['varmuus'].items()))}; hyväksyttävissä sellaisenaan {s['automaatioehdokkaat']}."
    )
    _print(f"Avoimet tulkintakysymykset: {dict(sorted(s['avoimet'].items())) or 'ei'}")
    if project.decisions:
        _print(f"Käyttäjän ratkaisuja {len(project.decisions)} (tallennettu projektiin).")
        for warning in project.provenance[0].details.get("ratkaisujen_varoitukset", []):
            _print(f"  ratkaisu: {warning}")
    if project.edits:
        _print(f"Käyttäjän rakennemuokkauksia {len(project.edits)} (tallennettu projektiin).")
        for warning in project.provenance[0].details.get("muokkausten_varoitukset", []):
            _print(f"  muokkaus: {warning}")
    if hybrid_report is not None:
        t = hybrid_report.totals()
        _print(
            f"Kielimalli {llm_name}: {t['kutsuja']} kutsua, uudelleenkäytetty {t['uudelleenkaytettyja']}, "
            f"budjetin takia ohitettu {t['budjetin_takia_ohitettuja']}, virheitä {t['virheita']}; "
            f"kustannus {t['kustannus_usd']:.2f} $, tokenit {t['tokenit']}; yhtäpitäviä sääntöjen kanssa "
            f"{t['yhtapitavia']}, hylättyjä lainauksia {t['hylattyja_lainauksia']}."
        )
    _print(f"Tekstin poikkeamat lähteestä (R-19): {s['tekstimuutokset']}")
    _print(
        f"Arho-kirjastossa {len(library.get('plan_regulation_groups', []))} ryhmää"
        + (
            ""
            if args.myos_keskeneraiset
            else " (virheelliset jätetty pois; --myos-keskeneraiset ottaa mukaan)"
        )
    )
    schema_note = _schema_check(kb, fragments)
    _print(
        f"Ryhti-fragmentteja {len(fragments['planRegulationGroups'])} + {len(fragments['generalRegulationGroups'])} "
        f"yleismääräysryhmää; {schema_note}"
    )
    for label, path in paths.items():
        _print(f"  {label}: {path}")
    return EXIT_ERROR if s["tekstimuutokset"] else EXIT_OK


def _hybrid(args, settings, kb, project, previous, llm_name, budget_limit, decisions):
    from kaavamaaraysavustaja.core.hybrid import HybridSettings, estimate_run, reuse_from_project, run_hybrid
    from kaavamaaraysavustaja.core.llm.base import LLMError
    from kaavamaaraysavustaja.core.llm.budget import Budget
    from kaavamaaraysavustaja.core.llm.prompts import PromptSet
    from kaavamaaraysavustaja.core.llm.providers import DEFAULT_MODELS, create_provider

    model = args.malli or settings.get("malli") or DEFAULT_MODELS[llm_name]
    reuse = reuse_from_project(previous, PromptSet.load(kb).label) if previous else {}
    try:
        estimate = estimate_run(kb, project, model, cached=llm_name == "claude", reuse=reuse)
    except KeyError as error:
        _print(f"Kustannusarvio: {error}")
        return EXIT_USAGE
    _print(f"Kustannusarvio: {estimate.describe()}; budjettiraja {budget_limit:.2f} $.")
    if reuse:
        _print(f"Aiemman projektin kielimallivastauksia käytettävissä: {len(reuse)}.")
    if estimate.usd > budget_limit:
        _print("Huom. arvio ylittää budjettirajan: osa yksiköistä jää sääntöpohjaisiksi.")
    if args.arvio:
        _print("Vain arvio (--arvio): kielimallia ei kutsuttu.")
        return EXIT_OK
    try:
        provider = create_provider(llm_name, model)
    except LLMError as error:
        _print(str(error))
        return EXIT_USAGE
    hybrid = HybridSettings(
        provider,
        model,
        Budget(budget_limit),
        quality=args.laatu or settings.get("laatu") or "medium",
        reuse=reuse,
        progress=_print if args.eteneminen else None,
    )
    return run_hybrid(kb, project, hybrid, decisions)


def _schema_check(kb, fragments) -> str:
    from kaavamaaraysavustaja.validation.schema import SchemaValidatorUnavailable, validate_fragments

    try:
        problems = validate_fragments(fragments, kb.load_schema())
    except SchemaValidatorUnavailable as error:
        return f"skeemavalidointi ohitettu ({error})"
    if not problems:
        return "skeemavalidointi: ei virheitä."
    return f"skeemavalidointi: {len(problems)} ryhmässä virheitä: " + "; ".join(
        f"{key}: {errors[0]}" for key, errors in list(problems.items())[:3]
    )


# --------------------------------------------------------------------------------------
# validate


def cmd_validate(args: argparse.Namespace) -> int:
    from kaavamaaraysavustaja.core.rules import RuleEngine
    from kaavamaaraysavustaja.exporters import report, ryhti_json
    from kaavamaaraysavustaja.knowledge.base import KnowledgeBase

    project = ConversionProject.load(args.projekti)
    kb = KnowledgeBase.load()
    if kb.version != project.meta.knowledge_version:
        _print(
            f"Huom. projekti on tehty tietopohjalla {project.meta.knowledge_version}, tarkistetaan tietopohjalla {kb.version}."
        )
    engine = RuleEngine(kb)
    for unit in project.units:
        engine.apply(unit, plan_level=project.meta.plan_level, mode=project.meta.mode)
    s = report.summary(project)
    errors = sum(n for (_, sev), n in s["saannot"].items() if sev == "virhe")
    _print(
        f"Paikallinen sääntötarkistus: {s['yksikoita']} yksikköä, virheitä {errors}, "
        f"tekstin poikkeamia (R-19) {s['tekstimuutokset']}."
    )
    fragments = ryhti_json.project_fragments(project)
    _print(_schema_check(kb, fragments))
    if not args.syke:
        return EXIT_ERROR if s["tekstimuutokset"] else EXIT_OK
    return _syke(args, project, kb)


def _syke(args: argparse.Namespace, project: ConversionProject, kb) -> int:
    from kaavamaaraysavustaja.exporters import ryhti_json
    from kaavamaaraysavustaja.exporters.report import is_automatable
    from kaavamaaraysavustaja.validation.syke_public_api import SykeError, api_key, validate_plan

    key = api_key()
    if not key:
        _print("Aseta Syken API-avain ympäristömuuttujaan RYHTI_API_KEY.")
        return EXIT_USAGE
    units = ryhti_json.exported_units(project)
    if args.yksikot:
        wanted = {u.strip() for u in args.yksikot.split(",")}
        units = [u for u in units if u.id in wanted]
    elif not args.kaikki:
        units = [u for u in units if is_automatable(u.proposal)][: args.ryhmat]
    if not units:
        _print("Ei validoitavia ryhmiä.")
        return EXIT_USAGE
    log = []
    failures = 0
    for unit in units:
        plan = ryhti_json.synthetic_plan([unit.proposal], name=f"{project.meta.title}/{unit.id}")
        try:
            result = validate_plan(
                plan, key=key, plan_type=args.kaavalaji, area=args.kunta, env=args.ymparisto
            )
        except SykeError as error:
            _print(f"Syke: {error}")
            return EXIT_ERROR
        relevant = result.regulation_findings()
        state = "OK" if result.status == 200 else f"HTTP {result.status}"
        _print(
            f"{unit.id} {unit.proposal.title.get('fin')}: {state}, määräystason havaintoja {len(relevant)}"
            f" (kaavatason havaintoja suodatettu {len(result.findings) - len(relevant)})"
        )
        for finding in relevant:
            message = kb.ryhti_message(finding.rule) or finding.message
            _print(f"    {finding.rule}: {message}")
        failures += bool(relevant) or result.status not in (200, 422)
        log.append(
            {
                "yksikko": unit.id,
                "otsikko": unit.proposal.title.get("fin"),
                "http": result.status,
                "havainnot": [
                    {"saanto": f.rule, "viesti": f.message, "kaavataso": f.plan_level}
                    for f in result.findings
                ],
            }
        )
    if args.tallenna:
        args.tallenna.write_text(
            json.dumps(
                {
                    "ymparisto": args.ymparisto,
                    "kaavalaji": args.kaavalaji,
                    "kunta": args.kunta,
                    "tulokset": log,
                },
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
        _print(f"Tulokset tallennettu: {args.tallenna}")
    return EXIT_ERROR if failures else EXIT_OK


# --------------------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kma", description="Kaavamääräysavustaja: sääntöpohjainen muunnos ja validointi"
    )
    p.add_argument("--version", action="version", version=f"kma {__version__}")
    sub = p.add_subparsers(dest="komento", required=True)

    c = sub.add_parser("convert", help="muunna tekstisyöte kaavamääräysryhmiksi")
    c.add_argument("syote", type=Path, help="tekstitiedosto (tools/extract_pdf_text.py tai käsin)")
    c.add_argument("--kartta", help="kartan tunnus (1, 1a) tai osa nimestä; oletus kaikki")
    c.add_argument("--ulos", type=Path, help="tuloskansio (oletus <syöte>_muunnos)")
    c.add_argument("--tiedostonimi", help="tulostiedostojen nimen alku (oletus syötteen nimi)")
    c.add_argument("--nimi", help="muunnoksen nimi raportissa ja kirjastossa")
    c.add_argument("--kirjaston-nimi", help="Arho-kirjaston nimi")
    c.add_argument("--kaavataso", choices=["yleiskaava", "asemakaava", "maakuntakaava"])
    c.add_argument("--tila", choices=["vooka", "laadinta"])
    c.add_argument(
        "--linjaus", action="append", metavar="L-0n=VAIHTOEHTO", help="linjausvalinta (toistettavissa)"
    )
    c.add_argument(
        "--asetukset", type=Path, help="asetustiedosto (YAML, ADR-0010): linjaukset, ratkaisut ym."
    )
    c.add_argument(
        "--kielimalli",
        choices=["ei", "claude", "mistral"],
        help="kielimalli epävarmoille yksiköille (oletus ei: sääntöpohjainen, ei SDK:ita)",
    )
    c.add_argument("--malli", help="mallin tunnus (oletus claude-opus-5-5 / mistral-large-latest)")
    c.add_argument("--budjetti", type=float, help="ajon budjettiraja dollareina (oletus 2.00)")
    c.add_argument(
        "--laatu", choices=["low", "medium", "high"], help="laatutaso (Claude effort, oletus medium)"
    )
    c.add_argument("--arvio", action="store_true", help="näytä kustannusarvio kutsumatta kielimallia")
    c.add_argument(
        "--projekti",
        type=Path,
        help="aiempi muunnosprojekti (*.kma.json): ratkaisut ja kielimallivastaukset säilyvät uudelleenajossa",
    )
    c.add_argument("--eteneminen", action="store_true", help="näytä kielimalliajon eteneminen yksiköittäin")
    c.add_argument("--html", action="store_true", help="tee myös HTML-raportti")
    c.add_argument(
        "--myos-keskeneraiset", action="store_true", help="vie myös virheelliset ryhmät Arho-kirjastoon"
    )
    c.set_defaults(func=cmd_convert)

    v = sub.add_parser("validate", help="tarkista muunnosprojekti (säännöt, skeema, valinnaisesti Syke)")
    v.add_argument("projekti", type=Path, help="*.kma.json")
    v.add_argument(
        "--syke", action="store_true", help="validoi myös Syken julkisella rajapinnalla (verkko, avain)"
    )
    v.add_argument("--ymparisto", choices=["test", "prod"], default="test")
    v.add_argument("--yksikot", help="validoitavat yksiköt pilkulla eroteltuina, esim. u003,u004")
    v.add_argument("--ryhmat", type=int, default=5, help="validoitavien ryhmien enimmäismäärä (oletus 5)")
    v.add_argument("--kaikki", action="store_true", help="validoi kaikki ryhmät")
    v.add_argument("--kaavalaji", default="21", help="RY_Kaavalaji-koodi (oletus 21 yleiskaava)")
    v.add_argument("--kunta", default="837", help="kuntakoodi (oletus 837 Tampere)")
    v.add_argument("--tallenna", type=Path, help="tallenna Syken tulokset JSON-tiedostoon")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
