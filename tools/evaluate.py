"""Evaluate the rule-based conversion against the golden test data (plan 10.3).

Usage::

    python tools/evaluate.py                       # tests/golden/kartta1_otos.txt, default policies
    python tools/evaluate.py --yksikot             # also a table per unit

Prints Markdown for docs/vaihe1_raportti.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaavamaaraysavustaja.core.convert import convert_units  # noqa: E402
from kaavamaaraysavustaja.core.evaluation import evaluate, percent, structure_of  # noqa: E402
from kaavamaaraysavustaja.core.ingest import parse  # noqa: E402
from kaavamaaraysavustaja.core.policy import PolicyLibrary  # noqa: E402
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase  # noqa: E402

GOLDEN_TEXT = ROOT / "tests" / "golden" / "kartta1_otos.txt"
GOLDEN_EXPECTED = ROOT / "tests" / "golden" / "kartta1_odotetut.yaml"


def run(text_path: Path = GOLDEN_TEXT, expected_path: Path = GOLDEN_EXPECTED):
    kb = KnowledgeBase.load()
    units = parse(text_path.read_text(encoding="utf-8")).units
    project = convert_units(kb, units, PolicyLibrary.load().resolve(), name="testiaineisto v1")
    expected = yaml.safe_load(expected_path.read_text(encoding="utf-8"))
    return project, evaluate(project, expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yksikot", action="store_true", help="tulosta myös yksikkökohtainen taulukko")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    project, evaluation = run()
    print("| Mittari | Tulos |")
    print("|---|---|")
    for name, value in evaluation.metrics().items():
        print(f"| {name} | {percent(value)} |")
    print(f"| sanallisen tekstin poikkeamat (R-19) | {evaluation.text_changes} |")
    if evaluation.unmatched:
        print(f"\nOdotuksia ilman yksikköä: {', '.join(evaluation.unmatched)}")
    if args.yksikot:
        print("\n| Yksikkö | Rakenne | Odotettu | Oikein | Puuttuvat kysymykset | Sellaisenaan |")
        print("|---|---|---|---|---|---|")
        for r in evaluation.results:
            print(
                f"| {r.unit.letter_code or ''} {r.unit.heading} | {', '.join(structure_of(r.unit.proposal)) or '–'} | "
                f"{', '.join(r.expected.get('rakenne', [])) or '–'} | {'kyllä' if r.structure_ok else 'ei'} | "
                f"{', '.join(sorted(r.missing_questions)) or '–'} | {'kyllä' if r.automatable else 'ei'} |"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
