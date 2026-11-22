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

## Alustava suositus

C (oma asennusapuri `--target`-kansioon) ja A kehittäjille. E varasuunnitelmana, jos
välityspalvelin estää SDK:n HTTP-asiakkaan mutta Qt:n verkkoliikenne toimii. Kaikissa
vaihtoehdoissa välityspalvelinasetukset luetaan QGISista (`QgsSettings`, `proxy/*`) ja
annetaan SDK:lle (`anthropic.DefaultHttpxClient(proxy=...)`, ks. `core/llm/claude.py`).
