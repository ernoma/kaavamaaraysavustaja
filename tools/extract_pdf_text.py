"""Extract the text of a legend PDF into a local text file for ``kma convert`` (ADR-0009).

Usage::

    python tools/extract_pdf_text.py lahtoaineistot/Voimassa_olevat_*.pdf
    python tools/extract_pdf_text.py kooste.pdf --out work/kooste.txt --pages 2-4

The output keeps the PDF line layout and adds ``@sivu N`` lines. It is a local working
copy: check and correct it (blank line = paragraph or heading break, ``@osio``,
``@merkinta`` … see ADR-0009) before converting. The default output folder ``work/`` is
git-ignored; never commit the extracted text of a whole compilation.

``pypdf`` (BSD) is a development dependency only; the core never imports a PDF library
and the PDF is never sent to a language model (CLAUDE.md rules 1 and 5).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def page_range(spec: str | None, count: int) -> list[int]:
    if not spec:
        return list(range(1, count + 1))
    pages: list[int] = []
    for part in spec.split(","):
        start, _, end = part.partition("-")
        pages += list(range(int(start), int(end or start) + 1))
    return [p for p in pages if 1 <= p <= count]


def extract(pdf: Path, pages: str | None = None) -> str:
    from pypdf import PdfReader  # development-only dependency

    reader = PdfReader(pdf)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    lines = [
        f"# Poimittu: {pdf.name} (sha256 {digest}), tools/extract_pdf_text.py",
        "# Tarkista ja korjaa teksti ennen muuntamista (ADR-0009). Älä committaa.",
    ]
    for number in page_range(pages, len(reader.pages)):
        lines.append(f"@sivu {number}")
        text = reader.pages[number - 1].extract_text() or ""
        lines += text.replace("\r\n", "\n").split("\n")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, help="tekstitiedosto (oletus work/<pdf-nimi>.txt)")
    parser.add_argument("--pages", help="sivut, esim. 2-4 tai 3,5-6 (oletus kaikki)")
    args = parser.parse_args(argv)
    out = args.out or ROOT / "work" / (args.pdf.stem + ".txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(extract(args.pdf, args.pages), encoding="utf-8")
    print(f"Teksti kirjoitettu: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
