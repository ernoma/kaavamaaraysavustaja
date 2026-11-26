# Vaihe 3a: ensimmäinen kokeiltava versio (QGIS-telakka)

26.11.2026 · lisäosa 0.3.0 · tietopohja TP-2026.11-3 · kehote prompts/v3 v3 ·
päätökset [ADR-0016](adr/0016-kokeiltava-kayttoliittyma-ja-uudet-maaraykset-ensin.md) ja
[ADR-0017](adr/0017-telakka-laadintatila-ja-kehote-v3.md)

## 1 Mitä tehtiin

| Osa | Sisältö |
|---|---|
| Telakka (`plugin/dock.py`) | *1 Syöte*: tila uusi / voimassa oleva, kaavataso, yksi määräys tai liitetty selite, tekstitiedoston avaus, linjausvalinnat oletuksineen, kielimalli ja budjetti. *2 Ehdotus*: yksiköt tilakuvakkeineen, rakenne kaavoittajan kielellä ja teknisesti URIneen, perustelut lainauksineen, varmuus, sääntötulokset, tulkintakysymykset, ratkaisu ja laajuus, uudelleenajo. *3 Vienti*: muunnosprojekti, raportti (Markdown/HTML), Ryhti-JSON, Arho-YAML, Syken testiympäristö |
| Taustatehtävät (`plugin/tasks.py`) | sääntöpohjainen muunnos, kielimalliajo ja Syke-validointi `QgsTask`issa; keskeytys ennen jokaista kutsua |
| Dialogit (`plugin/dialogs.py`) | kustannusarvio ja budjettiraja ennen jokaista kielimalliajoa, lähetettävä sisältö, API-avaimet (QgsAuthManager) |
| Työnkulku (`core/workflow.py`) | telakan logiikka ilman QGISia: syöte, muunnos, arvio, esikatselu, ajo, ratkaisut, vienti, Syke, tarkastelunäkymä; testattu CI:ssä |
| Laadintatila ytimessä | yksittäinen syöte (`ingest.single_unit`); numeroarvo suureeksi; K13 ja kaavasuositukset; R-08/R-15 eivät koske suuretta; R-19 vain VOOKA |
| Hybridi | suureen arvo aina lähteestä, kaavasuositukset säilyvät, mallin K13-ratkaisu, keskeytys (`should_stop`) |
| Kehote v3 | laadintatilan järjestelmäohje, kontekstiosa ja esimerkit; VOOKA-pyyntö merkki merkiltä sama kuin v2:ssa |
| Skeemavalidointi | Ryhdin arvotyypit erotellaan `dataType`-kentän mukaan (OpenAPI:n `oneOf` hylkäsi jokaisen numeroarvon) |
| Testiaineisto | 16 synteettistä uutta määräystä (`tests/golden/laadinta_odotetut.yaml`, vahvistamaton), live-ajon tallenne ja laatuportti |
| Testit | 228 testiä CI:ssä (ilman QGISia, verkkoa ja SDK:ita); QGIS-savutesti `tests/qgis/qgis_smoke.py` (merkki `qgis`) |
| CI | korjattu: `build_knowledge.py --check` oli epäonnistunut Linuxissa vaiheesta 2 alkaen, koska manifestin tarkistussummat oli laskettu CRLF-rivinvaihdoista (Git tallentaa LF). Nyt CI on vihreä. |
| Dokumentaatio | [käyttöohje](kayttoohje.md), [palautepohja](palaute_vaihe3.md), ADR-0017, tämä raportti |

Commitit: `71e2044` … (ks. `git log`), kaikki pushattu `main`-haaraan.

## 2 Miten kokeilet

Tarkemmin [käyttöohjeessa](kayttoohje.md). Tällä työasemalla lisäosa on jo linkitetty ja SDK
asennettu (`kma_deps`).

1. Päivitä säilö (`git pull`) ja käynnistä QGIS 3.44. *Lisäosat → Kaavamääräysavustaja →
   Tietoja*: "Kaavamääräysavustaja 0.3.0", tietopohja TP-2026.11-3, "claude ✓".
2. Avaa telakka (*Lisäosat → Kaavamääräysavustaja → Kaavamääräysavustaja*).
3. **Uusi määräys**: Tila *Uusi määräys (laadinta)*, otsikko "Pientalovaltainen asuntoalue",
   teksti kahdessa kappaleessa: "Alueelle saa rakentaa enintään 6 000 k-m² pientaloja." ja
   "Pihoille suositellaan hulevesien viivyttämistä." Kielimalli *Ei*, **Muunna**.
4. *2 Ehdotus*: tarkista rakenne (asuinpientaloalue + pääkäyttötarkoitus, sallittu kerrosala
   6000 k-m², otsikko ja tunnus AP), perustelut ja kysymys K13. Valitse *Kaavasuositus*,
   **Tallenna ratkaisu**, **Aja uudelleen ratkaisuin**: toinen kappale on nyt kaavasuositus.
5. **Voimassa oleva määräys**: *Uusi muunnos*, Tila *VOOKA*, Syöte *Liitetty selite*, liitä
   käyttöohjeen luvun 4 esimerkki (tai pätkä koosteesta), **Muunna**. Ratkaise c-1:n K1
   laajuudella *Kaikki samankaltaiset* ja aja uudelleen.
6. **Kielimalli**: tallenna Claude-avain (*Avaimet…*), valitse *Claude*, **Muunna**. Tarkista
   kustannusarvio ja *Näytä lähetettävä sisältö*; lähetä. Kokeile myös pientä budjettirajaa
   (esim. 0,05 $) ja *Keskeytä*-painiketta.
7. *3 Vienti*: valitse kansio, rastita muodot, **Vie**. Halutessasi **Validoi Syken
   testiympäristössä** (Syke-avain).
8. Kirjaa havainnot [palautepohjaan](palaute_vaihe3.md) (T-01) ja kuvaa omat
   muunnostarpeesi (T-02).

## 3 Tulokset

### 3.1 Voimassa olevat määräykset (VOOKA): ennallaan

Kehote v3 tuottaa VOOKA-tilassa saman pyynnön kuin v2 (testi), joten vaiheen 2 tallenteet
toistuvat sellaisinaan. `tools/evaluate.py --hybridi claude --vertailu` (107 yksikköä):

| Mittari | sääntöpohjainen | hybridi (Claude, v2 = v3) | vaihe 2 |
|---|---|---|---|
| hyväksytään sellaisenaan | 36/107 (34 %) | 84/107 (79 %) | 84/107 |
| korkean varmuuden ehdotuksista oikein | 6/6 | 46/46 | 46/46 |
| rakenteen osuvuus | 47/93 | 88/93 (95 %) | 88/93 |
| sanallisen tekstin poikkeamat (R-19) | 0 | 0 | 0 |

Laatuportit `test_golden.py` ja `test_golden_v2.py` menevät läpi.

### 3.2 Uudet määräykset (laadinta), synteettinen aineisto

`tools/evaluate.py --laadinta --vertailu` (16 yksikköä, vahvistamaton):

| Mittari | sääntöpohjainen | hybridi (Claude) |
|---|---|---|
| rakenteen osuvuus | 13/13 | 13/13 |
| kirjaintunnuksen osuvuus | 13/13 | 13/13 |
| tunnetuista kysymyksistä tunnistettu | 23/24 | 23/24 |
| hyväksytään sellaisenaan (ehdokas ja oikein) | 7/16 (44 %) | 15/16 (94 %) |
| korkean varmuuden ehdotuksista oikein | – | 15/15 |
| sanallisen määräyksen lajit (F1) | 0,58 | 0,90 |
| K13 suositus oikein | 3/3 | 3/3 |
| suure arvoineen | 3/3 | 3/3 |
| tekstin muutokset | 0 | 0 |
| kustannus | 0 | 1,16 $ (16 kutsua, 0,073 $ / yksikkö, 17 s / kutsu) |

Tulos on liian hyvä yleistettäväksi: synteettiset esimerkit noudattavat liitteen 4 otsikoita,
joten sääntöpohjainen vaihe löytää rakenteen aina. Todelliset uudet määräykset (T-02) ovat
todennäköisesti vapaamuotoisempia. Live-ajo paljasti kaksi sääntövirhettä (R-08 ja R-15
koskivat myös suuretta), jotka korjattiin; VOOKA-aineistossa ei ole suureita.

### 3.3 Syken testiympäristö

Laadintatilan ryhmät (sallittu kerrosala, tehokkuusluku, kaavasuositus merkinnässä ja
yleismääräyksessä) validoituivat ilman määräystason havaintoja. Sääntöpohjaisen vaiheen
ryhmä, jolta puuttuu sanallisen määräyksen laji, saa odotetusti havainnon
`req-codelist-spatialplanregulation-verbal-regulation-codevalue` (sama kuin R-03).

### 3.4 QGIS

`tests/qgis/qgis_smoke.py` QGIS 3.44.7:n Pythonilla ilman ikkunaa: lisäosa latautuu, telakka
avautuu, uusi ja voimassa oleva määräys muuntuvat, K13 ja K1 ratkeavat ja säilyvät
uudelleenajossa, vienti tuottaa kaikki tiedostot, kielimallipolku näyttää arvion ennen kutsua
(testiadapteri) ja käyttää vastauksen uudelleen, oikea `QgsTask` valmistuu ja lisäosa poistuu
siististi. SDK latautuu `kma_deps`-kansiosta (anthropic 2.12.0). Käyttöliittymää ei ole
klikattu QGIS-ikkunassa (T-01).

### 3.5 Kielimallikustannukset tässä vaiheessa

Live-kutsuja tehtiin vain laadinta-aineiston äänitykseen: 16 kutsua, 1,16 $ (arvio 1,50 $).
VOOKA-tallenteita ei äänitetty uudelleen.

## 4 Tunnetut puutteet

- Rakennetta ei voi muokata käsin (koodivalitsimet); vaikutus vain ratkaisuilla ja linjauksilla.
- Ei jäsennystaulukkoa eikä koko koosteen eräkäsittelyä; kielimallikutsut ajetaan peräkkäin.
- Ei muotoiluehdotuksia laadintatilassa (rajattu pois ensimmäisestä versiosta).
- Kaikkien kysymystyyppien rakenteellisia seurauksia ei ole toteutettu (esim. K2, K9, K10);
  ratkaisu sulkee kysymyksen ja välittyy kielimallille (ADR-0014).
- Mallin hylkäämät vaihtoehdot näkyvät perusteluissa, mutta kysymyksiä ei voi suodattaa
  tyypeittäin eikä korkean varmuuden ehdotuksia hyväksyä erissä (vaiheen 2 havainnot 1–2).
- Paikallinen Ryhti-skeematarkistus ohitetaan QGISissa (`jsonschema` puuttuu); Syke kattaa sen.
- Välityspalvelimen asetuksia ei välitetä SDK:lle (ADR-0002, varasuunnitelma).
- Laadinta-aineisto on synteettinen ja helppo; mittarit eivät kerro todellisesta tasosta.
- Käyttöliittymä vain suomeksi; ei kuvaketta (QGISin teemakuvake).

## 5 Mitä odotetaan palautteelta

Ensisijaisesti ([palautepohja](palaute_vaihe3.md)):

1. **Uusien määräysten todelliset tarpeet (T-02)**: millaisia tekstejä, kuka kirjoittaa, ja
   mitä tuloksella tehdään (Ryhti-JSON, Arho, raportti). Esimerkkitekstit korvaavat
   synteettisen aineiston, ja niillä mitataan laadintatila uudelleen.
2. **Ymmärrettävyys**: ovatko rakenne kaavoittajan kielellä, perustelut ja kysymyskortit
   selviä ilman koodien tuntemusta? Mitkä termit tai näkymät ovat hankalia?
3. **Puuttuvat toiminnot järjestyksessä**: rakenteen muokkaus, koko koosteen eräkäsittely,
   jäsennystaulukko, muotoiluehdotukset, kytkentä vektoriaineistoon.
4. **Kielimallin hyöty ja kustannus**: riittääkö sääntöpohjainen muunnos usein, ja onko arvio
   ennen lähetystä riittävän selkeä.
5. **Uusi vai voimassa oleva**: kumpi muunnostarve on nyt tärkeämpi, jotta seuraavan vaiheen
   järjestys voidaan päättää.

Käyttäjälle jäävät tehtävät: [`kayttajan_tehtavat.md`](kayttajan_tehtavat.md) (T-01, T-02, T-07).
