# Vaihe 2: kielimalli, perustelut ja tulkintakysymykset – raportti

*22.11.2026 · tietopohja TP-2026.11-3 · kehotteet prompts/v2 v2 · avustaja 0.2.0*

Vaihe 2 ei edellytä Arhoa eikä kaavoittajia (ADR-0012). Testiaineiston odotukset ovat
kehittäjän annotoimia (`tila: vahvistamaton`), joten mittarit kertovat vastaavuuden
suunnitelman suosituksiin, eivät kaavoittajien hyväksyntää.

## 1 Mitä tehtiin

| Osa | Toteutus | ADR |
|---|---|---|
| Hybridiputki | `core/hybrid.py`: sääntöpohjainen → kielimalli vain yksiköille, joiden varmuus ei ole korkea → sääntömoottori → varmuus. Kaksoiskappaleet yhdellä kutsulla. Malli saa vaiheen 1 rakenteen, perustelut, sääntötulokset, avoimet kysymykset, ratkaistut kohdat ja linjausvalinnat. | 0013 |
| Tekstin koskemattomuus | Sanallinen teksti tulee aina lähteestä; malli vain luokittelee sen. R-19 on ehdoton myös hybridissä. | 0013 |
| Lainausten tarkistus ja varmuus | Lainauksen on oltava otsikon tai tekstin osamerkkijono, muuten perustelu hylätään ja varmuus on matala. Korkea varmuus vaatii mallin ja sääntöpohjaisen rakenteen yhtäpitävyyden. | 0013 |
| Kehotteet dataksi | `knowledge/prompts/v1/` ja `v2/` (aktiivinen): järjestelmäohje, staattinen konteksti (koodit kuvauksineen, liite 4, K1–K15, linjaukset), kysymystyypit ja synteettiset esimerkit sanastohakuun. Manifestissa ja rakentajassa käsin ylläpidettävinä. Lisätietojen linjaus (vain kun liite 4, määre tai rakenne osoittaa). | 0013 |
| Tulkintakysymykset ja päätösloki | `core/decisions.py`: ratkaisut asetustiedostosta (`ratkaisut`), laajuus merkintä / projekti, tallennus projektiin, `--projekti` uudelleenajoon, ratkaisupohja `<nimi>_ratkaisut.yaml`. Mallin kysymykset yhdistetään ilman kaksoiskappaleita. | 0014 |
| Linjaus L-15 ja L-04/R-12 | L-15 otsikon valinta (oletus lähteen otsikko, Katja 2 §), L-04:n vaihtoehto kehittämisvyöhykkeen suunnittelumääräykselle. | 0015 |
| Kustannus ja budjetti | `core/llm/budget.py`, hinnat `knowledge/llm/hinnasto.yaml`: arvio ennen ajoa, `--budjetti`, `--arvio`. Tokenit, kustannus, malli, kehoteversio ja vastaukset provenance-tietoihin. Prompt caching käytössä. | 0013 |
| Mistral-adapteri | `core/llm/mistral.py`: `mistralai`-SDK laiskasti, JSON-skeema, yksi korjauskierros. Testit injektoidulla asiakkaalla. | 0013 |
| Jäsennin kartoille 1a–2 | Alaotsikot kappaleiksi, numeroidut osa-alueet alakohdiksi (K9), tavutettu yleismääräysotsikko, alaosiot, kartan 1c selite, `@merkinta` isolla tunnuksella. | 0009 |
| Testiaineisto | 107 yksikköä: Kartta 1 (30), keskustan kartat 1a–2 (52), kantakaupungin kartat 2–4 (25); odotetut lajit ja tarkistettavat kohdat. | – |
| Arviointiajuri | `tools/evaluate.py`: sääntöpohjainen vs. hybridi, tallennetut vastaukset `tests/recorded_llm/`, live-ajo jatkettavana. Laatuportti `tests/golden/test_golden_v2.py`. | – |

Testejä on 186 (lisäksi kaksi `live`-testiä), ruff ja `build_knowledge.py --check` ovat puhtaat,
ja arkkitehtuuritesti estää edelleen QGISin ja SDK:iden tuonnin ytimessä. CI ajaa hybridin
tallennetuilla vastauksilla ilman verkkoa ja ilman `anthropic`- ja `mistralai`-paketteja.

## 2 Mittarit tavoitteita vasten (luku 2.3)

```powershell
.\.venv\Scripts\python tools\evaluate.py --vertailu --yksikot
```

Testiaineisto: 107 yksikköä kolmesta otoksesta (`tests/golden/`), joista 93 kaavakohdetta,
11 yleismääräystä ja 3 informatiivista merkintää. Hybridi = Claude `claude-opus-5-5`, effort
`medium`, kehote v2. Kielimalli käsitteli 98 yksikköä; 6 oli sääntöpohjaisesti korkean
varmuuden ja 3 informatiivisia (jäävät käyttäjälle).

| Mittari (luku 2.3) | Tavoite | Sääntöpohjainen | Hybridi, kehote v1 | **Hybridi, kehote v2** |
|---|---|---:|---:|---:|
| Merkinnät, joiden ehdotus hyväksytään sellaisenaan | ≥ 70 % | 36/107 (34 %) | 59/107 (55 %) | **84/107 (79 %)** |
| Korkean varmuuden ehdotuksista oikein | ≥ 98 % | 6/6 | 39/39 | **46/46 (100 %)** |
| Tunnetuista monitulkintaisista kohdista nousee kysymykseksi | ≥ 90 % | 75/86 (87 %) | 84/86 (98 %) | **81/86 (94 %)** |
| Määräystekstin muutokset | 0 | 0 | 0 | **0** |
| Ryhmät läpäisevät Ryhdin määräystason validoinnin | 100 % | – | – | **15/15 valittua (Syke), skeema 100 %** |

"Hyväksytään sellaisenaan" mitataan ilman käyttäjiä ehdokkaina, jotka ovat myös oikein: ei
avoimia kysymyksiä, sääntövirheitä, -varoituksia eikä matalaa varmuutta, ja rakenne ja
kirjaintunnus vastaavat annotointia. **Tavoite ≥ 70 % saavutetaan vahvistamattomalla
aineistolla.** Kun kaavoittajat vahvistavat aineiston (vaihe 5), luku mitataan uudelleen.

Muut luvun 10.3 mittarit:

| Mittari | Sääntöpohjainen | Hybridi v1 | Hybridi v2 |
|---|---:|---:|---:|
| Pääkoodin osuvuus (kaavakohteet) | 50/93 (54 %) | 91/93 (98 %) | 91/93 (98 %) |
| Rakenteen osuvuus (lajit ja lisätiedot) | 47/93 (51 %) | 89/93 (96 %) | 88/93 (95 %) |
| Kirjaintunnuksen osuvuus | 31/33 (94 %) | 33/33 | 33/33 (100 %) |
| Lisätietojen F1 (P / R) | 0,66 (0,92 / 0,52) | 0,95 (0,94 / 0,96) | **0,95 (0,93 / 0,97)** |
| Sanallisen määräyksen lajien F1 (P / R) | 0,78 (0,88 / 0,70) | 0,85 (0,82 / 0,89) | **0,85 (0,83 / 0,87)** |
| Kalibrointi: korkea / keskitaso / matala, rakenne oikein | 100 / 100 / 35 % | 100 / 100 / 92 % | **100 % (46) / 93 % (41) / 90 % (20)** |
| Kustannus yksikköä kohden (kaikki 107) | 0 | 0,079 $ | **0,074 $** (live 7,89 $) |
| Aika kutsua kohden | – | 28 s | **25 s** |

Lajien F1:ssä tarkkuus lasketaan odotettujen ja "myös perusteltujen" lajien (`sanallisen_lajit_muut`)
mukaan, kattavuus odotettujen pääaiheiden mukaan.

### Kehote v1 → v2

Ensimmäinen live-ajo (v1) osui rakenteeseen jo 96 %:sti, mutta vain 55 % meni läpi
sellaisenaan: malli nosti K7:n lähes jokaisesta valinnaisesta lisätiedosta (20 yksikköä,
esim. "lisätäänkö seudullinen?") sekä K1:n, K6:n ja K8:n tapauksissa, jotka nimi tai liite 4
ratkaisee. Kehote v2 (ADR-0013) lisäsi kysymysten kynnyksen tyypeittäin ja käskee kirjata
valinnaiset lisätiedot hylättyinä vaihtoehtoina. Rakenteen osuvuus pysyi, ja kysymysten
kattavuus laski 98 %:sta 94 %:iin, eli malli jätti kolme tunnettua kysymystä nostamatta
(tavoite 90 % täyttyy). Samalla korjattiin koodissa R-15:n varoitus tekstittömistä ryhmistä
(ADR-0015).

### Mikä ei mene läpi sellaisenaan (23 yksikköä, v2)

| Syy | Yksiköitä | Esimerkit | Kenen ratkaistava |
|---|---:|---|---|
| Avoin K1 (aluevaraus vai osa-alue) | 3 | c-1, km, LUONNONSUOJELUALUE TAI -KOHDE | käyttäjä tai vektoriaineisto (vaihe 4) |
| Avoin K9 (alakohdat) | 3 | KAUPUNKIYMPÄRISTÖN KEHITTÄMISVYÖHYKE, VALUMA-ALUEET | käyttäjä |
| Informatiivinen (K6) | 4 | YLEISKAAVA-ALUEEN RAJA, kaupunkipuiston rajaus | käyttäjä vahvistaa |
| R-11 kirjaintunnus puuttuu | 4 | sekoittuneet alueet, ERIKOISPUISTO | käyttäjä antaa tunnuksen |
| Avoin K7 / K8 | 6 | TUTKITTAVA OHJEELLINEN LÄHIJUNA-ASEMA, JÄTEASEMA, Vu … ALUE TAI KOHDE | käyttäjä |
| Rakenne eri kuin annotointi | 5 | KEHITETTÄVÄ TORIALUE, TORI TAI AUKIO, TARVEALUE UUDELLE JÄTEASEMALLE | tarkistettava (annotointi tai malli) |

Kolme virheellistä ehdotusta on keskitason varmuudella eikä mikään korkealla: kaikki väärät
jäävät suodattimen "hyväksy korkean varmuuden" ulkopuolelle. Keskitason virheet ovat
`kehitettava`-lisätiedon lisäyksiä (KEHITETTÄVÄ TORIALUE, KEHITETTÄVÄ VIHER- JA
VIRKISTYSVYÖHYKE) ja yksi `osaAlue` aluevarauskoodille.

## 3 Syken testirajapinta (live, 22.11.2026)

```powershell
.\.venv\Scripts\kma validate work\v2\keskusta_hybridi.kma.json --syke --yksikot u001,u005,u015,u029,u033,u040,u042,u045,u050
.\.venv\Scripts\kma validate work\v2\kartat2_4_hybridi.kma.json --syke --yksikot u013,u016,u019,u023
.\.venv\Scripts\kma validate work\v2\kartta1_hybridi.kma.json --syke --yksikot u010,u021
```

Kielimallin käsittelemiä ryhmiä validoitiin 15: yleismääräys, kehittämisvyöhykkeet
(Ydinkeskustan kehittämisvyöhyke, Tammerkoski), pistekohteet (Naistenlahden voimalaitos,
maanalainen pysäköintilaitos, pyöräpysäköinti, kirkko, sähköasema), viivakohteet (Hämeenkatu,
VT12 + tunneli, vesijohto, valtakunnallinen pääväylä), osa-alueet (mav, saastunut maa-alue) ja
loma-asuntoalue. **Kaikki 15 saivat HTTP 200 ilman määräystason havaintoja.** Projektit
tehtiin tallennetuista vastauksista (`work/v2/`, ei säilöön).

## 4 Kustannukset

| Ajo | Kutsuja | Kustannus |
|---|---:|---:|
| Savutesti (kartta 1, kolme yksikköä, välimuistin ensikirjoitus) | 4 | 0,57 $ |
| Testiaineisto, kehote v1 | 98 | 8,65 $ |
| Testiaineisto, kehote v2 | 98 | 7,89 $ |
| **Yhteensä** | 200 | **noin 17,1 $** (raja 30 $) |

- Staattinen konteksti ja skeema ovat 48 775 tokenia, ja ne luetaan välimuistista
  (0,20 $ / milj.): noin 0,01 $ kutsua kohden. Ensikirjoitus maksaa noin 0,25 $.
- Kutsun kustannuksesta suurin osa on tulostetta (2 000–3 800 tokenia, sisältää päättelyn).
- Arvio ennen ajoa (8,52 $) oli 8 % yläkanttiin; arvion kerroin kalibroitiin savutestillä
  (1,75 merkkiä tokenia kohden suomelle ja JSONille).
- Koko koosteen 231 yksiköstä noin 210 menisi mallille: noin 16 $ ja 1,5 tuntia
  (peräkkäiset kutsut). Eräajorajapinta (luku 6.8) puolittaisi hinnan; ei toteutettu.

## 5 Mistral

`MISTRAL_API_KEY` ei ollut asetettu, joten **Mistralin live-ajo ja vertailu jäivät tekemättä**.
Adapteri on testattu injektoidulla asiakkaalla (pyyntö, korjauskierros, katkeaminen, puuttuva
avain), ja SDK 3.8 asennettiin kehitysympäristöön rajapinnan tarkistamiseksi. Vertailu ajetaan,
kun avain on käytössä:

```powershell
.\.venv\Scripts\python tools\evaluate.py --hybridi mistral --live --arvio
.\.venv\Scripts\python tools\evaluate.py --hybridi mistral --live --budjetti 5
.\.venv\Scripts\python tools\evaluate.py --vertailu
```

Mistralin hinnat (`knowledge/llm/hinnasto.yaml`) on merkitty vahvistamattomiksi, ja ne pitää
tarkistaa ennen ajoa.

## 6 Mitä jäi käyttäjälle

Tehtävien seurattava lista ja tila: [kayttajan_tehtavat.md](kayttajan_tehtavat.md) (T-03–T-14).
Painotus 26.11.2026: ensin kokeiltava käyttöliittymä (ADR-0016).

Paikkatietoasiantuntijalle nyt (ei edellytä Arhoa eikä kaavoittajia):

- **Testiaineiston tarkistettavat kohdat**: `tests/golden/keskusta_odotetut.yaml` ja
  `kartat2_4_odotetut.yaml`, kentät `tarkistettava: true` (23 yksikköä), erityisesti torit,
  Hämeenkatu, Tammerkoski, asemakeskus, vaihtoterminaali, valuma-alueet ja TARVEALUE-merkinnät.
  Lisäksi annotointia täydennettiin mallin löytämillä koodeilla (`henkiloliikenteenTerminaalialue`,
  `liikennetunneli(maanalainenTila)`, `yhdyskuntateknisenHuollonAlue(uusi)`): tarkista nekin.
- **Otosten käsin tehdyt korjaukset** (otosten otsakekommentit): kartan 1a palstajärjestys ja
  `KAUPUNKIRAKE NTEEN`. Samat korjaukset tarvitaan koko koosteen muunnoksessa.
- **Mistral-avain**, jos Mistral-vertailu halutaan (luku 5).
- Vaiheen 1 avoimet: normalisoinnin vahvistettavat kohdat ja liitteen 4 korjaukset.

Vaiheessa 5 kaavoittajien kanssa: testiaineiston vahvistus, linjaukset L-04 ja L-15 (ADR-0015)
sekä muut linjaukset.

## 7 Havaintoja vaiheen 3 kannalta

1. **Kysymysten kynnys ratkaisee automaatioasteen.** Malli osuu rakenteeseen 95 %:sti; ero
   55 % ja 79 % välillä syntyi vain siitä, kuinka herkästi se kysyy. Käyttöliittymässä
   kannattaa näyttää mallin hylkäämät vaihtoehdot (tallessa perusteluissa) ilman, että ne
   ovat kysymyksiä, ja antaa käyttäjän suodattaa kysymykset tyypeittäin.
2. **Varmuus on kalibroitu käyttökelpoisesti.** Korkea 46/46 oikein; virheet ovat keski- ja
   matalalla tasolla. "Hyväksy kaikki korkean varmuuden" -suodatin (luku 6.9, ≥ 98 %) voidaan
   ottaa käyttöön, kun vahvistettu aineisto vahvistaa tuloksen.
3. **Loput avoimet ovat aidosti käyttäjän tai vektoriaineiston ratkaistavia**: K1 (vaihe 4,
   päällekkäisyys), K9 (jaetaanko alakohtiin), K6 (informatiivinen) ja R-11 (sekoittuneen
   alueen kirjaintunnus). Ratkaisukortit, laajuus *samankaltaiset projektissa* ja ratkaisupohja
   (`<nimi>_ratkaisut.yaml`) ovat valmiina päätöslokissa (ADR-0014).
4. **Ajo kestää.** 25 s kutsua kohden peräkkäin; koko kooste noin 1,5 h. Vaiheessa 3 kutsut
   ajetaan `QgsTask`issa rinnakkain (esim. 4–8) tai eräajona, ja tulokset näytetään sitä mukaa
   kuin ne valmistuvat. Uudelleenajo `--projekti`-tavalla ei maksa mitään.
5. **Jäsennin vaatii yhä käsikorjauksia** palstajärjestyksessä. Jäsennystaulukossa tarvitaan
   tekstin siirto merkinnältä toiselle (kartta 1a) ja sanan sisäisen välilyönnin korjaus.
6. **Kustannusarvio ennen ajoa toimii** (8 % yläkanttiin). Käyttöliittymä voi näyttää saman
   arvion ja budjettirajan ennen lähetystä (luku 7.3).
7. **Sääntöpohjaisen vaiheen ja mallin yhtäpitävyys** antaa korkean varmuuden 46 ryhmälle.
   Kun Tampere hyväksyy muunnoksia (`hyvaksytyt.yaml`), ne tulevat sekä sääntöpohjaiseen
   täsmäykseen että kehotteen esimerkkeihin, jolloin malli tarvitaan yhä harvemmin.
