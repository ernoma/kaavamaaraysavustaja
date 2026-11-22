"""Normalization and parsing of the Tampere compilation format (ADR-0009).

The snippets are short excerpts of the compilation as extracted by tools/extract_pdf_text.py.
"""

from kaavamaaraysavustaja.core.ingest import (
    content_skeleton,
    dedupe_code,
    is_code_token,
    normalization_preserves_content,
    normalize_lines,
    normalize_text,
    parse,
    parse_source_plans,
    select_map,
)

RAW_PAGE = """\
@sivu 3
KANTAKAUPUNGIN YLEISKAAVAYHDISTELMÄ⎵
Kantakaupungin vaiheyleiskaava - valtuustokausi 2017–2021 (9.6.2023), Kantakaupungin yleiskaava 2040 (20.1.2020)
KARTTA 1 - YHDYSKUNTARAKENNE
Kaavamerkinnät ja -määräykset
YLEISMÄÄRÄYS
Yleiskaavan ohjausvaikutus, tuulivoimarakentaminen⎵
ja kaupan ohjaus
Yleiskaavan käyttötarkoitusalueilla voidaan sallia käyt -
tötarkoituksesta poikkeavaa rakentamista.
MAANKÄYTTÖ
KESKUSTATOIMINTOJEN ALUE
Alue varataan julkisille ja yksityisille palveluille, työpaik-
katoiminnoille sekä monipuolisesti virkistyksen, vapaa-
ajan ja kaupunkikulttuurin toiminnoille. Rakennusten julkiseen kau -
⎵
punkitilaan avautuvat tilat.
c-1 TÄYDENTYVÄ KESKUSTA
Vähittäiskaupan kerrosalan⎵
enimmäismitoitus Kalevassa on  70 000 k-m².
 km ALUE, JOLLE SAA SIJOITTAA SEUDULLISTA⎵
PALJON TILAA VAATIVAA KAUPPAA
Alueelle voidaan sijoittaa kauppaa.
VESIALUE
VAK -RATAPIHA
Järjestelyratapihan alueella on riski.
KARTTA 1 - YHDYSKUNTARAKENNE
ERITASOLllTTYMÄ
pvpv
POHJAVESIALUE
Aluetta koskevat toimenpiteet.
"""
# Trailing spaces matter in the PDF layout; ⎵ marks them so that editors keep them.
PAGE = RAW_PAGE.replace("⎵", " ")


def units_by_heading(text=PAGE):
    return {u.heading: u for u in parse(text).units}


def test_parse_units_and_metadata():
    result = parse(PAGE)
    assert result.warnings == []
    assert result.maps == {"Kartta 1 - Yhdyskuntarakenne": "1"}
    headings = [u.heading for u in result.units]
    assert headings == [
        "Yleiskaavan ohjausvaikutus, tuulivoimarakentaminen ja kaupan ohjaus",
        "KESKUSTATOIMINTOJEN ALUE",
        "TÄYDENTYVÄ KESKUSTA",
        "ALUE, JOLLE SAA SIJOITTAA SEUDULLISTA PALJON TILAA VAATIVAA KAUPPAA",
        "VESIALUE",
        "VAK -RATAPIHA",
        "ERITASOLIITTYMÄ",
        "POHJAVESIALUE",
    ]
    general = result.units[0]
    assert general.kind == "yleismaarays"
    assert general.page == 3
    assert [p.name for p in general.source_plans] == [
        "Kantakaupungin vaiheyleiskaava - valtuustokausi 2017–2021",
        "Kantakaupungin yleiskaava 2040",
    ]
    assert general.source_plans[1].date == "20.1.2020"
    c = units_by_heading()["KESKUSTATOIMINTOJEN ALUE"]
    assert c.section_path == ["MAANKÄYTTÖ"]
    assert c.map == "Kartta 1 - Yhdyskuntarakenne"
    assert c.letter_code is None


def test_letter_codes():
    units = units_by_heading()
    assert units["TÄYDENTYVÄ KESKUSTA"].letter_code == "c-1"
    assert units["ALUE, JOLLE SAA SIJOITTAA SEUDULLISTA PALJON TILAA VAATIVAA KAUPPAA"].letter_code == "km"
    pv = units["POHJAVESIALUE"]
    assert (pv.letter_code_raw, pv.letter_code) == ("pvpv", "pv")
    assert any(c.kind == "kaksoistunnus" and c.needs_confirmation for c in pv.normalization_diff)
    assert units["VESIALUE"].normalized_text == ""
    assert units["VAK -RATAPIHA"].letter_code is None


def test_code_tokens():
    for token in ["c-1", "km", "R(200)", "E-jv", "Mu", "sv-1", "Saa-2", "ge-1", "Vu", "pvpv", "sm-2sm-2"]:
        assert is_code_token(token), token
    for token in ["VAK", "C", "Liikkuminen", "Asuminen", "-KOHDE", "1."]:
        assert not is_code_token(token), token
    assert dedupe_code("sm-2sm-2") == ("sm-2", True)
    assert dedupe_code("km") == ("km", False)


def test_hyphenation_and_column_break():
    c = units_by_heading()["KESKUSTATOIMINTOJEN ALUE"]
    assert c.normalized_text == (
        "Alue varataan julkisille ja yksityisille palveluille, työpaikkatoiminnoille sekä monipuolisesti "
        "virkistyksen, vapaa-ajan ja kaupunkikulttuurin toiminnoille. Rakennusten julkiseen "
        "kaupunkitilaan avautuvat tilat."
    )
    kinds = [(ch.kind, ch.needs_confirmation) for ch in c.normalization_diff]
    assert ("tavutus", False) in kinds
    assert ("tavutus_yhdysmerkki", True) in kinds  # vapaa-|ajan: same vowel keeps the hyphen
    assert c.raw_text.count("\n") == 4  # raw text is kept as such


def test_space_hyphen_and_double_space():
    general = parse(PAGE).units[0]
    assert general.normalized_text.startswith(
        "Yleiskaavan käyttötarkoitusalueilla voidaan sallia käyttötarkoituksesta"
    )
    c1 = units_by_heading()["TÄYDENTYVÄ KESKUSTA"]
    assert c1.normalized_text == "Vähittäiskaupan kerrosalan enimmäismitoitus Kalevassa on 70 000 k-m²."
    assert [ch.kind for ch in c1.normalization_diff] == ["valilyonti"]


def test_suspicious_letters_corrected_and_flagged():
    unit = units_by_heading()["ERITASOLIITTYMÄ"]
    assert unit.heading_raw == "ERITASOLllTTYMÄ"
    change = unit.normalization_diff[0]
    assert (change.kind, change.part, change.needs_confirmation) == ("epailyttava_korjaus", "otsikko", True)


def test_flags_without_change():
    norm = normalize_text("kuten MRL128 §:ssä ja vapaaajan alueet..")
    assert norm.text == "kuten MRL128 §:ssä ja vapaaajan alueet.."
    notes = {c.note for c in norm.changes}
    assert len(notes) == 3 and all(c.needs_confirmation for c in norm.changes)


def test_soft_hyphen_and_zero_width():
    norm = normalize_lines([(1, "S­EKOITTUNUT al​ue")])
    assert norm.text == "SEKOITTUNUT alue"
    assert [c.kind for c in norm.changes] == ["pehmea_tavuviiva", "nollalevea_merkki"]


def test_trailing_hyphen_with_space_is_a_real_hyphen():
    norm = normalize_lines(
        [(1, "Suunnittelussa tulee varmistaa virkistys- "), (2, "ja ulkoilureittien jatkuvuus.")]
    )
    assert norm.text == "Suunnittelussa tulee varmistaa virkistys- ja ulkoilureittien jatkuvuus."
    assert norm.changes == []


def test_blank_line_is_paragraph_break():
    norm = normalize_lines([(1, "Ensimmäinen kappale."), (2, ""), (3, "Toinen kappale.")])
    assert norm.text == "Ensimmäinen kappale.\n\nToinen kappale."


def test_content_preserved():
    for unit in parse(PAGE).units:
        assert normalization_preserves_content(unit.raw_text, unit.normalized_text, unit.normalization_diff)
    assert not normalization_preserves_content("Alue varataan.", "Alue varattiin.", [])
    assert content_skeleton("käyt -\ntötarkoitus") == "käyttötarkoitus"


def test_select_map_and_duplicates():
    text = PAGE + "@sivu 6\nKARTTA 2 - VIHERYMPÄRISTÖ\nKaavamerkinnät ja -määräykset\nVESIALUE\n"
    result = parse(text)
    assert len(select_map(result, "1")) == 8
    second = select_map(result, "viherympäristö")
    assert [u.heading for u in second] == ["VESIALUE"]
    first_vesialue = units_by_heading()["VESIALUE"]
    assert second[0].duplicates_of == first_vesialue.id


def test_select_map_errors():
    import pytest

    with pytest.raises(ValueError, match="Kartat"):
        select_map(parse(PAGE), "9")


def test_directives():
    text = """\
@kartta Kartta 1 - Testi
@lahdekaavat Testikaava|1.1.2020; Toinen kaava
@osio LIIKENNEJÄRJESTELMÄ
VESIVÄYLÄ⎵

PYÖRÄLIIKENTEEN SEUDULLINEN⎵
 PÄÄREITISTÖ
Pyöräliikenteen pääreitistöä kehitetään.
@geometria viiva
@merkinta RAITIOTIE
@yleismaarays Hulevedet
Hulevedet on viivytettävä.
"""
    result = parse(text.replace("⎵", " "))
    units = {u.heading: u for u in result.units}
    assert list(units) == ["VESIVÄYLÄ", "PYÖRÄLIIKENTEEN SEUDULLINEN PÄÄREITISTÖ", "RAITIOTIE", "Hulevedet"]
    assert units["VESIVÄYLÄ"].section_path == ["LIIKENNEJÄRJESTELMÄ"]
    assert units["RAITIOTIE"].geometry_hint == "viiva"
    assert [(p.name, p.date) for p in units["RAITIOTIE"].source_plans] == [
        ("Testikaava", "1.1.2020"),
        ("Toinen kaava", None),
    ]
    assert units["Hulevedet"].kind == "yleismaarays"
    assert units["Hulevedet"].normalized_text == "Hulevedet on viivytettävä."


def test_general_regulation_without_title():
    text = "YLEISMÄÄRÄYS\nViheralueverkoston jatkuvuus ja virkistys-\nverkoston toimivuus tulee turvata.\n"
    unit = parse(text).units[0]
    assert unit.heading is None
    assert (
        unit.normalized_text == "Viheralueverkoston jatkuvuus ja virkistysverkoston toimivuus tulee turvata."
    )


def test_parse_source_plans():
    plans = parse_source_plans("Kantakaupungin yleiskaava 2040 (20.1.2020)")
    assert [(p.name, p.date) for p in plans] == [("Kantakaupungin yleiskaava 2040", "20.1.2020")]
