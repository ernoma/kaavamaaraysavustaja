"""Test the Syke public Ryhti plan validation API (Ryhti Plan Public Validate API).

Usage::

    python tools/syke_validate.py                         # test env, synthetic yleiskaava (Tampere 837)
    python tools/syke_validate.py --env prod              # production (needs a production key)
    python tools/syke_validate.py --plan oma_kaava.json --plan-type 23
    python tools/syke_validate.py --dry-run               # print the request, do not send

The key is read from the environment variable ``RYHTI_API_KEY`` (on Windows also from the
user environment in the registry, so a key saved with ``SetEnvironmentVariable(..., 'User')``
works without restarting the shell) and sent in the ``Ocp-Apim-Subscription-Key`` header.
Never commit the key. Standard library only (works in the QGIS Python
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

BASE_URLS = {
    "test": "https://api-test.ymparisto.fi/ryhti/plan-public",
    "prod": "https://api.ymparisto.fi/ryhti/plan-public",
}
VALIDATE_PATH = "/api/Plan/Validate"
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


def _windows_user_env(name: str) -> str | None:
    """Read a user environment variable set after this shell was started (Windows only)."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0] or None
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, help="Ryhti-kaava JSON (oletus: synteettinen testikaava)")
    parser.add_argument("--plan-type", default="21", help="RY_Kaavalaji-koodi, esim. 21 (yleiskaava)")
    parser.add_argument("--area", default="837", help="kunta- tai maakuntakoodi (Tampere 837)")
    parser.add_argument(
        "--env", choices=sorted(BASE_URLS), default="test", help="Syken ympäristö (oletus: test)"
    )
    parser.add_argument("--url", help="oma perusosoite tai koko Validate-osoite (ohittaa --env)")
    parser.add_argument("--dry-run", action="store_true", help="tulosta pyyntö, älä lähetä")
    parser.add_argument("--out", type=Path, help="tallenna vastaus tiedostoon")
    args = parser.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else minimal_plan()
    # The query parameter takes the bare code value ("21"); a full code URI is rejected with
    # quality__req_invalid_query_param (tested 22.11.2026). Accept a URI and strip it.
    plan_type = args.plan_type.rstrip("/").rsplit("/", 1)[-1]
    query = urllib.parse.urlencode({"planType": plan_type, "administrativeAreaIdentifiers": args.area})
    base = (args.url or BASE_URLS[args.env]).rstrip("/")
    if not base.endswith(VALIDATE_PATH):
        base += VALIDATE_PATH
    url = f"{base}?{query}"
    body = json.dumps(plan, ensure_ascii=False).encode("utf-8")

    if args.dry_run:
        print("POST", url)
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return 0

    key = os.environ.get(ENV_KEY) or _windows_user_env(ENV_KEY)
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
