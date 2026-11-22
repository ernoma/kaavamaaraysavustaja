"""Test the Syke public Ryhti plan validation API (Ryhti Plan Public Validate API).

Usage::

    $env:RYHTI_API_KEY = "<avain>"                       # PowerShell; never commit the key
    python tools/syke_validate.py                         # minimal synthetic yleiskaava (Tampere 837)
    python tools/syke_validate.py --plan oma_kaava.json --plan-type 23
    python tools/syke_validate.py --dry-run               # print the request, do not send

The key is read from the environment variable ``RYHTI_API_KEY`` and sent in the
``Ocp-Apim-Subscription-Key`` header. Standard library only (works in the QGIS Python
environment); a proxy is taken from ``HTTPS_PROXY`` like any urllib request.

API description: lahtoaineistot/ryhti-openapi/ryhti-plan-public-validate-api.json
(sykefi/Ryhti-rajapintakuvaukset, OpenApi/Alueidenkäyttö/Avoin, CC BY 4.0).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

DEFAULT_URL = "https://api.ymparisto.fi/ryhti/plan-public/api/Plan/Validate"
ENV_KEY = "RYHTI_API_KEY"
URI = "http://uri.suomi.fi/codelist/rytj/"


def minimal_plan() -> dict:
    """A minimal synthetic yleiskaava with one regulation group (C) and one plan object.

    Code values for life cycle and underground status are assumptions to be checked against
    the validation response (kaavaelinkaari 03 = valmistelu, RY_MaanalaisuudenLaji 01 = maanpäällinen).
    """
    lifecycle = URI + "kaavaelinkaari/code/03"
    group_key = str(uuid.uuid4())
    object_key = str(uuid.uuid4())
    area = {
        "srid": "3067",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [327000.0, 6822000.0],
                    [328000.0, 6822000.0],
                    [328000.0, 6823000.0],
                    [327000.0, 6823000.0],
                    [327000.0, 6822000.0],
                ]
            ],
        },
    }
    return {
        "planKey": str(uuid.uuid4()),
        "lifeCycleStatus": lifecycle,
        "legalEffectOfLocalMasterPlans": [URI + "oikeusvaik_YK/code/1"],
        "scale": 10000,
        "geographicalArea": area,
        "planDescription": "Kaavamääräysavustajan testikaava (synteettinen, ei oikea kaava)",
        "planObjects": [
            {
                "planObjectKey": object_key,
                "lifeCycleStatus": lifecycle,
                "undergroundStatus": URI + "RY_MaanalaisuudenLaji/code/01",
                "geometry": area,
                "name": {"fin": "Testialue"},
            }
        ],
        "planRegulationGroups": [
            {
                "planRegulationGroupKey": group_key,
                "titleOfPlanRegulation": {"fin": "Keskustatoimintojen alue"},
                "letterIdentifier": "C",
                "groupNumber": 1,
                "planRegulations": [
                    {
                        "planRegulationKey": str(uuid.uuid4()),
                        "lifeCycleStatus": lifecycle,
                        "type": URI + "RY_Kaavamaarayslaji/code/keskustatoimintojenAlue",
                        "additionalInformations": [
                            {"type": URI + "RY_Kaavamaarayksen_Lisatiedonlaji/code/paakayttotarkoitus"}
                        ],
                    }
                ],
            }
        ],
        "planRegulationGroupRelations": [{"planObjectKey": object_key, "planRegulationGroupKey": group_key}],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, help="Ryhti-kaava JSON (oletus: synteettinen testikaava)")
    parser.add_argument("--plan-type", default="21", help="RY_Kaavalaji-koodi, esim. 21 (yleiskaava)")
    parser.add_argument("--area", default="837", help="kunta- tai maakuntakoodi (Tampere 837)")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--dry-run", action="store_true", help="tulosta pyyntö, älä lähetä")
    parser.add_argument("--out", type=Path, help="tallenna vastaus tiedostoon")
    args = parser.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else minimal_plan()
    plan_type = (
        args.plan_type if args.plan_type.startswith("http") else URI + "RY_Kaavalaji/code/" + args.plan_type
    )
    query = urllib.parse.urlencode({"planType": plan_type, "administrativeAreaIdentifiers": args.area})
    url = f"{args.url}?{query}"
    body = json.dumps(plan, ensure_ascii=False).encode("utf-8")

    if args.dry_run:
        print("POST", url)
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return 0

    key = os.environ.get(ENV_KEY)
    if not key:
        print(f"Aseta API-avain ympäristömuuttujaan {ENV_KEY} (ks. docs/vaihe0_kayttajan_tehtavat.md).")
        return 2

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Ocp-Apim-Subscription-Key": key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, text = response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode("utf-8", "replace")
    except urllib.error.URLError as error:
        print(f"Yhteysvirhe: {error.reason} (tarkista välityspalvelin: HTTPS_PROXY)")
        return 3

    meaning = {
        200: "kaavassa ei virheitä",
        400: "kutsun rakenne ei ole skeeman mukainen",
        401: "API-avain puuttuu tai on väärä",
        403: "avaimella ei ole oikeutta tähän rajapintaan",
        422: "kutsun tietosisällössä virheitä (odotettu synteettiselle testikaavalle)",
    }.get(status, "")
    print(f"HTTP {status} {meaning}")
    try:
        parsed = json.loads(text)
        text = json.dumps(parsed, ensure_ascii=False, indent=1)
    except json.JSONDecodeError:
        pass
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    # 200 and 422 both prove that the key and the connection work.
    return 0 if status in (200, 400, 422) else 1


if __name__ == "__main__":
    sys.exit(main())
