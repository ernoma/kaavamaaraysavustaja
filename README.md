# Kaavamääräysavustaja

Työkalu sanallisten kaava- ja yleismääräysten muuntamiseen Katja-asetuksen (YM 311/2024) mukaiseen rakenteiseen muotoon: Ryhti-JSONiksi ja [Arho](https://github.com/GispoCoding/arho-qgis-plugin)-yhteensopiviksi kaavamääräysryhmiksi. Avustaja perustelee jokaisen muunnospäätöksen, nostaa monitulkintaiset kohdat käyttäjän ratkaistaviksi ja kestää koodistojen ja asetuksen muutokset.

**Tila:** vaihe 1 (ydin ja sääntöpohjainen muunnos) valmis. Komentorivi `kma convert` muuntaa koosteen kartan sääntöpohjaisesti muunnosprojektiksi, Arhon kirjastoksi, Ryhti-fragmenteiksi ja raportiksi; `kma validate` tarkistaa säännöillä, skeemalla ja Syken rajapinnalla. Tulokset: [`docs/vaihe1_raportti.md`](docs/vaihe1_raportti.md). Kielimalli tulee vaiheessa 2 (suunnitelman luku 12).

Kehittäjän ohjeet ja komennot: [`CLAUDE.md`](CLAUDE.md).

## Sisältö

| Polku | Sisältö |
|---|---|
| [`docs/Toteutussuunnitelma_Kaavamaaraysavustaja.md`](docs/Toteutussuunnitelma_Kaavamaaraysavustaja.md) | Toteutussuunnitelma: tavoitteet, arkkitehtuuri, vaiheistus, riskit ja avoimet kysymykset |
| [`docs/adr/`](docs/adr/) | Arkkitehtuuripäätökset |
| [`docs/laaturaportti_liite3.md`](docs/laaturaportti_liite3.md) | Katja-liitteen 4 taulukon tarkistus koodistoja vasten |
| [`docs/vaihe0_kayttajan_tehtavat.md`](docs/vaihe0_kayttajan_tehtavat.md) | Vaiheen 0 tehtävät, jotka tehdään Tampereen työasemalla tai kaavoittajien kanssa |
| [`docs/vaihe1_raportti.md`](docs/vaihe1_raportti.md) | Vaiheen 1 tulokset, mittarit, Syke-testi ja Arhon testiohje |
| `kaavamaaraysavustaja/` | Python-paketti ja QGIS-lisäosa (`core` ilman QGISia, `knowledge`, `exporters`, `validation`, `plugin`) |
| `knowledge/` | Tietopohja: koodistot ja indeksi, Katja-liitteen 4 vakiomääräysluettelo ja korjaukset, Ryhti-skeema, validointiviestit, säännöt, sanasto, Tampereen linjaukset, manifesti |
| `tools/` | Tietopaketin rakentaja, PDF:n tekstinpoiminta, arviointi, Claude-piikki, Syken validointitesti, SDK-ympäristön tarkistus |
| `tests/` | Yksikkö- ja arkkitehtuuritestit sekä testiaineisto v1 (`tests/golden/`; pytest, ilman QGISia) |
| `lahtoaineistot/koodistot/` | Kaavamääräyslaji-, lisätiedon laji- ja sanallisen kaavamääräyksen laji -koodistot (koodistot.suomi.fi, JSON) |
| `lahtoaineistot/ryhti-openapi/` | Ryhdin planService-, planDataSharingService- ja julkisen validointirajapinnan kuvaukset (OpenAPI) |
| `lahtoaineistot/katja/` | Katja-asetus liitteineen, opas tietomallimuotoisten kaavamääräysten laatimiseen (luonnos 16.2.2026), muutostarvemuistio (16.2.2026) ja esitystavan tekniset yksityiskohdat (xlsx) |
| `lahtoaineistot/arho/` | Ryhdin validointisäännöt paluuviesteineen Arho-lisäosasta (ks. `LAHDE.md`) |

## Lähdeaineistojen alkuperä ja lisenssit

`lahtoaineistot/`-kansion tiedostot ovat kolmansien osapuolten (ympäristöministeriö, Suomen ympäristökeskus, Digi- ja väestötietovirasto) julkaisemia aineistoja; `lahtoaineistot/arho/` on peräisin Arho-lisäosasta (GPL-2.0). Ne on tallennettu tähän työkalun tietopakettien lähtötiedoiksi sellaisinaan, eikä säilön lisenssi koske niitä. Opas ja muistio ovat luonnosvaiheen asiakirjoja; ajantasaiset versiot löytyvät julkaisijoiden sivuilta.

## Lisenssi

Säilön oma sisältö (koodi ja dokumentaatio): [GNU General Public License v2.0 tai myöhempi](LICENSE) – yhteensopiva Arho-lisäosan GPLv2-lisenssin kanssa.
