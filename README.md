# Kaavamääräysavustaja

Työkalu sanallisten kaava- ja yleismääräysten muuntamiseen Katja-asetuksen (YM 311/2024) mukaiseen rakenteiseen muotoon: Ryhti-JSONiksi ja [Arho](https://github.com/GispoCoding/arho-qgis-plugin)-yhteensopiviksi kaavamääräysryhmiksi. Avustaja perustelee jokaisen muunnospäätöksen, nostaa monitulkintaiset kohdat käyttäjän ratkaistaviksi ja kestää koodistojen ja asetuksen muutokset.

**Tila:** suunnitteluvaihe. Toteutus alkaa vaiheesta 0 (ks. suunnitelman luku 12).

## Sisältö

| Polku | Sisältö |
|---|---|
| [`docs/Toteutussuunnitelma_Kaavamaaraysavustaja.md`](docs/Toteutussuunnitelma_Kaavamaaraysavustaja.md) | Toteutussuunnitelma: tavoitteet, arkkitehtuuri, vaiheistus, riskit ja avoimet kysymykset |
| `lahtoaineistot/koodistot/` | Kaavamääräyslaji-, lisätiedon laji- ja sanallisen kaavamääräyksen laji -koodistot (koodistot.suomi.fi, JSON) |
| `lahtoaineistot/ryhti-openapi/` | Ryhdin planService- ja planDataSharingService-rajapintakuvaukset (OpenAPI) |
| `lahtoaineistot/katja/` | Katja-asetus liitteineen, opas tietomallimuotoisten kaavamääräysten laatimiseen (luonnos 16.2.2026), muutostarvemuistio (16.2.2026) ja esitystavan tekniset yksityiskohdat (xlsx) |

## Lähdeaineistojen alkuperä ja lisenssit

`lahtoaineistot/`-kansion tiedostot ovat kolmansien osapuolten (ympäristöministeriö, Suomen ympäristökeskus, Digi- ja väestötietovirasto) julkaisemia aineistoja. Ne on tallennettu tähän työkalun tietopakettien lähtötiedoiksi sellaisinaan, eikä säilön lisenssi koske niitä. Opas ja muistio ovat luonnosvaiheen asiakirjoja; ajantasaiset versiot löytyvät julkaisijoiden sivuilta.

## Lisenssi

Säilön oma sisältö (koodi ja dokumentaatio): [GNU General Public License v2.0 tai myöhempi](LICENSE) – yhteensopiva Arho-lisäosan GPLv2-lisenssin kanssa.
