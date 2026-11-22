# ADR-0002 Riippuvuuksien toimitus QGISiin

- Tila: **avoin** (päätös tehdään Tampereen työasematestin jälkeen, vaihe 0)
- Lähde: toteutussuunnitelma 6.3 ("Riippuvuuksien toimitus QGISiin"), riski "SDK-riippuvuuksien
  asennus tai välityspalvelin estää käytön"

## Tausta

Kielimalliadapterit käyttävät virallisia SDK:ita (`anthropic`, myöhemmin `mistralai`). QGIS ei
asenna lisäosien pip-riippuvuuksia. SDK:illa on käännettyjä riippuvuuksia (`pydantic-core`,
`jiter`), joiden on vastattava QGISin Python-versiota (OSGeo4W, QGIS 3.40: Python 3.12).
Tampereen työasemat ovat välityspalvelimen takana, ja käyttäjillä ei välttämättä ole
oikeutta asentaa ohjelmistoja.

Ydin toimii ilman SDK:ita (sääntöpohjainen tila), joten ongelma koskee vain kielimallitilaa.

## Vaihtoehdot

| | Vaihtoehto | Plussat | Miinukset |
|---|---|---|---|
| A | Käyttäjä tai ylläpito asentaa `pip install --user` OSGeo4W Shellissä | yksinkertaisin | vaatii komentorivin ja proxy-asetukset; päivitykset käsin |
| B | QPIP-tyyppinen asennus (lisäosa asentaa `requirements.txt`:n QGISin käynnistyessä) | käyttäjälle helppo | uusi riippuvuus (QPIP-lisäosa); verkko- ja oikeusongelmat käynnistyksessä |
| C | Lisäosan oma asennusapuri (napista `pip install --target <profiili>/python/kma_deps`) | hallittu, näkyvä, ei admin-oikeuksia | toteutettava ja testattava itse |
| D | Paketit lisäosan mukana (vendoring, wheelit zipissä) | toimii ilman verkkoa ja pipiä | iso zip, alustakohtaiset wheelit, päivitysvastuu, lisenssiselvitys |
| E | Ei SDK:ta: kutsut Qt:n `QNetworkAccessManager`illa (kuten Arho) | ei riippuvuuksia, QGISin proxy-asetukset suoraan | poikkeaa linjauksesta "virallinen SDK" (A6); rakenteisen tulosteen, uudelleenyritysten ja virheiden käsittely itse |

## Ratkaisua varten tarvittava tieto

Tampereen työasematesti (`docs/vaihe0_kayttajan_tehtavat.md`, tehtävä 1): toimiiko A
välityspalvelimen takana, toimiiko `--target` (C), ja tavoittaako SDK rajapinnat QGISin
proxy-asetuksilla. Tulokset kirjataan tähän ADR:ään.

## Työasematestin tulokset 22.11.2026

Tampereen työasema: Windows 10, OSGeo4W, QGIS 3.44.7-Solothurn, Python 3.12.12, pip 24.0,
OpenSSL 3.0.18. Välityspalvelinta ei tarvita tällä työasemalla, joten välityspalvelimen kautta
kulkevaa liikennettä ei testattu.

| Kohta | Tulos |
|---|---|
| `pip install --target …\profiles\default\python\kma_deps` (C) | onnistui; `anthropic` 2.12.0, `mistralai` 3.8.0 ja 17 riippuvuutta |
| `pip install --user` (A) | `--dry-run` onnistui; asennusta ei tehty, koska käyttäjäkansio on jo muiden työkalujen käytössä (`requests`, `pymupdf` ym.) |
| Käännetyt paketit (`pydantic_core` 2.50.5, `jiter` 0.19.0) | valmiit `cp312-win_amd64`-wheelit (`--only-binary=:all:`), ei kääntäjää |
| QGISin mukana tulevat paketit | QGIS ei sisällä `pydantic`-, `httpx`- eikä `typing_extensions`-pakettia; päällekkäisiä ovat vain `python-dateutil` (QGIS 2.9.0, kma_deps 4.0.0) ja `idna` (3.18 / 3.20) |
| Yhteydet OSGeo4W-komentoriviltä | Claude 401, Mistral 401, Syke-testi 401 (= tavoitettavissa) |
| Tuonti QGIS-prosessissa (`python-qgis`, `QgsApplication`) | `anthropic`, `mistralai.client.Mistral` ja `pydantic` toimivat; SDK:n kutsu virheellisellä avaimella → odotettu `AuthenticationError` |
| Varmenteet | ei lisäasetuksia; OSGeo4W asettaa `SSL_CERT_FILE`-muuttujan itse, ja `httpx2` käyttää `truststore`a |
| Claude-live-ajo kehitysympäristön venvistä | onnistui (ADR-0005) |

**Havainto polkujärjestyksestä:** jos `kma_deps` lisätään `sys.path`in alkuun, sen
`dateutil` 4.0.0 ja `idna` 3.20 peittävät QGISin versiot. Lisäosan kannattaa siksi lisätä kansio
polun **loppuun** (`sys.path.append`). Testattu: tällöin QGISin `dateutil` 2.9.0 säilyy ja SDK:t
toimivat silti, koska niiden muita riippuvuuksia ei ole QGISissa. Vaihtoehtoisesti asennus
tehdään rajoitetiedostolla (`pip freeze` QGISin ympäristöstä → `-c`), jolloin päällekkäiset
paketit ovat samoja versioita.

## Alustava suositus

C (oma asennusapuri `--target`-kansioon, kansio polun loppuun) ja A kehittäjille; testi
tukee tätä. Päätös voidaan tehdä, kun tiedetään, onko muilla Tampereen työasemilla
välityspalvelin. E on varasuunnitelma siltä varalta, että välityspalvelin estää SDK:n HTTP-asiakkaan mutta Qt:n verkkoliikenne toimii. Kaikissa
vaihtoehdoissa välityspalvelinasetukset luetaan QGISista (`QgsSettings`, `proxy/*`) ja
annetaan SDK:lle (`anthropic.DefaultHttpxClient(proxy=...)`, ks. `core/llm/claude.py`).
