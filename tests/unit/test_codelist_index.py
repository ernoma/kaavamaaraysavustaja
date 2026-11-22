from datetime import date

import pytest

from kaavamaaraysavustaja.knowledge import load_manifest
from kaavamaaraysavustaja.knowledge.codelists import (
    ADDITIONAL_INFO_TYPE,
    REGULATION_TYPE,
    VERBAL_REGULATION_TYPE,
)

DAY = date(2026, 11, 22)


def test_manifest_checksums_match():
    manifest = load_manifest(verify=True)
    assert manifest["tietopohja"] == "TP-2026.11-3"
    assert manifest["koodistot"][REGULATION_TYPE]["versio"] == "2025-10-07"


def test_code_counts(index):
    assert len(index.codes(REGULATION_TYPE)) == 268
    assert len(index.codes(ADDITIONAL_INFO_TYPE)) == 52
    assert len(index.codes(VERBAL_REGULATION_TYPE)) == 39


def test_extension_member_counts(index):
    extensions = index.data["codelists"][REGULATION_TYPE]["extensions"]
    counts = {name: ext["member_count"] for name, ext in extensions.items()}
    assert counts == {
        "aluevaraus": 92,
        "asemakaava": 233,
        "maakuntakaava": 110,
        "suure": 46,
        "yleiskaava": 200,
    }


def test_keskustatoimintojen_alue(index):
    code = index.get(REGULATION_TYPE, "keskustatoimintojenAlue")
    assert code.is_valid and not code.header_level
    assert code.name["fi"] == "Keskustatoimintojen alue"
    assert code.name["sv"]
    assert code.in_extension("aluevaraus", DAY)
    assert code.in_extension("yleiskaava", DAY)
    assert not code.in_extension("suure", DAY)


def test_header_level_codes(index):
    code = index.get(REGULATION_TYPE, "alueJotaKoskeeKehittamisperiaate")
    assert code.header_level
    assert index.get(ADDITIONAL_INFO_TYPE, "tyyppi").header_level
    assert index.get(VERBAL_REGULATION_TYPE, "maarayksenTyyppi").header_level
    assert not index.get(REGULATION_TYPE, "asumisenAlue").header_level


def test_retired_codes(index):
    retired = {c.value for c in index.codes(REGULATION_TYPE) if c.status == "RETIRED"}
    assert retired == {
        "valtakunnallisestiArvokasMaisemaAlue",
        "kunnanTaiKaupunginOsa",
        "rakennusalaJolleSaaSijoittaaTalousrakennuksen",
        "rakennusalaJolleSaaSijoittaaSaunan",
        "valtakunnallisestiMerkittavaRakennettuKulttuuriymparisto",
        "valtakunnallisestiMerkittavaArkeologinenKohde",
        "muuArkeologinenKohde",
    }
    assert all(index.get(REGULATION_TYPE, v).end_date == "2025-06-18" for v in retired)


def test_ended_extension_membership(index):
    code = index.get(REGULATION_TYPE, "muuArkeologinenKohde")
    assert code.in_extension("yleiskaava", date(2025, 1, 1))
    assert not code.in_extension("yleiskaava", DAY)


def test_hierarchy_and_uri_lookup(index):
    code = index.get(REGULATION_TYPE, "arkeologinenKohde")
    assert code.parent == "merkittavaRakennettuKulttuuriymparisto"
    assert index.by_uri(code.uri) is code
    assert code.uri == "http://uri.suomi.fi/codelist/rytj/RY_Kaavamaarayslaji/code/arkeologinenKohde"


@pytest.mark.parametrize("codelist", [REGULATION_TYPE, ADDITIONAL_INFO_TYPE, VERBAL_REGULATION_TYPE])
def test_usable_codes_exclude_retired_and_header(index, codelist):
    usable = index.usable_codes(codelist)
    assert usable
    assert all(c.is_valid and not c.header_level for c in usable)
