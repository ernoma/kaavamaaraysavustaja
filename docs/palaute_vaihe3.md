# Palaute: kokeiluversio 0.3 (vaihe 3a)

Täytä tähän tehtävien T-01 ja T-02 tulokset ([`kayttajan_tehtavat.md`](kayttajan_tehtavat.md)).
Lyhyet ranskalaiset viivat riittävät. Ohje: [`kayttoohje.md`](kayttoohje.md). Älä kirjoita
tähän API-avaimia tai henkilötietoja; säilö on julkinen. Jos esimerkkitekstiä ei saa julkaista,
merkitse se, niin kehittäjä tekee siitä synteettisen vastineen.

- Kokeilija: paikkatietoasiantuntija
- Päivämäärä:
- QGIS-versio ja työasema:
- Kielimalli käytössä (ei / Claude / Mistral), kokonaiskustannus noin:

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
