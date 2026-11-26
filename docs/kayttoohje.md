# Kaavamääräysavustaja – käyttöohje (kokeiluversio 0.3, vaihe 3a)

Ohje on paikkatietoasiantuntijalle. Lisäosa muuntaa sanallisen kaavamääräyksen Katja-asetuksen
mukaiseksi kaavamääräysryhmäksi QGISissa, ilman Arhoa. Kokeiluversiossa muunnetaan yksi
määräys kerrallaan (tai lyhyt liitetty selite). Palaute kirjataan tiedostoon
[`palaute_vaihe3.md`](palaute_vaihe3.md) (tehtävät T-01 ja T-02,
[`kayttajan_tehtavat.md`](kayttajan_tehtavat.md)).

Ehdotus on aina ehdotus: avustaja perustelee jokaisen valinnan ja kysyy monitulkintaiset kohdat,
ja sinä päätät. Mitään ei toimiteta Ryhtiin.

## 1 Asennus

Edellytykset: QGIS 3.40–3.44 (testattu 3.44.7, OSGeo4W). Arhoa ei tarvita.

1. **Linkitä lisäosa** QGIS-profiiliin (kerran; tällä työasemalla linkki on jo olemassa).
   PowerShell säilön juuresta:

   ```powershell
   New-Item -ItemType Junction -Path "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\kaavamaaraysavustaja" -Target (Resolve-Path .\kaavamaaraysavustaja)
   ```

   Linkki osoittaa säilöön, joten `git pull` päivittää lisäosan. Käynnistä QGIS uudelleen
   päivityksen jälkeen (tai käytä Plugin Reloader -lisäosaa).
2. **Ota käyttöön**: *Lisäosat → Hallitse ja asenna lisäosia → Asennetut* → rasti
   *Kaavamääräysavustaja* (kokeelliset lisäosat on sallittava *Asetukset*-välilehdellä).
3. **Kielimallin SDK** (valinnainen; ilman sitä muunnos on sääntöpohjainen). Asennettu tälle
   työasemalle 22.11.2026 (ADR-0002). Muualla OSGeo4W Shellissä:

   ```bat
   python -m pip install --only-binary=:all: --target "%APPDATA%\QGIS\QGIS3\profiles\default\python\kma_deps" "anthropic>=2.12" "mistralai>=1.0"
   ```

   Lisäosa lisää `kma_deps`-kansion Pythonin hakupolun loppuun. Tarkista *Lisäosat →
   Kaavamääräysavustaja → Tietoja*: rivillä "Kielimallien SDK:t" pitäisi lukea "claude ✓".
4. Avaa telakka: *Lisäosat → Kaavamääräysavustaja → Kaavamääräysavustaja* tai työkalurivin
   painike. Telakan yläreunassa näkyy tila, tietopohja (TP-2026.11-3) ja kehoteversio
   (prompts/v3).

## 2 API-avaimet

Avaimia tarvitaan vain kielimalliin (Claude tai Mistral) ja Syken validointiin.

- *Lisäosat → Kaavamääräysavustaja → API-avaimet…* (tai telakan *Avaimet…*). Kirjoita avain
  ja paina *Tallenna*. QGIS kysyy pääsalasanan kerran istunnossa.
- Avain tallentuu QGISin salattuun tunnistetietovarastoon. Sitä ei kirjoiteta projektiin,
  muunnokseen, raporttiin eikä lokiin, eikä dialogi näytä sitä.
- Jos varastossa ei ole avainta, käytetään ympäristömuuttujaa (`ANTHROPIC_API_KEY`,
  `MISTRAL_API_KEY`, `RYHTI_API_KEY`); dialogi kertoo, kumpaa käytetään.

## 3 Uuden määräyksen muunnos (laadinta)

1. *1 Syöte*: **Tila** *Uusi määräys (laadinta)*, **Kaavataso** *Yleiskaava*, **Syöte** *Yksi
   määräys*, **Ryhmän tyyppi** *Kaavakohteen määräys* tai *Yleismääräys*.
2. Kirjoita **Otsikko** (esim. "Kerrostalovaltainen asuntoalue"), halutessasi
   **Kirjaintunnus**, ja **Määräysteksti**. Tyhjä rivi erottaa kappaleet. Tekstin voi myös avata
   tiedostosta (*Avaa tekstitiedosto…*).
3. **Kielimalli**: *Ei kielimallia* riittää kokeiluun. Claude tarkentaa epävarmat kohdat
   (sanallisen määräyksen lajit, lähimmän koodin, kysymykset); ks. luku 5.
4. Paina **Muunna**. Muunnos ajetaan taustalla (QGIS pysyy käytettävänä), ja tulos avautuu
   *2 Ehdotus* -välilehdelle.

Mitä avustaja tekee laadintatilassa:

- ehdottaa Katja-asetuksen liitteen 4 mukaisen rakenteen, otsikon ja kirjaintunnuksen, jos ne
  vastaavat tekstiä (muuten lähimmän koodin ja kysymyksen K5)
- antaa **yhden numeroarvon suureena** (esim. "6 000 k-m²" → sallittu kerrosala 6000 k-m²,
  "e=0,6" → tehokkuusluku). Teksti säilyy; huomio kertoo, että arvo on myös suureena. Useita
  arvoja ei muuteta suureiksi (ryhmässä voi olla vain yksi suure).
- kysyy **K13 Määräys vai suositus?**, kun kappaleessa on "suositellaan" tai vastaava ilmaus.
  Valinta *Kaavasuositus* siirtää kappaleen kaavasuositukseksi.
- **ei muuta tekstiä**. Muotoiluehdotukset eivät kuulu tähän versioon.

## 4 Voimassa olevan määräyksen muunnos (VOOKA)

1. **Tila** *Voimassa oleva määräys (VOOKA)*.
2. Joko **Yksi määräys** (otsikko, tunnus, teksti) tai **Liitetty selite**: liitä koosteen
   selitteen pätkä sellaisenaan, esim.

   ```text
   @kartta Kartta 1 - Yhdyskuntarakenne
   KESKUSTATOIMINTOJEN ALUE
   Alue varataan julkisille ja yksityisille palveluille.
   c-1 TÄYDENTYVÄ KESKUSTA
   Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
   ```

   Otsikot isoin kirjaimin, tunnus otsikon alussa; `@`-ohjerivit kuten komentorivillä
   (ADR-0009). *Kartta*-kenttään voi rajata yhden kartan.
3. **Muunna**. VOOKA-tilassa sanallinen teksti siirtyy merkki merkiltä lähteen mukaisena
   (sääntö R-19 tarkistaa sen), ja linjaukset (esim. L-06 kirjaintunnus) ratkaisevat osan
   kysymyksistä.

## 5 Kielimalli, kustannusarvio ja budjetti

- Valitse *Kielimalli: Claude* ja aseta **Budjettiraja ajoa kohden** (oletus 2 $).
- Sääntöpohjainen muunnos tehdään aina ensin. Kielimallille lähetetään vain yksiköt, joita se
  ei ratkaissut varmasti.
- **Ennen jokaista kielimallikutsua** avautuu kustannusarvio: kutsujen määrä, arvio dollareina
  ja budjettiraja. *Näytä lähetettävä sisältö* näyttää kaiken, mitä lähetetään (järjestelmäohje,
  tietopohjan konteksti, määräysteksti). PDF:iä, kuvia tai avaimia ei lähetetä. Valinnan
  *Näytä lähetettävä sisältö ennen lähetystä* voi asettaa pysyväksi.
- *Lähetä kielimallille* aloittaa ajon; *Peruuta* jättää tuloksen sääntöpohjaiseksi.
- Kun budjettiraja tulee vastaan, loput yksiköt jäävät sääntöpohjaisiksi. *Keskeytä* lopettaa
  ajon: käsittelyssä oleva kutsu valmistuu, loput jäävät sääntöpohjaisiksi.
- Yksi kutsu maksaa noin 0,05–0,08 $ (ensimmäinen noin 0,30 $, koska kontekstin välimuisti
  kirjoitetaan) ja kestää 15–30 s.
- Ilman SDK:ta tai avainta telakka ilmoittaa syyn ja tekee sääntöpohjaisen muunnoksen.

## 6 Ehdotuksen tarkastelu

*2 Ehdotus*:

- **Lista**: yksiköt tilakuvakkeineen: ✔ valmis, ? avoin tulkintakysymys, ⚠ sääntövaroitus,
  ✖ sääntövirhe, – ei kaavamääräys. *Suodata* rajaa listan.
- **Tiedot** valitusta yksiköstä:
  - otsikko, kirjaintunnus, geometria, **varmuus** ja sen peruste
  - **Rakenne** kaavoittajan kielellä (esim. "Asuinpientaloalue (Pääkäyttötarkoitus)",
    "Sallittu kerrosala: 6000 k-m²", sanallinen määräys lajeineen, kaavasuositukset)
  - **Tekninen näkymä**: koodit ja URIt
  - **Perustelut** menetelmineen, varmuuksineen ja lainauksineen lähdetekstistä
  - **Sääntötarkistus** (R-01…R-20) ja lähdeteksti
- Kielimallin hylkäämät vaihtoehdot näkyvät perusteluissa ("Hylätty vaihtoehto: …").

## 7 Tulkintakysymysten ratkaiseminen

1. Valitse yksikkö ja kysymys (avoimet ensin). Kortti näyttää kysymyksen, perusteen ja
   vaihtoehdot seurauksineen; avustajan suositus on valittuna.
2. Valitse vaihtoehto ja **Laajuus**:
   - *Vain tämä merkintä*
   - *Kaikki samankaltaiset tässä muunnoksessa* (sama tunnuksen perusosa, esim. c-1…c-4,
     sama otsikko ilman määreitä tai sama teksti)
3. Kirjoita halutessasi perustelu ja paina **Tallenna ratkaisu**. Ratkaisu menee päätöslokiin.
4. Paina **Aja uudelleen ratkaisuin**. Ratkaisu vaikuttaa rakenteeseen (esim. K13 → kaavasuositus,
   K1 → osa-alue, K8 → geometria) ja säilyy jokaisessa uudelleenajossa. Aiemmat
   kielimallivastaukset käytetään uudelleen ilman kustannusta, kun kielimalli on edelleen
   valittuna.

Linjauksella ratkaistua kysymystä (esim. "ratkaistu: linjaus L-06") ei muuteta kortissa.
Vaihda linjausvalinta *1 Syöte → Linjausvalinnat* -kohdasta (lukitut linjaukset 🔒 eivät ole
muutettavissa).

## 8 Vienti ja validointi

*3 Vienti*: valitse kansio ja tiedostonimen alku, rastita muodot ja paina **Vie**.

| Tiedosto | Sisältö |
|---|---|
| `<nimi>.kma.json` | muunnosprojekti: syöte, ehdotukset, perustelut, ratkaisut ja kielimallin vastaukset; avaa myöhemmin *Avaa aiempi muunnos* -painikkeella |
| `<nimi>_raportti.md` / `.html` | muunnosraportti kaavoittajan kielellä |
| `<nimi>.ryhti.json` | Ryhti-JSON: kaavamääräysryhmät ja yleismääräysryhmät |
| `<nimi>.arho.yaml` | valinnainen Arhon kaavamääräysryhmäkirjasto (ryhmät, joissa on sääntövirheitä, jätetään pois, ellei toisin valita) |

Ryhti-skeematarkistus ohitetaan QGISissa, koska `jsonschema`-paketti puuttuu (ilmoitus
näkyy). **Validoi Syken testiympäristössä** lähettää ryhmät (enintään valittu määrä) Syken
julkiseen validointirajapintaan synteettisenä testikaavana; kaavatason havainnot suodatetaan
pois. Tarvitset Syken avaimen (luku 2).

## 9 Aiemman muunnoksen jatkaminen

*1 Syöte → Avaa aiempi muunnos (*.kma.json)*: projekti avautuu ratkaisuineen. Yhden määräyksen
syöte palautuu kenttiin; selitteen teksti liitetään uudelleen. *Muunna* tai *Aja uudelleen
ratkaisuin* säilyttää ratkaisut ja käyttää aiemmat kielimallivastaukset. *Uusi muunnos*
tyhjentää syötteen, ratkaisut ja tuloksen.

## 10 Tunnetut rajoitukset

- Yksi määräys tai lyhyt selite kerrallaan; koko koosteen eräkäsittely, jäsennystaulukko ja
  rakenteen muokkaus koodivalitsimilla tulevat palautteen mukaan.
- Ehdotusta ei voi muokata käsin telakassa: rakenteeseen vaikutetaan ratkaisuilla ja
  linjausvalinnoilla.
- Laadintatilan muotoiluehdotuksia ei ole.
- Välityspalvelinta ei ole testattu (tällä työasemalla sitä ei tarvita).
- Käyttöliittymä on vain suomeksi.

## 11 Ongelmatilanteet

- *Tietopohjaa ei voitu ladata*: aja säilössä `python tools\build_knowledge.py --check`.
- *Kielimallin SDK puuttuu*: asenna luvun 1 kohta 3.
- *API-avain puuttuu*: luku 2. Pääsalasanadialogi voi jäädä QGIS-ikkunan taakse.
- Virheen tarkemmat tiedot: *Näkymä → Paneelit → Lokiviestit*, välilehti *Kaavamääräysavustaja*.
