# ADR-0017 Kokeiltava telakka, laadintatilan käsittely ja kehote v3

- Tila: hyväksytty 26.11.2026 (vaihe 3a); täydennetty ADR-0018:lla 27.11.2026 (linjauksen
  vaihto kysymyskortista, selkokieli, vienti ilman korvaamista)
- Lähde: ADR-0016; toteutussuunnitelma luvut 5 (UC1, UC2), 6.3, 6.9, 6.13 ja 7; ADR-0002,
  ADR-0004, ADR-0013, ADR-0014

## Tausta

ADR-0016 linjasi, että vaiheen 3 ensimmäinen tavoite on pieni QGISissa kokeiltava versio, jolla
voi muuntaa sekä uuden (laadinta) että voimassa olevan (VOOKA) sanallisen määräyksen. Ydin
käsitteli tilan `laadinta` vain osittain: R-19 oli jo rajattu VOOKA-tilaan, mutta numeroarvot
jäivät aina sanallisiksi, kaavasuosituksia (K13) ei tunnistettu, ja kehote oli kirjoitettu vain
voimassa olevan kaavan muunnokselle. Vaiheen 2 tallennetut kielimallivastaukset ovat VOOKA-
tilan laatuportti, joten kehotteen muutos ei saa muuttaa VOOKA-pyyntöjä huomaamatta.

## Päätös

### Telakka (`plugin/`)

- **Yksi telakka, kolme välilehteä**: *1 Syöte* (tila, kaavataso, syötteen muoto: yksi määräys
  otsikkoineen tai liitetty selite, linjausvalinnat oletuksineen, kielimalli ja budjetti),
  *2 Ehdotus* (yksiköt tilakuvakkeineen ✔ ? ⚠ ✖ –, rakenne kaavoittajan kielellä ja teknisesti
  URIneen, perustelut lainauksineen, varmuus, sääntötulokset, tulkintakysymykset) ja *3 Vienti*
  (muunnosprojekti, raportti Markdown/HTML, Ryhti-JSON, valinnaisesti Arho-YAML ja Syken
  testiympäristön validointi). Jäsennystaulukko, muokkausnäkymät ja koko koosteen eräkäsittely
  odottavat palautetta (ADR-0016).
- **Logiikka on ytimessä**: `core/workflow.py` (ilman QGISia) kokoaa syötteen, sääntöpohjaisen
  muunnoksen, kustannusarvion, lähetettävän sisällön, kielimalliajon, ratkaisut, viennin, Syke-
  validoinnin ja tarkastelunäkymän HTML:n. Telakka vain kerää syötteen ja näyttää tuloksen;
  sama toiminnallisuus on testattu pytestillä CI:ssä.
- **Taustatehtävät**: sääntöpohjainen muunnos, kielimalliajo ja Syke-validointi ajetaan
  `QgsTask`issa (`plugin/tasks.py`), jotka voi keskeyttää. Kielimalliajo käsittelee kopiota
  projektista, joten telakka ei lue keskeneräistä tulosta. Keskeytys tarkistetaan ennen jokaista
  kutsua (`HybridSettings.should_stop`); käsittelyssä oleva kutsu valmistuu, loput yksiköt jäävät
  sääntöpohjaisiksi (tila `keskeytetty`).
- **Kustannusarvio ennen jokaista kielimalliajoa**: dialogi näyttää kutsujen määrän, arvion,
  uudelleenkäytettävät vastaukset ja budjettirajan, jota voi muuttaa; *Näytä lähetettävä sisältö*
  näyttää järjestelmäohjeen, staattisen kontekstin ja tehtävät (asetus: näytä aina). Jos
  kaikki vastaukset käytetään uudelleen, dialogia ei näytetä (kustannus 0).
- **Avaimet**: luetaan pääsäikeessä `plugin/auth.py`:llä (QgsAuthManager, pääsalasana), muuten
  ympäristömuuttujasta (ADR-0004), ja annetaan adapterille (`create_provider(api_key=…)`). Ilman
  SDK:ta tai avainta telakka kertoo syyn ja tekee sääntöpohjaisen muunnoksen.
- **Ratkaisut**: kysymyskortin valinta ja laajuus (*vain tämä merkintä* = `merkinta`, *kaikki
  samankaltaiset tässä muunnoksessa* = `projekti`) tallentuvat päätöslokiin (`Decision`,
  ADR-0014). *Aja uudelleen ratkaisuin* toistaa muunnoksen; aiemmat kielimallivastaukset
  käytetään uudelleen sisältöavaimella ilman kustannusta. Linjauksella ratkaistua kysymystä ei
  muuteta kortissa vaan linjausvalinnalla.
- `kma_deps` lisätään `sys.path`in loppuun lisäosan latautuessa (ADR-0002).

### Laadintatila ytimessä

- **R-19 vain VOOKA-tilassa** (ennallaan). Laadintatilassa tekstiä ei silti muuteta: jokainen
  sanallinen määräys ja kaavasuositus on käyttäjän tekstin osamerkkijono (`text_span`).
  Muotoiluehdotukset eivät kuulu ensimmäiseen versioon.
- **Numeroarvo suureeksi** (opas 3.3.9): kun tekstissä on yksi paikkaan sitomaton numeroarvo,
  jolle sanastossa on suure, ryhmään lisätään suureellinen määräys (`arvotyyppi` ja
  `mittayksikko` sanastosta, esim. `sallittuKerrosala` PositiveNumeric k-m², `tehokkuusluku`
  PositiveDecimal). Teksti säilyy; R-18 kertoo, että arvo on myös suureena. Useita arvoja → ei
  suureita (R-04: yksi suure ryhmää kohden), perustelu kehottaa jakamaan. Paikkasidonnainen arvo
  noudattaa linjausta L-07. Hybridissä arvo tulee aina sääntöpohjaisesta vaiheesta (lähteestä).
- **Suure ei ole rakenteen osa** R-08:ssa (sama pääkäyttötarkoitus tai osa-alue) eikä R-15:ssä
  (liitteen 4 koodiyhdistelmä): suureellinen määräys on yksinkertainen. VOOKA-aineistossa ei ole
  suureita, joten muutos ei vaikuta siihen.
- **K13 (määräys vai suositus)**: laadintatilassa kappale, jossa on suositteleva ilmaus
  (sanasto `suosittelevat_ilmaukset`), nostaa K13:n. Suositus on *kaavasuositus*, jos kappaleessa
  ei ole velvoittavaa ilmausta, muuten *kaavamääräys*. Ratkaisu *suositus* (käyttäjä tai
  kielimalli) siirtää kappaleen kaavasuositukseksi lähteen mukaisena; muu teksti jää
  sanallisiksi määräyksiksi yhtenäisinä jaksoina.
- K12 (vanhentunut lakiviittaus) jää laadintatilassa avoimeksi: laatija päivittää viittauksen.

### Kehote v3

- `knowledge/prompts/v3/`: oma järjestelmäohje (`jarjestelmaohje_laadinta.md`) ja kontekstiosa
  (`laadintaohje.md`, paikkamerkki `{{LAADINTAOHJE}}`) laadintatilalle sekä laadintaesimerkit
  (`tila: laadinta`), jotka valitaan vain laadintatilassa.
- **VOOKA-pyyntö on merkki merkiltä sama kuin v2:ssa** (järjestelmäohje, staattinen konteksti ja
  kaikkien testiaineiston yksiköiden tehtävät; testi `tests/unit/test_prompts.py`). Siksi
  v2:lla tallennettuja vastauksia (`golden_v2_claude.json`) ei äänitetty uudelleen, ja VOOKA-
  mittarit ovat ennallaan (79 % sellaisenaan, korkea 46/46, R-19 0).
- Laadintatilan testiaineisto (`tests/golden/laadinta_odotetut.yaml`, 16 synteettistä yksikköä,
  vahvistamaton) ja sen live-ajon tallenne (`laadinta_claude.json`) ovat laadintatilan
  laatuportti (`test_golden_laadinta.py`). Käyttäjän todelliset esimerkit (T-02) korvaavat tai
  täydentävät aineiston.

### Skeemavalidointi

Ryhdin OpenAPI-kuvauksessa arvotyypit ovat `oneOf`-listassa ilman erottelijaa, joten esimerkiksi
`{"dataType": "PositiveNumeric", "number": 6000}` vastaa neljää vaihtoehtoa ja hylätään.
`validation/schema.py` erottaa vaihtoehdot `dataType`-kentän mukaan. Syken testiympäristö
hyväksyi laadintatilan suureet ja kaavasuositukset.

## Seuraukset

- Lisäosa toimii QGIS 3.44:ssä ilman Arhoa; savutesti `tests/qgis/qgis_smoke.py` ajetaan QGISin
  Pythonilla paikallisesti (merkki `qgis`), ei CI:ssä. CI ei saa QGIS-riippuvuutta.
- QGISin Pythonissa ei ole `jsonschema`-pakettia: paikallinen skeematarkistus ohitetaan ja
  kerrotaan käyttäjälle; Syken validointi kattaa sen.
- Välityspalvelimen asetuksia ei vielä välitetä SDK:lle (ADR-0002 varasuunnitelma); tarve
  selviää kokeilussa.
- Muuttunut sääntöpohjainen tulos muuttaa kielimallin tehtävän vaiheen 1 osaa, mutta tallennettu
  vastaus käytetään uudelleen sisältöavaimella (ADR-0013). Kun sääntöjä muutetaan paljon,
  laadinta-aineiston vastaukset kannattaa äänittää uudelleen (noin 1,2 $).
