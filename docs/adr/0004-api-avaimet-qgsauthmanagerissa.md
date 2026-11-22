# ADR-0004 API-avaimet QgsAuthManagerissa

- Tila: hyväksytty 22.11.2026; `plugin/auth.py` testattu QGIS 3.44.7:ssä sekä ilman
  käyttöliittymää että käyttöliittymässä (ks. Testitulokset)
- Lähde: toteutussuunnitelma A7, 6.13

## Päätös

- Claude-, Mistral- ja Syke-avaimet tallennetaan QGISin salattuun tunnistetietovarastoon
  (`QgsApplication.authManager()`), jota suojaa QGISin pääsalasana. Kukin avain on oma
  `APIHeader`-tyyppinen tunnistetietomääritys.
- `QgsSettings`iin tallennetaan vain määrityksen tunniste (`kaavamaaraysavustaja/authcfg/<palvelu>`),
  joka ei ole salaisuus.
- Kehityksessä avain voidaan antaa ympäristömuuttujalla (`ANTHROPIC_API_KEY`,
  `MISTRAL_API_KEY`, `RYHTI_API_KEY`), jota käytetään, jos varastossa ei ole avainta.
- Avaimet eivät koskaan päädy projektitiedostoon, muunnosprojektiin (`*.kma.json`), lokiin,
  raporttiin, `QgsSettings`iin tai säilöön.

## Seuraukset

- Käyttäjä joutuu antamaan QGISin pääsalasanan kerran istunnossa.
- Kielimalliadapteri saa avaimen parametrina (`ClaudeProvider(api_key=...)`); ydin ei tunne
  QgsAuthManageria.
- Testausohje: `docs/vaihe0_kayttajan_tehtavat.md`, tehtävä 5.

## Testitulokset 22.11.2026

### Käyttöliittymä (käyttäjän ajama)

QGIS 3.44.7-Solothurn, Tampereen työasema, lisäosa linkitettynä `default`-profiiliin:

- Lisäosa otettiin käyttöön lisäosien hallinnassa, ja *Tietoja*-ikkuna näytti tietopohjan.
- `docs/vaihe0_kayttajan_tehtavat.md`:n tehtävän 5 Python-konsolin rivit toimivat, myös
  pääsalasanan kysely. `print(cfg_id, auth.stored_authcfg_id("claude"))` tulosti saman
  tunnisteen kahdesti (`7koj60d 7koj60d`), joten `QgsSettings`iin tallentui määrityksen
  tunniste.
- Tulos: onnistui ilman virheilmoituksia.

### Ilman käyttöliittymää (tekoälyn ajama)

QGIS 3.44.7-Solothurn (OSGeo4W, Python 3.12.12), `QgsApplication` ilman käyttöliittymää,
kertakäyttöinen profiili ja tunnistetietokanta (`QGIS_AUTH_DB_DIR_PATH`), testipääsalasana ja
testiavain:

- `storeAuthenticationConfig(config)` palauttaa **tuplen** `(True, QgsAuthMethodConfig)`, ja
  tunniste on myös alkuperäisessä oliossa. `loadAuthenticationConfig(id, config, True)`
  palauttaa tuplen `(bool, QgsAuthMethodConfig)`. `auth.py` käsittelee molemmat muodot.
- Tallennus, luku, päivitys (sama tunniste säilyy), määrityksen nimi
  "Kaavamääräysavustaja – Claude API", poisto ja luku poiston jälkeen (`None`) toimivat.
- Testiavain ei näkynyt yhdessäkään profiilin `.ini`-, `.txt`- tai `.log`-tiedostossa.
- Ilman käyttöliittymää ajetun `QgsApplication`in `QgsSettings` kirjoittaa
  `%APPDATA%\python\profiles\…`-kansioon, ei QGIS-profiiliin (organisaation nimeä ei ole
  asetettu). Tällä on merkitystä vain testiskripteissä.
