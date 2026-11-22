# Laaturaportti: Katja-asetuksen liitteen 4 taulukko (LIITE 3)

*Generoitu tiedosto (`python tools/build_knowledge.py`), älä muokkaa käsin.*

- Lähde: `lahtoaineistot/katja/LIITE 3_Esitystavan tekniset yksityiskohdat.xlsx`
- Lähteen sha256: `9ca90db678275aa7043c77bed933088c2b8f5ce519c385d448518ddaccfa538b`
- Tietopohja: TP-2026.11-1 (koodistot ks. `knowledge/manifest.yaml`)
- Korjaukset: `knowledge/katja/annex4_corrections.yaml` (alkuperäistä taulukkoa ei muokata)
- Määrityshierarkioiden voimassaolo tarkistettu päivälle 2026-11-22

Taulukon jokainen koodisarake (kaavamääräyslajit, lisätiedon lajit ja lisätietojen
koodiarvot) on tarkistettu koodistoja vasten. **Ristiriitaisiksi koodiarvoiksi** lasketaan:

- *jäsentymätön arvo*: arvo ei ole koodin URI (esim. selainosoite tai värikoodi)
- *koodisto ei tietopohjassa*: URI viittaa koodistoon, jota tietopohjassa ei ole
- *tuntematon koodi*: koodia ei ole koodistossa
- *väärä sarake*: koodi on väärän koodiston koodi sarakkeen tarkoitukseen nähden
- *poistunut koodi*: koodi on poistettu käytöstä
- *otsikkotason koodi*: koodistoa jäsentävä otsikkotason koodi

Huomioina (ei ristiriitoja) raportoidaan *ylimääräinen tyhjämerkki* (korjataan automaattisesti),
*ei kaavalajin määrityshierarkiassa* (koodi ei kuulu välilehden kaavalajin laajennukseen, vrt. Ryhdin
suositus `rec-codelist-spatialplanregulationtype-plantype-conformity`) ja
*arvo ilman lisätiedon lajia*.

## Yhteenveto

| Välilehti | Rivejä | Ristiriitaiset koodiarvot | Korjattu | Avoinna | Huomioita |
|---|---:|---:|---:|---:|---:|
| Asemakaava | 256 | 5 | 5 | 0 | 6 |
| Yleiskaava | 360 | 13 | 9 | 4 | 12 |
| Maakuntakaava | 226 | 6 | 6 | 0 | 35 |

## Asemakaava

Ristiriitaiset koodiarvot: 5 (väärä sarake 1, poistunut koodi 4).

| Rivi | Sarake | Arvo | Luokka | Selitys | Korjaus |
|---:|---|---|---|---|---|
| 57 | lisatiedonlajin_3_koodiarvo | `tontilleAjoSallittu` (RY_Kaavamaarayksen_Lisatiedonlaji) | väärä sarake | Arvosarakkeessa on lisätiedon lajin koodi (RY_Kaavamaarayksen_Lisatiedonlaji). | AK-057-b (korjattu) |
| 109 | kaavamaarayslaji_koodi | `kunnanTaiKaupunginOsa` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | AK-109 (korjattu) |
| 119 | kaavamaarayslaji_koodi | `rakennusalaJolleSaaSijoittaaSaunan` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | AK-119 (korjattu) |
| 132 | kaavamaarayslaji_koodi | `muuArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | AK-132 (korjattu) |
| 133 | kaavamaarayslaji_koodi | `muuArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | AK-133 (korjattu) |

### Huomiot (Asemakaava)

| Rivi | Sarake | Arvo | Huomio | Selitys |
|---:|---|---|---|---|
| 52 | lisatiedonlajin_2_koodiarvo | `jalankulkualue` | ylimääräinen tyhjämerkki | Arvon alussa tai lopussa on tyhjämerkki; poistettu automaattisesti. |
| 54 | lisatiedonlajin_2_koodiarvo | `jalankulkualue` | ylimääräinen tyhjämerkki | Arvon alussa tai lopussa on tyhjämerkki; poistettu automaattisesti. |
| 55 | lisatiedonlajin_2_koodiarvo | `jalankulkualue` | ylimääräinen tyhjämerkki | Arvon alussa tai lopussa on tyhjämerkki; poistettu automaattisesti. |
| 56 | lisatiedonlajin_2_koodiarvo | `jalankulkualue` | ylimääräinen tyhjämerkki | Arvon alussa tai lopussa on tyhjämerkki; poistettu automaattisesti. |
| 57 | lisatiedonlajin_2_koodiarvo | `jalankulkualue` | ylimääräinen tyhjämerkki | Arvon alussa tai lopussa on tyhjämerkki; poistettu automaattisesti. |
| 120 | kaavamaarayslaji_koodi | `kaupunkiTaiKylakuvallisestiArvokasAlue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'asemakaava'. |

## Yleiskaava

Ristiriitaiset koodiarvot: 13 (väärä sarake 4, poistunut koodi 4, jäsentymätön arvo 1, koodisto ei tietopohjassa 4).

| Rivi | Sarake | Arvo | Luokka | Selitys | Korjaus |
|---:|---|---|---|---|---|
| 46 | lisatiedonlajin_koodiarvo | `kayttotarkoituskohdistus` (RY_Kaavamaarayksen_Lisatiedonlaji) | väärä sarake | Arvosarakkeessa on lisätiedon lajin koodi (RY_Kaavamaarayksen_Lisatiedonlaji). | YK-046-a (korjattu) |
| 46 | lisatiedonlaji_koodi_2 | `tuulivoimalaAlue` | väärä sarake | Sarakkeeseen kuuluu koodiston RY_Kaavamaarayksen_Lisatiedonlaji koodi, nyt RY_Kaavamaarayslaji. | YK-046-b (korjattu) |
| 47 | lisatiedonlajin_koodiarvo | `kayttotarkoituskohdistus` (RY_Kaavamaarayksen_Lisatiedonlaji) | väärä sarake | Arvosarakkeessa on lisätiedon lajin koodi (RY_Kaavamaarayksen_Lisatiedonlaji). | YK-047-a (korjattu) |
| 47 | lisatiedonlaji_koodi_2 | `aurinkovoimalaAlue` | väärä sarake | Sarakkeeseen kuuluu koodiston RY_Kaavamaarayksen_Lisatiedonlaji koodi, nyt RY_Kaavamaarayslaji. | YK-047-b (korjattu) |
| 162 | kaavamaarayslaji_koodi | `muuArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | YK-162 (korjattu) |
| 163 | kaavamaarayslaji_koodi | `valtakunnallisestiMerkittavaArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | YK-163 (korjattu) |
| 215 | kaavamaarayslaji_koodi | `muuArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | YK-215 (korjattu) |
| 216 | kaavamaarayslaji_koodi | `valtakunnallisestiMerkittavaArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | YK-216 (korjattu) |
| 335 | kaavamaarayslaji_koodi | `https://koodistot.suomi.fi/code;registryCode=rytj;schemeCode=RY_Kaavamaarayslaji;codeCode=liikennealue` | jäsentymätön arvo | Arvo ei ole koodiston URI-tunnus. | YK-335 (korjattu) |
| 358 | lisatiedonlajin_koodiarvo | `11` (oikeusvaik_YK) | koodisto ei tietopohjassa | Koodistoa oikeusvaik_YK ei ole tietopohjassa. Koodi on Ryhdin OpenAPI:n enumeraatiossa. | – (**avoinna**) |
| 359 | lisatiedonlajin_koodiarvo | `11` (oikeusvaik_YK) | koodisto ei tietopohjassa | Koodistoa oikeusvaik_YK ei ole tietopohjassa. Koodi on Ryhdin OpenAPI:n enumeraatiossa. | – (**avoinna**) |
| 360 | lisatiedonlajin_koodiarvo | `12` (oikeusvaik_YK) | koodisto ei tietopohjassa | Koodistoa oikeusvaik_YK ei ole tietopohjassa. Koodi on Ryhdin OpenAPI:n enumeraatiossa. | – (**avoinna**) |
| 361 | lisatiedonlajin_koodiarvo | `12` (oikeusvaik_YK) | koodisto ei tietopohjassa | Koodistoa oikeusvaik_YK ei ole tietopohjassa. Koodi on Ryhdin OpenAPI:n enumeraatiossa. | – (**avoinna**) |

### Huomiot (Yleiskaava)

| Rivi | Sarake | Arvo | Huomio | Selitys |
|---:|---|---|---|---|
| 172 | kaavamaarayslaji_koodi | `saamelaiskulttuurinKannaltaTarkeaAlue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 179 | kaavamaarayslaji_koodi | `radonriskialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 223 | kaavamaarayslaji_koodi | `saamelaiskulttuurinKannaltaTarkeaAlue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 227 | kaavamaarayslaji_koodi | `radonriskialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 284 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 318 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 319 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 320 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 324 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 325 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 326 | kaavamaarayslaji_koodi | `tie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |
| 352 | kaavamaarayslaji_koodi | `kaupunginTaiKunnanosanNimi` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'yleiskaava'. |

## Maakuntakaava

Ristiriitaiset koodiarvot: 6 (poistunut koodi 4, jäsentymätön arvo 2).

| Rivi | Sarake | Arvo | Luokka | Selitys | Korjaus |
|---:|---|---|---|---|---|
| 104 | kaavamaarayslaji_koodi | `muuArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | MK-104 (korjattu) |
| 105 | kaavamaarayslaji_koodi | `valtakunnallisestiMerkittavaArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | MK-105 (korjattu) |
| 110 | kaavamaarayslaji_koodi | `#196840` | jäsentymätön arvo | Arvo ei ole koodiston URI-tunnus. | MK-110 (korjattu) |
| 133 | kaavamaarayslaji_koodi | `muuArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | MK-133 (korjattu) |
| 134 | kaavamaarayslaji_koodi | `valtakunnallisestiMerkittavaArkeologinenKohde` | poistunut koodi | Koodin tila RETIRED, päättynyt 2025-06-18. | MK-134 (korjattu) |
| 210 | kaavamaarayslaji_koodi | `https://koodistot.suomi.fi/code;registryCode=rytj;schemeCode=RY_Kaavamaarayslaji;codeCode=liikennealue` | jäsentymätön arvo | Arvo ei ole koodiston URI-tunnus. | MK-210 (korjattu) |

### Huomiot (Maakuntakaava)

| Rivi | Sarake | Arvo | Huomio | Selitys |
|---:|---|---|---|---|
| 19 | kaavamaarayslaji_koodi | `maantie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 21 | kaavamaarayslaji_koodi | `lentoliikenteenAlue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 23 | kaavamaarayslaji_koodi | `kanava` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 24 | kaavamaarayslaji_koodi | `henkiloliikenteenTerminaalialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 25 | kaavamaarayslaji_koodi | `tavaraliikenteenTerminaalialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 26 | kaavamaarayslaji_koodi | `varikko` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 30 | kaavamaarayslaji_koodi | `jatteenkasittelyalue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 35 | kaavamaarayslaji_koodi | `moottoriurheilualue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 43 | kaavamaarayslaji_koodi | `metsatalousalue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 67 | kaavamaarayslaji_koodi | `lentoliikenteenAlue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 69 | kaavamaarayslaji_koodi | `kanava` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 70 | kaavamaarayslaji_koodi | `henkiloliikenteenTerminaalialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 71 | kaavamaarayslaji_koodi | `tavaraliikenteenTerminaalialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 72 | kaavamaarayslaji_koodi | `varikko` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 76 | kaavamaarayslaji_koodi | `jatteenkasittelyalue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 81 | kaavamaarayslaji_koodi | `moottoriurheilualue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 89 | kaavamaarayslaji_koodi | `metsatalousalue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 117 | kaavamaarayslaji_koodi | `tarinaAlue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 119 | kaavamaarayslaji_koodi | `tulvariskialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 122 | kaavamaarayslaji_koodi | `rakentamisrajoitusYleiskaava` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 145 | kaavamaarayslaji_koodi | `tulvariskialue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 146 | kaavamaarayslaji_koodi | `rakentamisrajoitusYleiskaava` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 175 | kaavamaarayslaji_koodi | `kaksiajoratainenTieTaiKatu` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 176 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 177 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 198 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 199 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 200 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 202 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 203 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 204 | kaavamaarayslaji_koodi | `valtatie` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 207 | kaavamaarayslaji_koodi | `jalankulkualue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 207 | kaavamaarayslaji_koodi_2 | `pyorailyalue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 208 | kaavamaarayslaji_koodi | `jalankulkualue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |
| 209 | kaavamaarayslaji_koodi | `pyorailyalue` | ei kaavalajin määrityshierarkiassa | Koodi ei kuulu laajennukseen 'maakuntakaava'. |

## Tarkistukset, joita rakentaja ei tee

- **Semanttinen vastaavuus**: koodi voi olla voimassa ja oikeassa sarakkeessa, mutta
  vastata otsikkoa huonosti (esim. suunnitelmassa mainittu *LV Venesatama → kanava*).
  Nämä tarkistetaan käsin linjauspalavereissa ja kirjataan korjaustiedostoon.
- **Esitystavan tyylitiedot** (värit, viivat, fontit) eivät kuulu vakiomääräysluetteloon.
- Koodiston `oikeusvaik_YK` arvot (esim. 11 ja 12 lisätiedolla *rakennusluvanPeruste*)
  löytyvät Ryhdin OpenAPI:n enumeraatiosta ja vastaavat oppaan alaviitettä 12; ne
  merkitään avoimiksi, kunnes koodisto lisätään tietopohjaan (vaihe 1).
