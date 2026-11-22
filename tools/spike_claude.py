"""Phase 0 spike: convert one example regulation with Claude structured outputs.

Usage::

    python tools/spike_claude.py                 # dry run with the test adapter (no network)
    python tools/spike_claude.py --live          # real call; needs ANTHROPIC_API_KEY
    python tools/spike_claude.py --live --out tests/recorded_llm/spike_c1.json

Only the regulation text below is sent to the model (never PDFs). The live run costs about
0.05-0.15 USD with claude-opus-5-5 (plan 6.8). Results are printed; nothing is stored
unless ``--out`` is given.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from kaavamaaraysavustaja.core.llm import StructuredRequest  # noqa: E402
from kaavamaaraysavustaja.core.llm.fake import FakeProvider  # noqa: E402
from kaavamaaraysavustaja.core.llm.schema import code_enums, conversion_schema  # noqa: E402
from kaavamaaraysavustaja.knowledge import CodelistIndex, knowledge_dir, load_manifest  # noqa: E402
from kaavamaaraysavustaja.knowledge.codelists import (  # noqa: E402
    ADDITIONAL_INFO_TYPE,
    REGULATION_TYPE,
    VERBAL_REGULATION_TYPE,
)

# Plan chapter 8.2 (Tampere, kantakaupungin yleiskaavamerkinnät 2025).
EXAMPLE = {
    "otsikko": "TÄYDENTYVÄ KESKUSTA",
    "kirjaintunnus": "c-1",
    "polku": "Kartta 1 > Maankäyttö",
    "geometriavihje": "alue",
    "teksti": (
        "Aluetta kehitetään täydennettävänä keskustatoimintojen alueena. Täydentämisen tulee edistää "
        "toimintojen monipuolisuutta ja keskustojen elinvoimaisuutta. Kaukajärven keskusta-alueelle ei "
        "saa sijoittaa seudullisia vähittäiskaupan suuryksiköitä. Vähittäiskaupan kerrosalan "
        "enimmäismitoitus Kalevassa on 70 000 k-m²."
    ),
}

SYSTEM = """Olet Katja-asetuksen (YM 311/2024) ja Ryhti-tietomallin asiantuntija-avustaja.
Muunnat voimassa olevan yleiskaavan sanallisen kaavamääräyksen rakenteiseksi
kaavamääräysryhmäksi.

Ehdottomat säännöt:
- VOOKA-tila: sanallista tekstiä ei muuteta. Sanallisen määräyksen arvo on lähdeteksti sellaisenaan.
- Käytä vain skeeman sallimia koodeja.
- Jos tulkinta on epävarma, älä arvaa: lisää tulkintakysymys (tyypit K1–K15) vaihtoehtoineen.
- Perustele jokainen valinta lainauksella, joka on lähdetekstin osamerkkijono.
- Aluemaisen kohteen ryhmässä muilla kuin sanallisilla määräyksillä on sama lisätieto:
  pääkäyttötarkoitus tai osa-alue. Kehittämisvyöhykkeeseen liittyy aina sanallinen
  suunnittelumääräys.
Vastaa vain skeeman mukaisella JSONilla."""


def static_context(index: CodelistIndex, plan_level: str) -> str:
    enums = code_enums(index, plan_level)

    def lines(codelist: str, values: list[str]) -> str:
        return "\n".join(f"- {v}: {index.get(codelist, v).name.get('fi', '')}" for v in values)

    annex = yaml.safe_load((knowledge_dir() / "katja" / "annex4_katja-ii_393-2025.yaml").read_text("utf-8"))
    annex_lines = []
    for entry in annex["kaavalajit"][plan_level]:
        infos = ", ".join(str(i.get("laji")) for i in entry["lisatiedot"])
        codes = ", ".join(str(c) for c in entry["kaavamaarayslajit"])
        annex_lines.append(f"- {entry.get('kirjaintunnus') or '–'} {entry.get('otsikko')}: {codes} [{infos}]")
    return (
        f"Kaavataso: {plan_level}\n\n## Kaavamääräyslajit\n{lines(REGULATION_TYPE, enums['regulation_types'])}\n\n"
        f"## Lisätiedon lajit\n{lines(ADDITIONAL_INFO_TYPE, enums['additional_info_types'])}\n\n"
        f"## Sanallisen määräyksen lajit\n{lines(VERBAL_REGULATION_TYPE, enums['verbal_types'])}\n\n"
        "## Katja-asetuksen liitteen 4 vakiomääräykset (tunnus otsikko: kaavamääräyslajit [lisätiedot])\n"
        + "\n".join(annex_lines)
    )


def fake_answer(request: StructuredRequest) -> dict:
    return {
        "ryhmat": [
            {
                "otsikko": "Täydentyvä keskusta",
                "kirjaintunnus": "c-1",
                "ryhmatyyppi": "kaavakohde",
                "geometria": ["alue"],
                "maaraykset": [
                    {
                        "laji": "kehittamisvyohyke",
                        "arvo": None,
                        "lisatiedot": [
                            {"laji": "osaAlue", "arvo": None},
                            {"laji": "kayttotarkoituskohdistus", "arvo": "keskustatoimintojenAlue"},
                        ],
                        "sanallisen_lajit": [],
                        "tekstiviitteet": [],
                    },
                    {
                        "laji": "suunnittelumaarays",
                        "arvo": EXAMPLE["teksti"],
                        "lisatiedot": [],
                        "sanallisen_lajit": ["kehittamisperiaate", "taydennysrakentaminen", "kaupanOhjaus"],
                        "tekstiviitteet": ["Aluetta kehitetään täydennettävänä keskustatoimintojen alueena."],
                    },
                ],
                "suositukset": [],
            }
        ],
        "perustelut": [],
        "vaihtoehdot": [],
        "tulkintakysymykset": [],
        "kokonaisvarmuus": "matala",
    }


def check_quotes(data: dict) -> list[str]:
    """Quotes must be substrings of the source text (plan 6.9)."""
    quotes = [p["lainaus"] for p in data.get("perustelut", [])]
    for group in data.get("ryhmat", []):
        for regulation in group.get("maaraykset", []):
            quotes += regulation.get("tekstiviitteet", [])
    return [q for q in quotes if q and q not in EXAMPLE["teksti"] and q not in EXAMPLE["otsikko"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="kutsu Claude API:a (vaatii avaimen)")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--out", type=Path, help="tallenna vastaus ja käyttötiedot JSON-tiedostoon")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    index = CodelistIndex.load()
    request = StructuredRequest(
        system=SYSTEM,
        static_context=static_context(index, "yleiskaava"),
        task_input=json.dumps(EXAMPLE, ensure_ascii=False, indent=1),
        json_schema=conversion_schema(index, "yleiskaava"),
        quality=args.quality,
        metadata={"tietopohja": manifest["tietopohja"]},
    )
    if args.live:
        from kaavamaaraysavustaja.core.llm.claude import ClaudeProvider

        provider = ClaudeProvider(model=args.model)
    else:
        provider = FakeProvider(fake_answer)
        print("Kuivaharjoitus testiadapterilla (lisää --live oikeaan kutsuun).")

    started = time.monotonic()
    response = provider.generate_structured(request)
    elapsed = time.monotonic() - started
    print(json.dumps(response.data, ensure_ascii=False, indent=1))
    print(f"\nmalli={response.model_id} stop_reason={response.stop_reason} aika={elapsed:.1f}s")
    print(f"tokenit: {response.usage}")
    bad = check_quotes(response.data)
    print(
        "Lainaukset: kaikki löytyvät lähdetekstistä." if not bad else f"Lainauksia ei löydy lähteestä: {bad}"
    )
    for warning in response.warnings:
        print("Varoitus:", warning)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "tietopohja": manifest["tietopohja"],
            "malli": response.model_id,
            "laatu": args.quality,
            "syote": EXAMPLE,
            "vastaus": response.data,
            "kaytto": response.usage.__dict__,
            "kesto_s": round(elapsed, 1),
        }
        args.out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("Tallennettu", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
