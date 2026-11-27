# Kaavamääräysavustaja – käyttöohje (kokeiluversio 0.3.4, vaihe 3a)

Ohje on paikkatietoasiantuntijalle. Lisäosa muuntaa sanallisen kaavamääräyksen Katja-asetuksen
mukaiseksi kaavamääräysryhmäksi QGISissa, ilman Arhoa. Kokeiluversiossa muunnetaan yksi
määräys kerrallaan (tai lyhyt liitetty teksti). Palaute kirjataan tiedostoon
[`palaute_vaihe3.md`](palaute_vaihe3.md) (tehtävät T-01 ja T-02,
[`kayttajan_tehtavat.md`](kayttajan_tehtavat.md)). Versio 0.3.1 korjasi ensimmäisen
palautekierroksen havainnot P1-01–P1-09, versio 0.3.2 toisen kierroksen havainnot P2-01–P2-03
ja versiot 0.3.3–0.3.4 havainnon P3-01 (kaavamääräyslajin ja lisätietojen valinta koodistosta).

Ehdotus on aina ehdotus: avustaja perustelee jokaisen valinnan ja kysyy monitulkintaiset kohdat,
ja sinä päätät. Mitään ei toimiteta Ryhtiin.

## 1 Asennus

Edellytykset: QGIS 3.40–3.44 (testattu 3.44.7, OSGeo4W). Arhoa ei tarvita.

1. **Linkitä lisäosa** QGIS-profiiliin (kerran; tällä työasemalla linkki on jo olemassa).
   PowerShell säilön juuresta:

   ```powershell
   New-Item -ItemType Junction -Path "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\kaavamaaraysavustaja" -Target (Resolve-Path .\kaavamaaraysavustaja)
   ```

   Linkki osoittaa suoraan säilön työhakemistoon, joten QGIS käyttää aina sitä koodia, joka
   kansiossa on: muutokset näkyvät QGISissa ilman erillistä asennusta tai `git pull`ia
   (`git pull` tarvitaan vain, jos koodia on muutettu toisessa kloonissa tai koneella).
   Jos QGIS oli auki muutosten aikana, käynnistä se uudelleen (tai käytä Plugin Reloader
   -lisäosaa), jotta uusi koodi latautuu.
2. **Ota käyttöön**: *Lisäosat → Hallitse ja asenna lisäosia → Asennetut* → rasti
   *Kaavamääräysavustaja* (kokeelliset lisäosat on sallittava *Asetukset*-välilehdellä).
3. **Kielimallin SDK** (valinnainen; ilman sitä muunnos on sääntöpohjainen). Asennettu tälle
   työasemalle 22.11.2026. Muualla OSGeo4W Shellissä:

   ```bat
   python -m pip install --only-binary=:all: --target "%APPDATA%\QGIS\QGIS3\profiles\default\python\kma_deps" "anthropic>=2.12" "mistralai>=1.0"
   ```

   Lisäosa lisää `kma_deps`-kansion Pythonin hakupolun loppuun. Tarkista *Lisäosat →
   Kaavamääräysavustaja → Tietoja*: rivillä "Kielimallien SDK:t" pitäisi lukea "claude ✓".
4. Avaa telakka: *Lisäosat → Kaavamääräysavustaja → Kaavamääräysavustaja* tai työkalurivin
   painike. Telakan yläreunassa näkyy muunnostila ja se, minkä ajankohdan koodistoja ja
   sääntöjä avustaja käyttää (esim. *Koodistot ja säännöt: marraskuu 2026*). Kun viet hiiren
   rivin päälle, näet tarkemmat tunnisteet: tietopohja (esim. TP-2026.11-3) on avustajan
   käyttämä koodistojen, Katja-asetuksen liitteen 4, tarkistussääntöjen, linjausten ja
   kielimallin ohjeiden kokonaisuus, ja sen tunnus kirjataan muunnokseen, jotta tuloksen voi
   toistaa.

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
   määräys: otsikko ja teksti erikseen*, **Ryhmän tyyppi** *Kaavakohteen määräys* tai
   *Yleismääräys*.
2. Kirjoita **Otsikko** (esim. "Kerrostalovaltainen asuntoalue"), halutessasi
   **Kirjaintunnus**, ja **Määräysteksti**. Tyhjä rivi erottaa kappaleet. Tekstin voi myös avata
   tiedostosta (*Avaa tekstitiedosto…*). Jos otsikko ja tunnus ovat valmiiksi tekstissä, voit
   käyttää myös syötettä *Liitetty teksti* (luku 4).
3. **Kielimalli**: *Ei kielimallia* riittää kokeiluun. Claude tarkentaa epävarmat kohdat
   (sanallisen määräyksen lajit, lähimmän koodin, kysymykset); ks. luku 5.
4. Paina **Muunna**. Muunnos ajetaan taustalla (QGIS pysyy käytettävänä), ja tulos avautuu
   *2 Ehdotus* -välilehdelle.

Mitä avustaja tekee laadintatilassa:

- ehdottaa Katja-asetuksen liitteen 4 mukaisen rakenteen, otsikon ja kirjaintunnuksen, jos ne
  vastaavat tekstiä (muuten lähimmän koodin ja kysymyksen *Ei sopivaa Katja-koodia*)
- antaa **yhden numeroarvon suureena** (esim. "6 000 k-m²" → sallittu kerrosala 6000 k-m²,
  "e=0,6" → tehokkuusluku). Teksti säilyy; huomio kertoo, että arvo on myös suureena. Useita
  arvoja ei muuteta suureiksi (ryhmässä voi olla vain yksi suure).
- kysyy **Määräys vai suositus?**, kun kappaleessa on "suositellaan" tai vastaava ilmaus.
  Valinta *Kaavasuositus* siirtää kappaleen kaavasuositukseksi.
- **ei muuta tekstiä**. Muotoiluehdotukset eivät kuulu tähän versioon.

## 4 Voimassa olevan määräyksen muunnos (VOOKA)

1. **Tila** *Voimassa oleva määräys (VOOKA)* (VOOKA = voimassa olevan kaavan muunnos).
2. Joko **Yksi määräys** (otsikko, tunnus ja teksti omiin kenttiinsä) tai **Liitetty teksti:
   otsikko ja kirjaintunnus tekstissä (yksi tai useampi merkintä)**. Liitetty teksti sopii myös
   yhdelle merkinnälle: otsikko ja tunnus luetaan tekstistä, joten niille ei ole omia kenttiä.
   Kummallakin syötteellä on oma tekstinsä: kun vaihdat syötettä, toisen syötteen teksti
   säilyy tallessa ja palaa, kun vaihdat takaisin. Telakan katkoviivalaatikko on malli, ei
   syötettä. Muoto: merkinnän otsikko omalla rivillään ISOIN KIRJAIMIN, kirjaintunnus otsikon
   alussa ja määräysteksti seuraavilla riveillä. Yksi merkintä:

   ```text
   c-1 TÄYDENTYVÄ KESKUSTA
   Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
   ```

   Useita merkintöjä ja kartta:

   ```text
   @kartta Kartta 1 - Yhdyskuntarakenne
   KESKUSTATOIMINTOJEN ALUE
   Alue varataan julkisille ja yksityisille palveluille.
   c-1 TÄYDENTYVÄ KESKUSTA
   Aluetta kehitetään täydennettävänä keskustatoimintojen alueena.
   ```

   Yleismääräykset kirjoitetaan otsikon YLEISMÄÄRÄYKSET alle. `@`-alkuiset ohjerivit
   (esim. `@kartta`, `@osio`) toimivat kuten komentorivillä. Jos jokin rivi jää tunnistamatta
   (esim. otsikko ei ole isoin kirjaimin tai teksti on ennen ensimmäistä otsikkoa), telakka
   kertoo ohitetut rivit.
3. **Kartta**: jos tekstissä on useita karttoja (rivit `@kartta Kartta 1 - Nimi` tai otsikot
   `KARTTA 1 - NIMI`), telakka näyttää karttavalinnan. Valitse muunnettava kartta tai *Kaikki
   kartat*. Kartan nimi kirjataan muunnosraporttiin ja Arho-kirjaston kuvaukseen, ja merkinnät
   ryhmitellään kirjastossa kartan mukaan. Kun tekstissä on yksi kartta, sen nimi kirjataan
   ilman valintaa. Yksi määräys ei kuulu karttaan, joten sille valintaa ei näytetä.
4. **Muunna**. VOOKA-tilassa sanallinen teksti siirtyy merkki merkiltä lähteen mukaisena
   (tarkistussääntö R-19 varmistaa sen), ja linjaukset (esim. *Kirjaintunnukset*) ratkaisevat
   osan kysymyksistä (luku 7).

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
- **Ehdotus**-välilehti valitusta yksiköstä:
  - otsikko, kirjaintunnus, geometria, **varmuus** ja sen peruste
  - **Rakenne** kaavoittajan kielellä (esim. "Asuinpientaloalue (Pääkäyttötarkoitus)",
    "Sallittu kerrosala: 6000 k-m²", sanallinen määräys lajeineen, kaavasuositukset)
  - **Tekninen näkymä**: koodit ja URIt
  - **Perustelut**: menetelmä (esim. Katja-asetuksen liite 4, sanasto, linjaus), varmuus,
    lähde ja lainaus lähdetekstistä
  - **Sääntötarkistus**: tarkistussäännön nimi ja tunnus (esim. R-15) sekä viesti
  - lähdeteksti
- **Ryhti-JSON**-välilehti näyttää valitun yksikön tai koko muunnoksen (*Näytä*) Ryhti-JSONin
  täsmälleen sellaisena kuin vienti kirjoittaa sen; *Kopioi* vie sen leikepöydälle. Yläpuolella
  kerrotaan, onko tulkintakysymyksiä avoinna (JSON perustuu silloin avustajan suosituksiin), onko
  sääntövirheitä ja onko tallennettuja ratkaisuja tai lisätietojen muutoksia, jotka näkyvät vasta
  uudelleenajon jälkeen. Jos yksikköä ei viedä (esim. ei kaavamääräys), syy kerrotaan.
- **Lisätiedot**-välilehdellä lisäät ja poistat valitun yksikön lisätietoja (luku 7,
  *Lisätietojen lisäys ja poisto*).
- **Onko tulos Ryhti-kelpoinen?** Vain sääntö*virhe* estää Ryhdin hyväksynnän. *Varoitus*
  kannattaa tarkistaa, ja *huomio* on tiedoksi: sitä ei tarvitse eikä yleensä voi korjata
  telakassa (esim. huomio siitä, että numeroarvo on sekä tekstissä että suureena; teksti on
  laatijan). Kun virheitä ei ole, Ryhti-JSON-välilehti sanoo *Avustajan tarkistussäännöt: ei
  virheitä*. Ryhdin oman tarkistuksen saat kohdassa *3 Vienti → Validoi Syken
  testiympäristössä* (luku 8).
- Tekstien tunnisteet näytetään selitettyinä: linjaus nimellään (esim. *linjaus
  Kirjaintunnukset (L-06)*), tulkintakysymys tyypillään (esim. *Kirjaintunnus (tulkintakysymys
  K14)*) ja sääntö sanalla *tarkistussääntö*.
- Kielimallin hylkäämät vaihtoehdot näkyvät perusteluissa ("Hylätty vaihtoehto: …").

## 7 Tulkintakysymysten ratkaiseminen

1. Valitse yksikkö ja kysymys (avoimet ensin). Listarivi kertoo kysymyksen ja tilan (avoin,
   ratkaisit itse, ratkaistu linjauksella …); kysymystyyppi tunnuksineen näkyy työkaluvihjeessä.
2. Kortti näyttää kysymyksen ja perusteen, **kuka kysymyksen ratkaisi** ja **miten ratkaisua
   voi muuttaa**:

   | Ratkaisija | Miten muutetaan |
   |---|---|
   | Avoin kysymys | Avustajan suositus on valittuna. Valitse vaihtoehto ja laajuus ja paina *Tallenna ratkaisu*. |
   | Sinä | Omat ratkaisut ovat aina muutettavissa: valitse toinen vaihtoehto ja tallenna, tai *Poista oma ratkaisu* (kysymys palaa avoimeksi). Jos ratkaisit kysymyksen samankaltaiselle merkinnälle laajuudella *kaikki samankaltaiset*, kortti kertoo merkinnän; voit tallentaa tälle merkinnälle oman ratkaisun. |
   | Kielimalli | Voit korvata ratkaisun omallasi. |
   | Linjaus | Linjaus koskee koko muunnosta. Valitse kortissa toinen vaihtoehto ja *Vaihda linjaus ja aja uudelleen*. Valinta on sama kuin *1 Syöte → Linjausvalinnat*, ja se kirjataan tämän muunnoksen linjausvalinnaksi. |
   | Lukittu linjaus 🔒 | Ei muutettavissa: Tampere on päättänyt linjauksesta, ja kortti kertoo, kuka päätti ja milloin. |
   | Muunnostila | Voimassa olevan määräyksen tekstiä ei muuteta (esim. vanhentunut lakiviittaus jää ennalleen). Jos teksti laaditaan uudelleen, valitse tila *Uusi määräys (laadinta)*. |

   **Ei sopivaa Katja-koodia**: jos avustaja ei löydä merkinnälle koodia, ryhmään tulee vain
   sanallinen määräys (ja sääntövirhe). Valitse kortin kohdasta *Tai valitse kaavamääräyslaji
   itse kansallisesta koodistosta* sopiva laji: kirjoita hakusana (esim. "työpaikka"), valitse
   listasta (kuvaus näkyy alla) ja paina **Tallenna koodi ratkaisuksi**. Uudelleenajossa ryhmän
   rakenne tehdään valitusta koodista: aluevaraus saa pääkäyttötarkoituksen ja kirjaintunnuksen
   liitteestä 4, jos sillä on siellä rivi (esim. *Työpaikkojen alue* → TP). Sanallinen teksti
   säilyy ennallaan. Lista sisältää kaavatason kaavamääräyslajit ilman otsikkotason koodeja,
   sanallisia määräyksiä ja suureita. Ryhmää, jonka koodin valitsit itse, ei lähetetä
   kielimallille. Lisätiedot (esim. *ympäristö asettaa toiminnan laadulle erityisiä
   vaatimuksia*) valitaan sen jälkeen Lisätiedot-välilehdellä (alla).
3. **Laajuus**: *Vain tämä merkintä* tai *Kaikki samankaltaiset tässä muunnoksessa* (sama
   tunnuksen perusosa, esim. c-1…c-4, sama otsikko ilman määreitä tai sama teksti). Kirjoita
   halutessasi perustelu ja paina **Tallenna ratkaisu**. Ratkaisu menee päätöslokiin, ja kortti
   näyttää ⏳-merkin, kunnes ajat muunnoksen uudelleen.
4. Paina **Aja uudelleen ratkaisuin**. Ratkaisu vaikuttaa rakenteeseen (esim. *Määräys vai
   suositus* → kaavasuositus, *Aluevaraus vai osa-alue* → osa-alue, *Geometriatyyppi* →
   geometria) ja säilyy jokaisessa uudelleenajossa. Aiemmat kielimallivastaukset käytetään
   uudelleen ilman kustannusta, kun kielimalli on edelleen valittuna.

### Lisätietojen lisäys ja poisto

Lisätiedot täydentävät kaavamääräystä (koodisto RY_Kaavamaarayksen_Lisatiedonlaji), esim.
*pääkäyttötarkoitus*, *uusi* tai *ympäristö asettaa toiminnan laadulle erityisiä vaatimuksia*.
Avustaja ehdottaa lisätiedot liitteestä 4, koodistosta tai sanastosta; voit lisätä niitä ja
poistaa minkä tahansa, myös avustajan ehdottaman. Rakenne voi tulla mistä tahansa (liite 4,
koodin nimi, sanasto tai oma kaavamääräyslajin valinta).

1. Valitse yksikkö ja avaa *2 Ehdotus* → **Lisätiedot**.
2. Ylhäällä näkyy **päämääräys** (ryhmän ensimmäinen muu kuin sanallinen määräys, esim.
   *Työpaikkojen alue*). Jos ryhmässä on muitakin ei-sanallisia määräyksiä (esim. suure
   *Sallittu kerrosala*), valitse kohde kohdasta **Määräys**. Jos ryhmässä on vain sanallinen
   määräys, valitse ensin kaavamääräyslaji (*Ei sopivaa Katja-koodia*) ja aja muunnos uudelleen.
3. Luettelo näyttää kohteen lisätiedot: *(avustajan ehdotus)*, *(lisäsit)* tai muutoksen tila
   (⏳ *lisätään*, *poistetaan* tai *palautetaan, kun ajat uudelleen*; *poistit*).
4. **Lisää**: kirjoita hakusana kenttään *Lisää lisätieto* (esim. "ympäristö"), valitse listasta
   (kuvaus näkyy alla) ja paina **Lisää lisätieto**. Jos lisätiedolla on arvo (esim.
   *käyttötarkoituskohdistus*, *poisluettava käyttötarkoitus*), valitse arvoksi kaavamääräyslaji
   kentästä *Arvo*. Perustelu on valinnainen ja näkyy perusteluissa ja raportissa.
5. **Poista**: valitse lisätieto luettelosta ja paina **Poista lisätieto**. Samasta painikkeesta
   voit perua tallennetun muutoksen (*Peru lisäys*, *Peru poisto*) tai palauttaa poistamasi
   (*Palauta lisätieto*).
6. Paina **Aja uudelleen muutoksin** (tai *Aja uudelleen ratkaisuin*). Muutos näkyy rakenteessa,
   perusteluissa (*Käyttäjä lisäsi lisätiedon …*), raportissa ja Ryhti-JSONissa.

Huomaa:

- Valittavissa ovat kaavatason voimassa olevat lisätiedon lajit ilman otsikkotason koodeja.
  Lajit, joiden arvo on luku, arvoväli tai aikaväli (esim. *käyttötarkoituksen osuus
  kerrosalasta*, *väliaikainen määräys*) tai jonka koodisto ei ole tietopohjassa (*rakennusluvan
  peruste*), eivät vielä ole valittavissa.
- Muutos koskee vain tätä merkintää. Se säilyy uudelleenajoissa ja tallentuu muunnosprojektiin,
  ja se palautuu, kun avaat aiemman muunnoksen. Päämääräykseen tehty muutos säilyy, vaikka
  vaihtaisit kaavamääräyslajia. Numeroidut alakohdat (esim. *1. HERVANNAN ALUE*) saavat
  yläkohdan rakenteen muutoksineen; perustelu kertoo sen, ja alakohdan lisätietoja voi muuttaa
  erikseen.
- Tarkistussäännöt tarkistavat tuloksen, eikä avustaja estä ristiriitaista muutosta. Esimerkiksi
  aluevarauksen pääkäyttötarkoituksen poisto antaa virheen (tarkistussääntö R-08), ja suureeseen
  sallitaan vain *ehdottomasti noudatettava* ja *käyttötarkoituskohdistus* (R-05). Korjaa
  poistamalla tai palauttamalla.
- Kirjaintunnus: jos muokattu koodiyhdistelmä vastaa liitteen 4 riviä, tunnus otetaan siltä
  riviltä (esim. *Teollisuusalue* + *ympäristö asettaa …* → TY). Muuten käytetään sen rivin
  tunnusta, josta rakenne tuli (esim. TP), ja perustelu kehottaa tarkistamaan sen.
- **Muokattua ryhmää ei lähetetä kielimallille.** Jos ryhmälle on aiempi kielimallin vastaus, se
  käytetään uudelleen ilman kustannusta ja muutokset tehdään sen päälle. Voimassa olevan
  määräyksen sanallinen teksti säilyy aina ennallaan.

### Linjausvalinnat

*1 Syöte → Linjausvalinnat*: linjaukset ovat tulkintaperiaatteita, joita avustaja noudattaa
koko muunnoksessa, esimerkiksi säilytetäänkö lähteen kirjaintunnus. Osion otsikko kertoo,
ovatko kaikki linjaukset suositellussa oletuksessa vai mitä on muutettu. Kun avaat osion,
näet jokaisesta linjauksesta selitteen, valinnan ja sen **vaikutuksen**.

- Oletuksena on suositeltu vaihtoehto (*suositus*). Muuta valintaa vain, jos tämä muunnos
  tarvitsee toisen tulkinnan. Vain muutetut valinnat kirjataan muunnokseen ja raporttiin
  käyttäjän valintoina; ne näkyvät myös kysymyskorteissa.
- **Lukittu** 🔒 linjaus on Tampereen päätös: valintaa ei voi muuttaa, ja telakka kertoo,
  kuka päätti ja milloin. Tällä hetkellä yksikään linjaus ei ole lukittu.
- Joillakin linjauksilla on tässä versiossa vain yksi käytettävissä oleva vaihtoehto; telakka
  kertoo sen.
- Linjauksen tunnus (esim. L-06) näkyy työkaluvihjeessä, kun viet hiiren linjauksen nimen päälle.

## 8 Vienti ja validointi

*3 Vienti*: valitse kansio ja tiedostonimen alku, rastita muodot ja paina **Vie**.

- **Tiedostonimen alku** ehdotetaan ehdotuksen ensimmäisen kaavamääräysryhmän otsikosta (tai
  kirjaintunnuksesta), esim. `Pientalovaltainen_asuntoalue`. Ehdotus päivittyy jokaisen
  muunnoksen jälkeen, ellet ole kirjoittanut nimeä itse.
- Vienti **ei korvaa** olemassa olevia tiedostoja: jos kansiossa on jo samannimisiä, nimeen
  lisätään juokseva numero (`…_2`, `…_3`), ja tulos kertoo sen. Valinta *Korvaa samannimiset
  tiedostot (kysytään ensin)* korvaa ne, kun vahvistat; *Ei* peruu viennin.

| Tiedosto | Sisältö |
|---|---|
| `<nimi>.kma.json` | muunnosprojekti: syöte, ehdotukset, perustelut, ratkaisut ja kielimallin vastaukset; avaa myöhemmin *Avaa aiempi muunnos* -painikkeella |
| `<nimi>_raportti.md` / `.html` | muunnosraportti kaavoittajan kielellä |
| `<nimi>.ryhti.json` | Ryhti-JSON: kaavamääräysryhmät ja yleismääräysryhmät (sama kuin *Ryhti-JSON*-välilehti) |
| `<nimi>.arho.yaml` | valinnainen Arhon kaavamääräysryhmäkirjasto (ryhmät, joissa on sääntövirheitä, jätetään pois, ellei toisin valita) |

Paikallinen Ryhti-skeematarkistus jää QGISissa tekemättä, koska `jsonschema`-paketti
puuttuu; tämä ei ole virhe (ks. T-15, jos haluat sen). **Validoi Syken testiympäristössä**
lähettää ryhmät (enintään valittu määrä) Syken julkiseen validointirajapintaan synteettisenä
testikaavana; kaavatason havainnot suodatetaan pois. Hyväksytty ryhmä näkyy muodossa *✔ …:
Ryhti hyväksyi ryhmän, ei havaintoja*. Havainto näytetään selkokielisenä, ja Ryhdin
sääntötunniste on sulkeissa. Tarvitset Syken avaimen (luku 2).

## 9 Aiemman muunnoksen jatkaminen

*1 Syöte → Avaa aiempi muunnos (*.kma.json)*: projekti avautuu ratkaisuineen,
lisätietojen muutoksineen ja linjausvalintoineen. Yhden määräyksen syöte palautuu kenttiin;
liitetty teksti liitetään uudelleen. *Muunna* tai *Aja uudelleen ratkaisuin* säilyttää
ratkaisut ja muutokset ja käyttää aiemmat kielimallivastaukset. *Uusi muunnos* tyhjentää
syötteen, ratkaisut, muutokset ja tuloksen. Version 0.3.4 projekteja ei voi avata vanhemmilla
versioilla (projektin muoto 2); vanhemmat projektit avautuvat.

Komentorivillä `kma convert … --projekti aiempi.kma.json` käyttää aiemman projektin ratkaisut ja
muutokset. Asetustiedostoon voi kirjoittaa muutokset kenttään `muokkaukset`, esim.

```yaml
muokkaukset:
  - otsikko: "TYÖPAIKKOJEN JA ELINKEINOJEN ALUE, JOLLA YMPÄRISTÖ ASETTAA TOIMINNAN LAADULLE ERITYISIÄ VAATIMUKSIA"
    lisaa: ymparistoAsettaaToiminnanLaadulleErityisiaVaatimuksia
    perustelu: vrt. liitteen 4 rivi TY
  - otsikko: "PIENTALOVALTAINEN ASUNTOALUE"
    lisaa: kayttotarkoituskohdistus
    arvo: asuinpientaloalue
    maarays: sallittuKerrosala   # oletus: päämääräys
```

(`poista: <laji>` poistaa lisätiedon; `tunnus` tunnistaa merkinnän otsikon lisäksi.)

## 10 Tunnetut rajoitukset

- Yksi määräys tai lyhyt liitetty teksti kerrallaan; koko koosteen eräkäsittely ja
  jäsennystaulukko tulevat palautteen mukaan.
- Rakenteeseen vaikutetaan ratkaisuilla, linjausvalinnoilla, kaavamääräyslajin valinnalla
  koodistosta (kun sopivaa Katja-koodia ei ole) ja lisätietojen lisäyksellä ja poistolla.
  Useamman kaavamääräyslajin valinta, otsikon, kirjaintunnuksen ja geometrian muokkaus sekä
  lisätiedot, joiden arvo on luku tai väli, puuttuvat vielä. Lisätietojen muutos koskee vain
  yhtä merkintää (ei laajuutta *kaikki samankaltaiset*).
- Laadintatilan muotoiluehdotuksia ei ole.
- Välityspalvelinta ei ole testattu (tällä työasemalla sitä ei tarvita).
- Käyttöliittymä on vain suomeksi.

## 11 Ongelmatilanteet

- *Tietopohjaa ei voitu ladata*: aja säilössä `python tools\build_knowledge.py --check`.
- *Kielimallin SDK puuttuu*: asenna luvun 1 kohta 3.
- *API-avain puuttuu*: luku 2. Pääsalasanadialogi voi jäädä QGIS-ikkunan taakse.
- *Tekstistä ei löytynyt merkintää* tai *ohitettiin rivejä*: liitetyssä tekstissä otsikon on
  oltava omalla rivillään ISOIN KIRJAIMIN (luku 4). Voit käyttää myös syötettä *Yksi määräys*.
- Virheen tarkemmat tiedot: *Näkymä → Paneelit → Lokiviestit*, välilehti *Kaavamääräysavustaja*.
