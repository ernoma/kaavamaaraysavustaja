# ADR-0003 Tietopakettien muoto ja rakentaminen

- Tila: hyväksytty 22.11.2026
- Lähde: toteutussuunnitelma 4 (P4), 6.6, 11

## Tausta

Koodistot, Katja-liite 4, säännöt, kehotteet, Ryhdin skeema ja Tampereen linjaukset muuttuvat
toisistaan riippumatta. Jokainen muunnos on voitava selittää ja ajaa uudelleen sillä
tietopohjalla, jolla se tehtiin.

## Päätös

- Tietopohja on säilön kansio `knowledge/`, jonka `manifest.yaml` nimeää version (esim.
  `TP-2026.11-1`) ja sisältää jokaisen tiedoston sha256-tarkistussumman (`tiedostot`) sekä
  lähdeaineistojen tarkistussummat (`lahteet`). `kaavamaaraysavustaja.knowledge.load_manifest`
  tarkistaa eheyden latauksessa.
- **Tiedostomuodot:**
  - koodistot koodistopalvelun JSONina sellaisenaan: `codelists/<koodisto>/<pvm>.json`, jossa
    päivämäärä on koodiston `modified`/`contentModified`-leimoista uusin
  - koodistoindeksi `codelists/index.json`: konegeneroitu, avaimet englanniksi (vastaa
    koodistopalvelun kenttiä); ydin käyttää tätä, ei raakatiedostoja
  - ihmisen luettavat ja katselmoitavat tiedostot YAMLina, avaimet suomeksi kuten
    suunnitelmassa: manifesti, vakiomääräysluettelo, korjaukset, (myöhemmin) säännöt ja linjaukset
  - Ryhdin skeema JSON Schemana (2020-12) `ryhti/schema_<julkaisu>.json`
  - Ryhdin validointisäännöt ja viestit CSV:nä sellaisenaan Arhosta (`ryhti/validation_messages.csv`)
- **Rakentaminen:** `tools/build_knowledge.py` tuottaa kaiken generoidun deterministisesti
  (ei aikaleimoja). `--check` vertaa säilön tiedostoja uuteen rakennukseen, ja CI ajaa sen.
  `openpyxl` on vain kehitysriippuvuus.
- **Sijainti ajossa:** oletuksena paketin vieressä oleva `knowledge/`; ympäristömuuttuja
  `KMA_KNOWLEDGE_DIR` ohittaa. Jakelupaketissa tietopohja kopioidaan lisäosan mukaan (vaihe 3).
- Tietopohjan uusi versio on uusi manifesti ja uudet tiedostot; vanhat koodistoversiot voivat
  jäädä rinnalle. Vaikutusanalyysi ja muutosvertailu tehdään vaiheissa 1–2.

## Seuraukset

- Raakakoodistot ovat säilössä kahteen kertaan (lähde ja tietopohja), mutta Git tallentaa
  identtisen sisällön yhtenä blobina.
- `.gitattributes` estää rivinvaihtomuunnokset `knowledge/`- ja `lahtoaineistot/`-kansioissa,
  jotta tarkistussummat pysyvät samoina Windowsissa ja Linuxissa.
- OpenAPI → JSON Schema -muunnoksessa abstraktin `AttributeValue`-yläluokan `allOf` poistetaan
  arvotyypeistä: `additionalProperties: false` yhdessä aliluokan omien kenttien kanssa hylkäisi
  muuten jokaisen arvon. `nullable` muunnetaan `null`-tyypiksi.
- Ryhti-julkaisun tunnus `2026-release-11` on suunnitelman merkintä; OpenAPI-tiedoston oma
  `info.version` on `1`. Tunnus tarkistetaan, kun skeema seuraavan kerran päivitetään.
