# Vaihe 1: ydin ja sääntöpohjainen muunnos – raportti

*22.11.2026 · tietopohja TP-2026.11-2 · avustaja 0.1.0 · sääntöpohjainen, ei kielimallikutsuja*

## 1 Mitä tehtiin

| Osa | Toteutus | ADR |
|---|---|---|
| Välimalli | `core/model.py`: muunnosprojekti, yksiköt, ehdotukset, perustelut, tulkintakysymykset, päätökset, linjausvalinnat ja alkuperätiedot. Koodit URI:na koodistoversion kanssa. JSON edestakaisin (`*.kma.json`). | – |
| Syöte ja normalisointi | `core/ingest.py` jäsentää koosteen tekstimuodon (kartta, osio, otsikko, kirjaintunnus, teksti, sivu, lähdekaavat). Normalisointi säilyttää alkuperäisen ja normalisoidun tekstin sekä erolistan. `tools/extract_pdf_text.py` poimii PDF:n paikalliseen tiedostoon (pypdf, vain kehityksessä). | 0009 |
| Täsmäys | `core/match.py`: hyväksytyt muunnokset, liite 4 korjauksineen, koodien nimet, otsikon määreet, sanallisen määräyksen lajit, suureet ja paikkasidonnaisuus, yleismääräyksen kohdistus, lakiviittaukset. Sanasto on dataa (`knowledge/rules/sanasto_v1.yaml`). | – |
| Muunnos | `core/convert.py`: ehdotukset perusteluineen ja varmuuksineen sekä tulkintakysymykset K1–K12, K14 ja K15. Linjauksen ratkaisema kysymys merkitään ratkaistuksi. | – |
| Linjaukset | `knowledge/org/tampere/linjaukset.yaml` (L-01–L-07), `core/policy.py`. Valinnat tulevat valitsimista ja asetustiedostosta, lukitun ohitus on virhe, ja valinnat näkyvät projektissa ja raportissa. | 0010 |
| Sääntömoottori v1 | `core/rules/`: R-01–R-20, metatieto `knowledge/rules/rules_v1.yaml`, Ryhdin vastaavat sääntötunnisteet ja viestit. Laajennuksen ulkopuolinen koodi on varoitus. | – |
| Viejät | Arho-YAML `format_version: 2` (lähde fe456a8), Ryhti-fragmentit, raportti Markdown/CSV/HTML. | 0011 |
| Validointi | Skeemavalidointi (jsonschema laiskasti) ja Syken julkinen rajapinta (stdlib), `ruleId`:n normalisointi. | 0011 |
| Komentorivi | `kma convert`, `kma validate [--syke]`. | 0010, 0011 |
| Testiaineisto v1 | `tests/golden/`: 30 yksikköä Kartta 1:ltä, odotetut tulokset (vahvistamaton luonnos) ja laatuportti. `tools/evaluate.py`. | – |

Testejä on 145 (lisäksi yksi `live`-testi), ruff on puhdas, `build_knowledge.py --check` on
puhdas, ja arkkitehtuuritesti kieltää ytimessä qgis-, PyQt-, openpyxl- ja PDF-kirjastot.

## 2 Kartta 1 – Yhdyskuntarakenne (koko kartta)

```powershell
.\.venv\Scripts\python tools\extract_pdf_text.py lahtoaineistot\Voimassa_olevat_yleiskaavamerkinnat_kantakaupungissa_2025.pdf --out work\kooste.txt
.\.venv\Scripts\kma convert work\kooste.txt --kartta 1 --ulos work\k1 --tiedostonimi kartta1 --html
```

| | Kartta 1 | Koko kooste (kaikki kartat) |
|---|---:|---:|
| Yksiköitä | 66 (2 yleismääräystä, 63 merkintää, 1 informatiivinen) | 231 |
| Jäsennysvaroituksia | 0 | 0 |
| Varmuus korkea / keskitaso / matala | 4 / 10 / 52 | 7 / 39 / 185 |
| Hyväksyttävissä sellaisenaan (ei avoimia kysymyksiä, virheitä eikä varoituksia) | 14 (21 %) | 46 (20 %) |
| Avoimet kysymykset | K5 40, K8 34, K1 5, K7 5, K2 3, K6 1 | K5 153, K8 119, K2 11, K7 14, K6 8, K1 6, K9 2 |
| Sanallisen tekstin poikkeamat (R-19) | 0 | 0 |
| Arho-kirjaston ryhmät (virheettömät) | 26 | 56 |
| Ryhti-fragmentit, skeemavirheet | 52, 0 | 145, 0 |
| Konesuoritusaika | 1,4 s | – |

Avoimet kysymykset kertovat sääntöpohjaisen vaiheen rajan. K5 (ei vakiomääräystä) ja K8
(geometria tuntematon) koskevat erityisesti liikennejärjestelmän merkintöjä, joilla ei ole
tekstiä (VALTAKUNNALLINEN PÄÄVÄYLÄ, PÄÄKOKOOJAKATU …), ja strategisia
kehittämisperiaatemerkintöjä. Niitä ratkaistaan vaiheessa 2.

## 3 Mittarit (luku 2.3) testiaineistolla v1

```powershell
.\.venv\Scripts\python tools\evaluate.py --yksikot
```

Odotetut tulokset ovat kehittäjän luonnoksia (`tila: vahvistamaton`), koska kaavoittajat
eivät ole vielä annotoineet aineistoa. Mittarit kertovat siksi, miten hyvin sääntöpohjainen
muunnos vastaa suunnitelman suosituksia, eivät kaavoittajien hyväksyntää.

| Mittari (luku 2.3) | Tavoite | Vaihe 1 | Huomio |
|---|---|---|---|
| Merkinnät, joiden ehdotus hyväksytään sellaisenaan | ≥ 70 % | **37 %** (11/30) ehdokkaita, joista 11/11 oikein | Ilman käyttäjiä mitataan ehdokkaat: ei avoimia kysymyksiä, virheitä eikä varoituksia. Tavoite edellyttää kielimallia (vaihe 2). |
| Korkean varmuuden ehdotuksista oikein | ≥ 98 % | 3/3 (100 %) | Otos on pieni. Sanallisen määräyksen lajit ovat aina keskitasoa (suunnitelma 8.1), joten korkeaan varmuuteen pääsevät vain tekstittömät merkinnät. |
| Tunnetuista monitulkintaisista kohdista nousee tulkintakysymykseksi | ≥ 90 % | **93 %** (28/30) | Puuttuvat: K1 *Kaupunkivihreän kehittämisalue* (nousee K5:nä) ja K14 *Loma-asuntoalue* (koodia ei löydy). |
| Voimassa olevan kaavan määräystekstin muutokset | 0 kpl | **0** | R-19 ja testi `test_verbal_text_is_source_text_character_by_character`; myös Arho-YAMLin edestakainen luku. |
| Ryhmät latautuvat Arhoon ja läpäisevät Ryhdin määräystason validoinnin | 100 % hyväksytyistä | skeema 100 %; Syke 12/12 valittua ja 27/28 paikallisesti virheetöntä | Arhon latautuminen testataan käsin (luku 5). |
| Käsittelyaika merkintää kohden | vähintään puolittuu | ei mitattavissa | Vaatii käyttäjät; kone käsittelee kartan 1,4 sekunnissa. |

Muut luvun 10.3 mittarit:

| Mittari | Tulos |
|---|---|
| Pääkoodin osuvuus (kaavakohteet) | 19/27 (70 %) |
| Rakenteen osuvuus (lajit ja lisätiedot) | 18/27 (67 %) |
| Kirjaintunnuksen osuvuus | 11/12 (92 %) |
| Ryhmätyyppi oikein | 30/30 |

Väärin tai ilman rakennetta jäivät LOMA-ASUNTOALUE ja YHTEISÖJEN LOMA-ASUNTOALUE
(vapaa-ajan asuminen: sanastosta puuttuu synonyymi), VAK -RATAPIHA, UUSI
JÄTEVEDENPUHDISTAMO, VALTAKUNNALLINEN PÄÄVÄYLÄ, KEHITETTÄVÄ PÄÄKOKOOJAKATU,
VAIHTOPYSÄKKI ja TUTKITTAVA OHJEELLINEN LÄHIJUNA-ASEMA (koodin nimi poikkeaa otsikosta)
sekä SELVITYSALUE (osa-alue-lisätieto puuttuu). Kaikki saavat avoimen tulkintakysymyksen,
joten mikään niistä ei mene läpi sellaisenaan. Laatuportti (`tests/golden/test_golden.py`)
estää tulosten heikkenemisen.

## 4 Syken testirajapinta (live, 22.11.2026)

```powershell
.\.venv\Scripts\kma validate work\k1\kartta1.kma.json --syke --yksikot u001,u002,u003,u004,u009,u018,u020,u030,u032,u049,u052,u055
.\.venv\Scripts\kma validate work\k1\kartta1.kma.json --syke --kaikki --tallenna work\k1\syke_kaikki.json
```

Jokainen ryhmä validoitiin omana synteettisenä yleiskaavanaan (kaavalaji 21, kunta 837,
testiympäristö). Aluevaraukset peittävät kaavan rajauksen, ja yleismääräyksille lisätään
kantava aluevaraus (ADR-0011).

| Ryhmät | HTTP 200 | HTTP 422 |
|---|---:|---:|
| Valitut 12 (2 yleismääräystä, C, c-1, A, EP, W, ke, RL, rautatie, uusi eritasoliittymä, ohjeellinen raitiotie) | 12 | 0 |
| Kaikki 52 vietävää ryhmää | 27 | 25 |
| – paikallisesti virheettömät (28) | 27 | 1 |
| – paikallisesti virheelliset (24) | 0 | 24 |

- Paikallisesti virheelliset ryhmät saivat Sykeltä vastaavan virheen:
  `req-geom-areaobject-additionalinfo-mainuseclass-section-area-mandatory` (21, vrt. R-09
  ja R-08) ja `req-planregulationgroup-letteridentifier-not-null` (4, vrt. R-11).
- Ainoa ristiriita on *Selvitysalue*. Sen geometria on tuntematon (K8 avoin), ja
  synteettinen kaava käytti aluetta. R-08 antaa nyt tällaisesta huomion.
- Ensimmäinen ajo paljasti kaksi synteettisen kaavan puutetta, jotka on korjattu:
  pelkkä yleismääräysryhmä vaatii kaavakohteen (HTTP 400), ja aluevarausten on peitettävä
  kaavan rajaus.

## 5 Arho-kirjaston testiohje (QGIS 3.44.7, Arho asennettuna)

YAMLin latautumista Arhoon ei voi testata ilman QGISia ja Arhon tietokantaa. Testi kestää
noin 15 minuuttia.

1. Tee kirjasto (tai käytä valmista `work\k1\kartta1.arho.yaml`):

   ```powershell
   .\.venv\Scripts\kma convert work\kooste.txt --kartta 1 --ulos work\k1 --tiedostonimi kartta1
   ```

   Ilman paikallista PDF-poimintaa testiaineistosta:

   ```powershell
   .\.venv\Scripts\kma convert tests\golden\kartta1_otos.txt --ulos work\golden --tiedostonimi otos
   ```

2. Avaa QGIS 3.44.7 ja Arho-projekti (yhteys Arhon tietokantaan, josta koodistot luetaan).
3. Avaa Arhon kirjastojen hallinta (*Kirjastot*) ja lisää kaavamääräysryhmäkirjastoksi
   tiedosto `work\k1\kartta1.arho.yaml`.
4. Tarkista:
   - Kirjasto latautuu ilman virheilmoitusta. Kirjaa viesti, jos ilmoitus on esim.
     "Kirjaston tyyppiä ei löytynyt…", "tiedostomuoto on uudempi…" tai
     `Invalid regulation code in config: <koodi>` (TemplateSyntaxError).
   - Kirjastossa on 26 ryhmää kategorioittain (*Kartta 1 - Yhdyskuntarakenne / Maankäyttö*,
     */ Strategiset kehittämisperiaatemerkinnät*, */ Liikennejärjestelmä*).
   - Ryhmä **Täydentyvä keskusta (c-1)**: kehittämisvyöhyke, jolla lisätiedot osa-alue ja
     käyttötarkoituskohdistus → keskustatoimintojen alue. Lisäksi sanallinen määräys, jonka
     teksti alkaa "Aluetta kehitetään täydennettävänä…", ja lajit kaupan ohjaus,
     kehittämisperiaate ja täydennysrakentaminen.
   - Ryhmä **Keskustatoimintojen alue (C)**: pääkäyttötarkoitus ja koko teksti
     muuttumattomana. Vertaa merkki merkiltä raporttiin `kartta1_raportti.md`.
   - Ryhmä **Ohjeellinen uusi leirintäalue (RL)**: lisätiedot pääkäyttötarkoitus, ohjeellinen
     sijainti ja uusi.
5. Piirrä testikaavaan yksi aluekohde ja liitä siihen ryhmä *Keskustatoimintojen alue*.
   Lisäksi päällekkäinen kohde ryhmällä *Täydentyvä keskusta*. Aja Arhon validointi, jos
   taustajärjestelmä on käytettävissä.
6. Valinnainen: tee kirjasto valitsimella `--myos-keskeneraiset` (50 ryhmää, myös
   puutteelliset) ja tarkista, että sekin latautuu.
7. Kirjaa tulos tämän tiedoston loppuun (*Arho-testin tulokset*): latautuiko kirjasto, kuinka
   monta ryhmää näkyi, virheilmoitukset sanatarkasti ja huomiot (esim. näkyykö
   `geometry`-kenttä, toimiiko `code_value` lisätiedolla).

## 6 Mitä jäi käyttäjälle

- **Arho-latautumistesti** (luku 5).
- **Odotettujen tulosten vahvistus**: kaavoittajat käyvät `tests/golden/kartta1_odotetut.yaml`:n
  läpi. Erityisesti K1-tapaukset (c-1–c-4, km), sekoittuneet alueet (K2), VAK-ratapiha ja
  loma-asuntoalueet. Kun odotukset on vahvistettu, `tila: vahvistettu` ja mittarit ajetaan uudelleen.
- **Normalisoinnin vahvistettavat kohdat**: raportissa ovat kohdassa "Vahvistettavat
  normalisoinnit" (esim. `vapaa-⏎ajan`, `MRL128`, kahdentuneet tunnukset `pvpv`). Lähde on
  kooste, joten teksti on lisäksi tarkistettava alkuperäistä kaava-asiakirjaa vasten
  (suunnitelma 3.7).
- **Linjausten lukitus** (ADR-0010), kun yleiskaavoitus päättää. Erityisesti L-04 ja L-05,
  joiden oletus poikkeaa suunnitelman alkuperäisestä VOOKA-suosituksesta.
- **Liitteen 4 korjausten vahvistus** (tehtävä 7, ennallaan).

## 7 Havaintoja vaiheen 2 kannalta

1. **Kielimallin työ on selvästi rajattavissa.** Sääntöpohjainen vaihe ratkaisee liitteen 4
   mukaiset ja määreelliset merkinnät. Avoimiksi jäävät K5 (lähin koodi), K8 (geometria),
   K1/K2 (rakenteen valinta) ja sanallisen määräyksen lajit. Kielimallille kannattaa antaa
   vaiheen 1 löydökset ja tulkintakysymykset valmiina, kuten luvussa 6.5 on suunniteltu.
2. **Sanallisen määräyksen lajit ovat heikoin sääntöpohjainen osa.** Sanastohaku löytää
   aiheita, mutta painottaa toistuvia sanoja (esim. *joukkoliikenteen* osuu sekä liikenteeseen
   että joukkoliikenteeseen). Lajien valinta ja niiden lukumäärä (L-09) sopivat kielimallille,
   ja sääntöpohjainen tulos voi toimia vihjeenä ja vertailukohtana.
3. **Liitteen 4 otsikot eroavat koosteesta.** Esimerkiksi *Asuntoalue* ↔ ASUMISEN ALUE.
   Koodiyhdistelmähaku löytää kirjaintunnuksen silloinkin, kun otsikko poikkeaa. Synonyymit
   (loma-asunto = vapaa-ajan asuminen, pääväylä = valtatie) kannattaa kerätä sanastoon tai
   antaa mallille.
4. **Opas 3.1.1 ja Katja 2 § ovat jännitteessä.** Esimerkiksi c-1:n koodiyhdistelmä vastaa
   liitteen 4 otsikkoa *Keskustatoimintojen kehittämisvyöhyke*. R-15 antaa tästä huomion,
   koska sanallinen määräys laajentaa tietosisältöä. Asia kannattaa linjata (esim. L-15):
   käytetäänkö lähteen otsikkoa vai Katjan otsikkoa.
5. **L-04 ja R-12.** Oletuksella `sanallinenMaarays` kehittämisvyöhyke saa huomion, koska
   opas edellyttää suunnittelumääräystä. Kun L-04 lukitaan, R-12:n alatapaus kannattaa
   tarkistaa.
6. **Syken validointi on luotettava vertailukohta.** Paikalliset säännöt ja Syke olivat 51/52
   ryhmässä samaa mieltä. Syke ei tarkista poistuneita koodeja eikä kaavalajin
   määrityshierarkiaa, joten R-01 on tarpeen (vaihe 0). Arviointiajuri voi ajaa Syken
   validoinnin osana vaiheen 2 regressiota (merkintä `live`).
7. **Jäsennin on koosteeseen sidottu.** Keskustan kartoilla (1a–2) on alaotsikoita ja
   numeroituja osa-alueita (K9), joita jäsennin ei vielä erottele kunnolla. Kielimallin
   jäsennysapu (luku 6.5 kohta 3) tai `@`-ohjeet ratkaisevat ne.
8. **Vahvistamaton testiaineisto rajoittaa mittareita.** Ennen kuin kielimallia arvioidaan,
   tarvitaan kaavoittajien annotointi (luku 10.2) ja testiaineiston laajennus 80–120
   yksikköön. Muuten mitataan vain vastaavuutta kehittäjän tulkintaan.

## Arho-testin tulokset

*(käyttäjä täyttää: päivämäärä, Arhon versio, latautuiko, ryhmien määrä, virheilmoitukset, huomiot)*
