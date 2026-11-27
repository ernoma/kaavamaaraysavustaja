# Palaute: kokeiluversio 0.3 (vaihe 3a)

Täytä tähän tehtävien T-01 ja T-02 tulokset ([`kayttajan_tehtavat.md`](kayttajan_tehtavat.md)).
Lyhyet ranskalaiset viivat riittävät. Ohje: [`kayttoohje.md`](kayttoohje.md). Älä kirjoita
tähän API-avaimia tai henkilötietoja; säilö on julkinen. Jos esimerkkitekstiä ei saa julkaista,
merkitse se, niin kehittäjä tekee siitä synteettisen vastineen.

- Kokeilija: paikkatietoasiantuntija
- Päivämäärä: 27.11.2026 (ensimmäinen palautekierros)
- QGIS-versio ja työasema: QGIS 3.44, Windows-kehityskone
- Kielimalli käytössä (ei / Claude / Mistral), kokonaiskustannus noin:

## Palautekierros 1 (27.11.2026): havainnot

Kokeiltu [`vaihe3a_raportti.md`](vaihe3a_raportti.md):n kokeiluaskelten mukaan. Kokeilija
antoi palautteen keskustelussa, ja tekoäly kirjasi sen tähän. Kokeilijan havainnot ovat
kohdissa "Havainto". Kohdat "Syy" ja "Korjaussuunta" ovat tekoälyn lisäyksiä, jotka se on
tarkistanut koodista (`plugin/dock.py`, `core/workflow.py`). Korjaukset tehtiin versioon 0.3.1
(27.11.2026), ja sarake "Tehty (0.3.1)" kertoo, mitä kunkin havainnon kohdalla tehtiin.

**Yleisarvio:** käyttöliittymä vaikuttaa kehityskelpoiselta.

| # | Kohta | Havainto | Syy (versio 0.3.0) | Korjaussuunta | Tehty (0.3.1) |
|---|---|---|---|---|---|
| P1-01 | Koko telakka | Käyttöliittymässä näkyy paljon tunnisteita ja lyhenteitä, kuten ADR-0009, L-06, K14 ja 11-3. Käyttäjä ei tiedä, mitä ne tarkoittavat, eikä hänen pitäisi joutua etsimään niitä dokumentaatiosta, joka ei välttämättä ole edes hänen saatavillaan. Jos tunnisteet ovat toteutukselle tarpeellisia, ne saavat näkyä, mutta käyttäjä on silti huomioitava. | Tunnisteita näkyy suoraan useassa kohdassa: syötevalinnassa ("ADR-0009"), linjausvalinnoissa ("L-06 …"), kysymysluettelossa ("K14 …") ja otsakkeessa (tietopohjan versio "TP-2026.11-3" ja kehoteversio "prompts/v3 v3"). | Ensisijaisesti selkokielinen teksti. Tunniste joko poistetaan tai näytetään toissijaisena, ja siihen liitetään lyhyt selitys (työkaluvihje tai sulkeissa). Esimerkiksi "Tietopohja TP-2026.11-3" voisi olla "Koodistot ja säännöt: marraskuu 2026", ja tarkempi tieto näkyisi työkaluvihjeessä. ADR-viitteitä ei näytetä käyttäjälle. | Tunnisteet selitetään. Otsakkeessa tila ja *Koodistot ja säännöt: marraskuu 2026*, tunnukset (tietopohja, kehotteen versio) työkaluvihjeessä. Linjaukset ja kysymykset näkyvät nimillään, ja tunnus on toissijainen: *linjaus Kirjaintunnukset (L-06)*, *Kirjaintunnus (tulkintakysymys K14)*, *tarkistussääntö R-19*. ADR-viitteet poistettu telakasta, Tietoja-ikkunasta ja käyttöohjeesta. Testi tarkistaa, ettei telakan teksteissä ole selittämättömiä tunnisteita (ADR-0018). |
| P1-02 | 1 Syöte: Kartta | Käyttäjälle ei selviä, miksi Kartta-kenttään kannattaisi kirjoittaa jotain. | Kenttä vain välitetään muunnokselle. Selite-syötteessä sen arvosta tulee projektin nimi ja kartan otsikko. | Kenttä selitetään (mihin arvo päätyy ja mihin sitä käytetään), tai se poistetaan tai siirretään lisäasetuksiin, jos sillä ei ole käyttäjälle merkitystä. | Selvitetty: kenttä rajasi liitetyn tekstin yhteen karttaan, kun tekstissä on useita karttoja. Kartan nimi kirjataan raporttiin ja Arho-kirjaston kuvaukseen, ja se ryhmittelee merkinnät kirjastossa. Vapaa tekstikenttä korvattu karttavalinnalla, joka näkyy vain, kun tekstissä on useita karttoja, ja jonka alla on selitys. Tekstin ainoa kartta kirjataan ilman valintaa. |
| P1-03 | 1 Syöte: Kartta | Käyttäjä ihmettelee, miksi Kartta-kenttää ei voi täyttää, kun hän syöttää uutta määräystä. | `_update_input_fields` poistaa kentän käytöstä *Yksi määräys* -syötteessä. Kenttä on käytössä vain *Liitetty selite* -syötteessä. | Käyttäytyminen yhtenäistetään (kenttä joko käytössä molemmissa tai piilotettu), tai syy kerrotaan näkyvästi. | Yksi määräys ei kuulu karttaan, joten valintaa ei näytetä; syy on liitetyn tekstin ohjeessa ja käyttöohjeessa. Liitetyssä tekstissä myös Otsikko, Kirjaintunnus ja Ryhmän tyyppi piilotetaan harmaannuttamisen sijaan, koska ne luetaan tekstistä. |
| P1-04 | 1 Syöte: Linjausvalinnat | Käyttäjälle ei selviä, miten Linjausvalinnat-laatikko vaikuttaa muunnokseen. | Laatikko on oletuksena kiinni. Kunkin rivin otsikko on muotoa "L-nn otsikko", ja selitys näkyy vain työkaluvihjeessä. | Laatikkoon lisätään lyhyt johdanto (mitä linjaus on ja milloin sitä muutetaan). Kunkin valinnan vaikutus kerrotaan selkokielellä näkyvissä, ei vain työkaluvihjeessä. Lukitulle linjaukselle kerrotaan, miksi se on lukittu. | Laatikossa johdanto (näkyy myös kiinni ollessa) ja otsikossa yhteenveto (*kaikki suositellussa oletuksessa* tai *muutettu 1: …*). Jokaisella linjauksella selite, selkokieliset vaihtoehdot ja valitun vaihtoehdon vaikutus näkyvissä; lukitulle kerrotaan, kuka päätti, milloin ja miksi. Tekstit ovat linjauskirjastossa (selite, nimi, vaikutus). Korjattu samalla kaksi vikaa: auki ollut laatikko muutti oletukset käyttäjän valinnoiksi, ja kiinni ollut laatikko esti aiemman muunnoksen linjausvalintojen palautuksen. |
| P1-05 | 1 Syöte: Liitetty selite | Jos käyttäjä valitsee *Liitetty selite*, jotta otsikkoa ja kirjaintunnusta ei tarvitse kirjoittaa erikseen vaan ne tulevat tekstin mukana, voiko silti syöttää vain yhden merkinnän? | Voi, sillä selitteen jäsennin hyväksyy myös yhden merkinnän. Valinnan teksti "(useita merkintöjä, ADR-0009)" antaa kuitenkin ymmärtää muuta. | Valinnan nimi ja ohje muotoillaan uudelleen, esimerkiksi "Liitetty teksti, jossa otsikko ja kirjaintunnus ovat mukana (yksi tai useampi merkintä)". Lyhyt esimerkki muodosta lisätään. Toimivuus varmistetaan testillä. | Valinta on nyt *Liitetty teksti: otsikko ja kirjaintunnus tekstissä (yksi tai useampi merkintä)*. Ohje ja yhden merkinnän esimerkki näkyvät valinnan alla ja tekstikentässä. Testattu yksi merkintä tunnuksen kanssa ja ilman sekä esimerkin kelpoisuus. Jos otsikkoa ei tunnisteta, virhe kertoo muodon, ja ohitetut rivit ilmoitetaan. |
| P1-06 | 2 Ehdotus: ratkaisut | Käyttäjä ihmettelee, miksi osaa tekemistään ratkaisuista ei voi muuttaa ja osaa voi. | Linjauksella ratkaistu kysymys näytetään vain luku -tilassa (`resolved_by` alkaa "linjaus…"), ja ohje on vain pienellä kursiivilla. Ratkaisu muuttuu Syöte-välilehden linjausvalinnalla. Lukittua linjausta ei voi muuttaa lainkaan. | Ero näytetään selkeästi: kuka ratkaisi kysymyksen (käyttäjä, linjaus tai lukittu linjaus) ja miten sitä voi muuttaa. Linjauksen voisi vaihtaa suoraan kysymyskortista, jolloin ratkaisu kirjataan muunnoskohtaisena valintana. Käyttäjän omat ratkaisut ovat aina muutettavissa. | Kortti kertoo ratkaisijan (sinä, kielimalli, linjaus, lukittu linjaus, muunnostila) ja muutostavan. Omat ratkaisut ovat aina muutettavissa, ja uusi painike *Poista oma ratkaisu* palauttaa kysymyksen avoimeksi. Linjauksen voi vaihtaa kortista (*Vaihda linjaus ja aja uudelleen*): vaihto kirjataan muunnoksen linjausvalinnaksi (ADR-0018). Lukittua ei voi vaihtaa. Tallennettu ratkaisu näkyy ⏳-merkillä, kunnes muunnos ajetaan uudelleen. |
| P1-07 | 2 Ehdotus: Ryhti-JSON | Viimeistään silloin, kun kaikki tulkintakysymykset on ratkaistu, käyttäjän pitäisi voida tarkastella syntyvää Ryhti-JSONia suoraan käyttöliittymässä. | Ryhti-JSON näkyy vasta viedyssä tiedostossa. *Tekninen näkymä* on HTML-tiivistelmä. | Lisätään näkymä, joka näyttää valitun yksikön Ryhti-JSONin (luettava, kopioitava). Lisäksi kerrotaan, onko kysymyksiä vielä avoinna. | *2 Ehdotus* → välilehti *Ryhti-JSON*: valitun yksikön tai koko muunnoksen JSON samalla viejällä kuin vienti, painike *Kopioi*. Yläpuolella kerrotaan avoimet kysymykset, sääntövirheet ja uudelleenajoa odottavat ratkaisut; jos yksikköä ei viedä, syy. |
| P1-08 | 3 Vienti: tiedostonimi | Tiedostonimen alun ehdotus tulee ilmeisesti Syöte-välilehden Otsikko-kentästä, vaikka siihen ei olisi syötetty mitään. Ainakaan *Liitetty selite* -syötteessä sitä ei pitäisi käyttää. Ehdotuksen pitäisi tulla Ehdotus-välilehden kaavamääräysryhmän otsikosta. | `set_project` asettaa nimen vain, jos kenttä on tyhjä. Nimi tulee projektin nimestä, joka on Otsikko-kenttä, selitteellä Kartta-kenttä tai "Telakan muunnos". Uusi muunnos ei päivitä vanhaa ehdotusta. | Ehdotus muodostetaan ehdotuksen ensimmäisen kaavamääräysryhmän otsikosta (tai kirjaintunnuksesta), ja se päivitetään jokaisen muunnoksen jälkeen, ellei käyttäjä ole muuttanut nimeä itse. | Ehdotus tulee ensimmäisen kaavamääräysryhmän otsikosta (tai kirjaintunnuksesta) ja päivittyy jokaisen muunnoksen jälkeen, ellei nimeä ole muutettu itse. |
| P1-09 | 3 Vienti: ylikirjoitus | *Vie*-painike tallentaa kansiossa jo olevien tiedostojen päälle kysymättä, saako niin tehdä vai pitäisikö nimen loppuun lisätä esimerkiksi juokseva numero. | `workflow.export` kirjoittaa tiedostot tarkistamatta, ovatko ne jo olemassa. | Ennen vientiä tarkistetaan olemassa olevat tiedostot ja kysytään: korvaa tai lisää juokseva numero (oletus). Logiikka sijoitetaan `core/workflow.py`:hin testattavaksi. | Oletuksena nimeen lisätään juokseva numero (`nimi_2`), ja tulos kertoo sen. *Korvaa samannimiset tiedostot (kysytään ensin)* on erillinen valinta. Logiikka `core/workflow.py`:ssä, testit `tests/unit/test_workflow_palaute.py`. |


## Palautekierros 2 (versio 0.3.1): kokeile korjaukset

Korjaukset on tehty versioon 0.3.1 (27.11.2026). Käynnistä QGIS uudelleen, jotta uusi koodi
latautuu (lisäosa on linkki työhakemistoon). Kirjaa tulos tähän tai kerro se keskustelussa.

| # | Kokeile | Toimiiko? (kyllä / ei / osittain) | Huomiot |
|---|---|---|---|
| P1-01 | Otsakkeessa *Koodistot ja säännöt: marraskuu 2026*; tunnisteet vain työkaluvihjeissä tai sulkeissa selityksen kanssa | | |
| P1-02, P1-03 | *Liitetty teksti* ja kaksi `@kartta`-riviä: karttavalinta ja selitys tulevat näkyviin. *Yksi määräys*: karttavalintaa ei ole | | |
| P1-04 | *Linjausvalinnat*: johdanto, yhteenveto otsikossa, selite ja vaikutus jokaiselle linjaukselle | | |
| P1-05 | *Liitetty teksti* yhdellä merkinnällä (esim. `c-1 TÄYDENTYVÄ KESKUSTA` + teksti) | | |
| P1-06 | Kysymyskortti: ratkaisija ja muutostapa; oman ratkaisun muutos ja poisto; linjauksen vaihto kortista | | |
| P1-07 | *2 Ehdotus → Ryhti-JSON*: yksikkö ja koko muunnos, *Kopioi*, avoimien kysymysten tieto | | |
| P1-08 | Tiedostonimi ryhmän otsikosta; päivittyy uuden muunnoksen jälkeen, oma nimi säilyy | | |
| P1-09 | Toinen vienti samaan kansioon: `_2`-nimet; *Korvaa samannimiset tiedostot* kysyy ensin | | |

### Palautekierros 2 (27.11.2026): havainnot

**Yleisarvio:** kokeilu versiolla 0.3.1 meni pääosin hyvin. Kohdat "Syy" ja "Tehty" ovat
tekoälyn lisäyksiä.

| # | Kohta | Havainto | Syy (versio 0.3.1) | Tehty (0.3.2) |
|---|---|---|---|---|
| P2-01 | 1 Syöte: Liitetty teksti | Kun Syöte-kohtaan valitaan *Liitetty teksti*, Kartta-valinnan yläpuolelle jää näkyviin otsikko ja teksti, mahdollisesti aiemmin samalle välilehdelle syötetyt. | Valinnan alla oleva muotoesimerkki (`c-1 TÄYDENTYVÄ KESKUSTA` ja teksti) näytti syötetyltä tiedolta. Lisäksi *Yksi määräys* -syötteeseen kirjoitettu teksti jäi tekstikenttään, vaikka se ei ole liitetyn tekstin muodossa, ja kapeassa telakassa esimerkki levensi välilehteä. | Esimerkki on katkoviivalaatikossa otsikolla "Esimerkki yhdestä merkinnästä (malli, ei syötettä)" ja rivittyy. Kummallakin syötteellä on oma tekstinsä: vaihdettaessa toisen syötteen teksti jää talteen ja palaa takaisin vaihdettaessa. Savutesti tarkistaa tämän. |
| P2-02 | 2 Ehdotus: Ryhti-kelpoisuus | Laadintaesimerkkiä (Pientalovaltainen asuntoalue, 6 000 k-m², suositellaan) ei saanut korjattua Ehdotus-välilehdellä Ryhti-validiksi: jäi epäselväksi, osasiko korjata vai eikö se ollut mahdollista. | Tulos oli jo Ryhti-kelpoinen: paikallinen skeematarkistus ei virheitä ja Syken testiympäristö OK ilman havaintoja sekä ennen että jälkeen *Määräys vai suositus* -ratkaisun (tarkistettu 27.11.2026). Jäljelle jäi vain huomio R-18 (numeroarvo sekä tekstissä että suureena), joka on tiedoksi eikä korjattavissa telakassa. Telakka ei kertonut tätä selvästi, ja viennin "skeemavalidointi ohitettu" näytti ongelmalta. | Ryhti-JSON-välilehti kertoo *Avustajan tarkistussäännöt: ei virheitä* ja huomioiden ja varoitusten määrän selityksineen sekä ohjaa Syken validointiin. Sääntötarkistus selittää, että vain virhe estää Ryhdin hyväksynnän. Vienti kertoo, ettei puuttuva paikallinen skeematarkistus ole virhe, ja Syken hyväksymä ryhmä näkyy muodossa "Ryhti hyväksyi ryhmän, ei havaintoja". |
| P2-03 | Kokeiluohjeet | Kaikkia kokeiluohjeita ei ollut helppo ymmärtää. | Edellisen raportin kokeiluaskeleet olivat englanniksi ja tiiviitä. | Kokeiluaskeleet suomeksi alla (palautekierros 3) ja käyttöohjeessa. |

### Palautekierros 3 (versio 0.3.2): kokeiluaskeleet

Käynnistä QGIS uudelleen ja avaa telakka.

1. *1 Syöte*: valitse **Syöte** *Yksi määräys*, kirjoita **Otsikko** "Pientalovaltainen
   asuntoalue" ja **Määräysteksti** kahtena kappaleena: "Alueelle saa rakentaa enintään 6 000
   k-m² pientaloja." ja tyhjän rivin jälkeen "Pihoille suositellaan hulevesien viivyttämistä."
2. Vaihda **Syöte** *Liitetty teksti*: tekstikentän pitäisi olla tyhjä, otsikkokenttiä ei
   näy, ja esimerkki on katkoviivalaatikossa. Vaihda takaisin *Yksi määräys*: teksti palaa.
3. Paina **Muunna**. *2 Ehdotus*: valitse kysymys "Määräys vai suositus?", valitse
   *Kaavasuositus*, **Tallenna ratkaisu** ja **Aja uudelleen ratkaisuin**. Yksikkö saa merkin ✔.
4. Avaa välilehti **Ryhti-JSON**: sen pitäisi sanoa *Ei avoimia tulkintakysymyksiä* ja
   *Avustajan tarkistussäännöt: ei virheitä, huomioita 1 (tiedoksi, ei korjattavaa)*. Tulos on
   tällöin Ryhti-kelpoinen; huomio koskee numeroarvoa, joka on sekä tekstissä että suureena.
5. *3 Vienti*: paina **Vie** ja halutessasi **Validoi Syken testiympäristössä** (Syken avain
   tarvitaan): tuloksen pitäisi olla "Ryhti hyväksyi ryhmän, ei havaintoja".

| Askel | Toimiko? (kyllä / ei / osittain) | Huomiot |
|---|---|---|
| 1–2 Syötteen vaihto | | |
| 3 Ratkaisu ja uudelleenajo | | |
| 4 Ryhti-JSON ja tarkistussäännöt | | |
| 5 Vienti ja Syke | | |

## T-01 Kokeilu

### A. Asennus ja käynnistys

| Kohta | Toimiko? (kyllä / ei / osittain) | Huomiot |
|---|---|---|
| Lisäosa latautui ja telakka avautui | | |
| *Tietoja*-ikkuna: tietopohja ja "claude ✓" | | |
| Avainten tallennus (*API-avaimet…*), pääsalasana | | |

### B. Uuden määräyksen muunnos (laadinta)

Ehdotus kokeiltavaksi (tai oma teksti):

> Otsikko: *Pientalovaltainen asuntoalue*
> Teksti: *Alueelle saa rakentaa enintään 6 000 k-m² pientaloja.* (tyhjä rivi)
> *Pihoille suositellaan hulevesien viivyttämistä.*

| Kohta | Toimiko? | Huomiot |
|---|---|---|
| Rakenne-ehdotus (koodit, pääkäyttötarkoitus, Katja-otsikko, kirjaintunnus) järkevä | | |
| Numeroarvo suureena (sallittu kerrosala 6000 k-m²) | | |
| K13: kappale kaavasuositukseksi *Tallenna ratkaisu* + *Aja uudelleen* | | |
| Sanallisen määräyksen lajit osuvat | | |
| Perustelut ja lainaukset ymmärrettäviä | | |
| Kielimallin kustannusarvio näkyi ennen lähetystä ja vastasi toteumaa | | |

### C. Voimassa olevan määräyksen muunnos (VOOKA)

| Kohta | Toimiko? | Huomiot |
|---|---|---|
| Yksi merkintä tai liitetty selite muuntui | | |
| Teksti siirtyi muuttumattomana | | |
| Tulkintakysymys (esim. K1 c-1-merkinnälle) ratkesi, laajuus *samankaltaiset* toimi | | |

### D. Vienti

| Kohta | Toimiko? | Huomiot |
|---|---|---|
| Muunnosprojekti, raportti, Ryhti-JSON (Arho-YAML valinnainen) | | |
| Syken testiympäristön validointi | | |
| Aiemman muunnoksen avaus ja uudelleenajo | | |

### E. Yleisarvio

- Mikä toimi hyvin:
- Mikä oli hankalaa tai epäselvää (näkymät, termit, kysymykset):
- Mitä puuttuu, jotta käyttäisit työkalua oikeassa työssä:
- Kumpi on tärkeämpi nyt: uusien vai voimassa olevien määräysten muunnos? Miksi?
- Tarvitaanko seuraavaksi (järjestä 1 = tärkein): koko koosteen eräkäsittely, rakenteen
  muokkaus koodivalitsimilla, jäsennystaulukko, muotoiluehdotukset uusiin teksteihin,
  kytkentä vektoriaineistoon (vaihe 4), muu:

## T-02 Uusien määräysten muunnostarpeet

Kuvaa 3–5 tyypillistä tilannetta. Esimerkkitekstit korvaavat tai täydentävät synteettisen
testiaineiston (`tests/golden/laadinta_odotetut.yaml`), jolla laadintatilaa nyt arvioidaan.

| # | Tilanne (kuka kirjoittaa, missä vaiheessa) | Kaavataso | Esimerkkiteksti tai kuvaus | Mitä tuloksella tehdään (Ryhti, Arho, raportti, muu) | Saako tekstin julkaista säilössä? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
