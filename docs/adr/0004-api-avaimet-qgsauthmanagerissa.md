# ADR-0004 API-avaimet QgsAuthManagerissa

- Tila: hyväksytty 22.11.2026; toteutus (`plugin/auth.py`) on luonnos, jota ei ole testattu QGISissa
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
