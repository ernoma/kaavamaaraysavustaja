"""Evaluate the conversion against the golden test data (plan 10.3).

Usage::

    python tools/evaluate.py                              # rule-based, all golden sets
    python tools/evaluate.py --yksikot                    # also a table per unit
    python tools/evaluate.py --hybridi claude             # hybrid with recorded responses (no network)
    python tools/evaluate.py --vertailu                   # rule-based vs hybrid (Claude, Mistral if recorded)
    python tools/evaluate.py --hybridi claude --live --arvio            # cost estimate only
    python tools/evaluate.py --hybridi claude --live --budjetti 8       # live run, records the responses

Recorded responses are in ``tests/recorded_llm/golden_v2_<provider>.json`` (no API keys).
A live run shows the cost estimate first and records every response, so CI can replay them.
Prints Markdown for docs/vaihe2_raportti.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaavamaaraysavustaja.core.convert import convert_units  # noqa: E402
from kaavamaaraysavustaja.core.evaluation import (  # noqa: E402
    combine,
    evaluate,
    model_costs,
    percent,
    structure_of,
)
from kaavamaaraysavustaja.core.ingest import parse  # noqa: E402
from kaavamaaraysavustaja.core.policy import PolicyLibrary  # noqa: E402
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase  # noqa: E402

GOLDEN = ROOT / "tests" / "golden"
RECORDED = ROOT / "tests" / "recorded_llm"
GOLDEN_SETS = [
    ("kartta1", GOLDEN / "kartta1_otos.txt", GOLDEN / "kartta1_odotetut.yaml"),
    ("keskusta", GOLDEN / "keskusta_otos.txt", GOLDEN / "keskusta_odotetut.yaml"),
    ("kartat2_4", GOLDEN / "kartat2_4_otos.txt", GOLDEN / "kartat2_4_odotetut.yaml"),
]
DEFAULT_MODELS = {"claude": "claude-opus-5-5", "mistral": "mistral-large-latest"}


def recorded_path(provider: str) -> Path:
    return RECORDED / f"golden_v2_{provider}.json"


def rule_based(kb, sets=GOLDEN_SETS):
    projects, evaluations = [], []
    choices = PolicyLibrary.load().resolve()
    for name, text, expected in sets:
        units = parse(text.read_text(encoding="utf-8")).units
        project = convert_units(kb, units, choices, name=f"testiaineisto {name}")
        projects.append(project)
        evaluations.append(evaluate(project, yaml.safe_load(expected.read_text(encoding="utf-8"))))
    return projects, evaluations


def hybrid(kb, provider, model, budget, sets=GOLDEN_SETS, progress=None, quality="medium"):
    from kaavamaaraysavustaja.core.hybrid import HybridSettings, run_hybrid

    projects, evaluations = rule_based(kb, sets)
    for project in projects:
        run_hybrid(kb, project, HybridSettings(provider, model, budget, quality=quality, progress=progress))
    evaluations = [
        evaluate(p, yaml.safe_load(expected.read_text(encoding="utf-8")))
        for p, (_, _, expected) in zip(projects, sets, strict=True)
    ]
    return projects, evaluations


def replay_provider(name: str):
    from kaavamaaraysavustaja.core.llm.fake import ReplayProvider

    path = recorded_path(name)
    if not path.exists():
        return None, None
    provider = ReplayProvider.from_file(path)
    return provider, provider.record.get("malli", DEFAULT_MODELS[name])


def metrics_table(columns: dict[str, tuple[list, object]]) -> list[str]:
    names = list(columns)
    lines = ["| Mittari | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    evaluations = {n: combine(e) for n, (e, _) in columns.items()}
    first = next(iter(evaluations.values()))
    for metric in first.metrics():
        lines.append(
            f"| {metric} | " + " | ".join(percent(evaluations[n].metrics()[metric]) for n in names) + " |"
        )
    for metric in first.f1_scores():
        cells = []
        for n in names:
            p, r, f = evaluations[n].f1_scores()[metric]
            cells.append(f"P {p:.2f} / R {r:.2f} / F1 {f:.2f}")
        lines.append(f"| {metric} (F1) | " + " | ".join(cells) + " |")
    for level in ("korkea", "keskitaso", "matala"):
        lines.append(
            f"| varmuus {level}: rakenne oikein | "
            + " | ".join(percent(evaluations[n].calibration()[level]) for n in names)
            + " |"
        )
    lines.append(
        "| sanallisen tekstin poikkeamat (R-19) | "
        + " | ".join(str(evaluations[n].text_changes) for n in names)
        + " |"
    )
    cost_cells, time_cells = [], []
    for n in names:
        projects = columns[n][1]
        c = model_costs(projects) if projects else None
        if c and c["kutsuja"]:
            cost_cells.append(
                f"{c['usd_per_yksikko']:.3f} $ / yks. ({c['kustannus_usd']:.2f} $, {int(c['kutsuja'])} kutsua)"
            )
            time_cells.append(f"{c['s_per_kutsu']:.1f} s / kutsu")
        else:
            cost_cells.append("0")
            time_cells.append("–")
    lines.append("| kustannus | " + " | ".join(cost_cells) + " |")
    lines.append("| aika | " + " | ".join(time_cells) + " |")
    return lines


def unit_table(evaluations) -> list[str]:
    lines = [
        "| Yksikkö | Rakenne | Odotettu | Oikein | Varmuus | Puuttuvat kysymykset | Sellaisenaan |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in combine(evaluations).results:
        lines.append(
            f"| {r.unit.letter_code or ''} {r.unit.heading or 'Yleismääräys'} | {', '.join(structure_of(r.unit.proposal)) or '–'} | "
            f"{', '.join(r.expected.get('rakenne', [])) or '–'} | {'kyllä' if r.structure_ok else 'ei'} | "
            f"{r.unit.proposal.confidence} | {', '.join(sorted(r.missing_questions)) or '–'} | "
            f"{'kyllä' if r.accepted_as_such else 'ei'} |"
        )
    return lines


def live(args, kb) -> int:
    from kaavamaaraysavustaja.core.hybrid import estimate_run
    from kaavamaaraysavustaja.core.llm.budget import Budget
    from kaavamaaraysavustaja.core.llm.fake import RecordingProvider
    from kaavamaaraysavustaja.core.llm.prompts import PromptSet
    from kaavamaaraysavustaja.core.llm.providers import create_provider

    name = args.hybridi
    model = args.malli or DEFAULT_MODELS[name]
    projects, _ = rule_based(kb)
    estimates = [estimate_run(kb, project, model, cached=name == "claude") for project in projects]
    units = sum(e.units for e in estimates)
    usd = sum(e.usd for e in estimates)  # conservative: the cache write is counted once per set
    print(
        f"Kustannusarvio koko testiaineistolle ({model}): {units} yksikköä mallille, noin {usd:.2f} $ "
        f"(budjettiraja {args.budjetti:.2f} $)."
    )
    for (set_name, _, _), e in zip(GOLDEN_SETS, estimates, strict=True):
        print(f"  {set_name}: {e.describe()}")
    if args.arvio:
        return 0
    key_var = {"claude": "ANTHROPIC_API_KEY", "mistral": "MISTRAL_API_KEY"}[name]
    if not os.environ.get(key_var):
        print(f"{key_var} puuttuu: live-ajo jää tekemättä.")
        return 2
    recorder = RecordingProvider(create_provider(name, model))
    budget = Budget(args.budjetti)
    started = time.monotonic()
    projects, evaluations = hybrid(
        kb, recorder, model, budget, progress=print if args.eteneminen else None, quality=args.laatu
    )
    print(f"Live-ajo: {budget.calls} kutsua, {budget.spent:.2f} $, {time.monotonic() - started:.0f} s.")
    recorder.save(
        recorded_path(name),
        kehote=PromptSet.load(kb).label,
        tietopohja=kb.version,
        laatu=args.laatu,
        aineisto=[n for n, _, _ in GOLDEN_SETS],
    )
    print(f"Vastaukset tallennettu: {recorded_path(name).relative_to(ROOT)}")
    print("\n".join(metrics_table({f"hybridi ({name}, live)": (evaluations, projects)})))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yksikot", action="store_true", help="tulosta myös yksikkökohtainen taulukko")
    parser.add_argument(
        "--hybridi", choices=["claude", "mistral"], help="hybridi tallennetuilla vastauksilla"
    )
    parser.add_argument("--vertailu", action="store_true", help="sääntöpohjainen vs. hybridit (tallennetut)")
    parser.add_argument("--live", action="store_true", help="kutsu kielimallia ja tallenna vastaukset")
    parser.add_argument("--arvio", action="store_true", help="vain kustannusarvio (live)")
    parser.add_argument("--budjetti", type=float, default=5.0, help="live-ajon budjettiraja dollareina")
    parser.add_argument("--malli", help="mallin tunnus")
    parser.add_argument("--laatu", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--eteneminen", action="store_true")
    parser.add_argument("--json", type=Path, help="tallenna mittarit JSON-tiedostoon")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    kb = KnowledgeBase.load()

    if args.live:
        if not args.hybridi:
            parser.error("--live vaatii --hybridi claude|mistral")
        return live(args, kb)

    from kaavamaaraysavustaja.core.llm.budget import Budget

    columns: dict[str, tuple[list, object]] = {}
    rule_projects, rule_evals = rule_based(kb)
    if args.vertailu or not args.hybridi:
        columns["sääntöpohjainen"] = (rule_evals, rule_projects)
    wanted = ["claude", "mistral"] if args.vertailu else ([args.hybridi] if args.hybridi else [])
    for name in wanted:
        provider, model = replay_provider(name)
        if provider is None:
            print(f"Huom. {recorded_path(name).relative_to(ROOT)} puuttuu: hybridi ({name}) jää vertailusta.")
            continue
        projects, evaluations = hybrid(kb, provider, model, Budget(None))
        columns[f"hybridi ({name})"] = (evaluations, projects)
    print("\n".join(metrics_table(columns)))
    last = list(columns.values())[-1][0]
    unmatched = combine(last).unmatched
    if unmatched:
        print(f"\nOdotuksia ilman yksikköä: {', '.join(unmatched)}")
    if args.yksikot:
        print()
        print("\n".join(unit_table(last)))
    if args.json:
        out = {}
        for name, (evaluations, projects) in columns.items():
            e = combine(evaluations)
            out[name] = {
                "mittarit": e.metrics(),
                "f1": e.f1_scores(),
                "kalibrointi": e.calibration(),
                "r19": e.text_changes,
                "kustannus": model_costs(projects) if projects else None,
            }
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
