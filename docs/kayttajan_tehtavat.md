# Käyttäjän tehtävät (seurattava lista)

Tämä on **ainoa seurattava lista** tehtävistä, jotka vaativat käyttäjää: paikkatietoasiantuntijaa,
kaavoittajia, omaa tunnusta tai Tampereen työasemaa. Vaiheraporteissa ja vaiheen 0 ohjeessa on
tehtävien tausta ja tarkat ohjeet; tila pidetään ajan tasalla tässä.

Käytäntö (CLAUDE.md):

- Kun vaihe tai tehtävä tuottaa käyttäjälle jäävän työn, se lisätään tähän ennen committia.
- Kun käyttäjä kertoo tehneensä tehtävän, tila päivitetään ja tulos kirjataan viitattuun paikkaan.
- Jokaisen vaiheen alussa tekoäly käy listan läpi ja ottaa mukaan tehtävät, joiden "Milloin"
  osuu kyseiseen vaiheeseen.

Tila: **avoin**, **odottaa** (edellytys puuttuu), **tehty**, **rajattu pois**.
Painotus 26.11.2026 (ADR-0016): ensin QGISissa kokeiltava käyttöliittymä, myös uusien
määräysten muuntamiseen. Kokeilun palaute ohjaa jatkokehitystä. Ensimmäinen kokeiltava versio
(0.3.0, vaihe 3a) valmistui 26.11.2026: [vaihe3a_raportti.md](vaihe3a_raportti.md). Ensimmäisen
palautekierroksen korjaukset (P1-01–P1-09) ovat versiossa 0.3.1 (27.11.2026):
[palaute_vaihe3.md](palaute_vaihe3.md).

## Nyt ja vaiheessa 3 (paikkatietoasiantuntija, ei edellytä Arhoa eikä kaavoittajia)

| # | Tehtävä | Milloin | Tila | Ohje / tulos |
|---|---|---|---|---|
| T-01 | **Kokeile QGIS-käyttöliittymää uudelleen** (versio 0.3.1, palautekierros 2). Käynnistä QGIS uudelleen, jotta uusi koodi latautuu, ja kokeile ensin palautekierroksen 1 korjaukset P1-01–P1-09 tarkistuslistan mukaan. Jatka sitten alkuperäistä kokeilua: uuden sanallisen määräyksen muunnos sekä voimassa olevan merkinnän muunnos, tulkintakysymyksen ratkaisu, vienti ja halutessasi kielimalli (Claude-avain *API-avaimet…*-dialogiin) ja Syke-validointi. Kirjaa mikä toimii, mikä puuttuu ja millaisia muunnostarpeita ja käyttötapauksia sinulla on. QGISin käynnistys ja klikkaus jäävät sinulle (tekoäly ajoi vain savutestin ja kuvakaappaukset ilman näkyvää ikkunaa). | vaihe 3, nyt (0.3.1 valmis 27.11.2026) | avoin: palautekierros 1 annettu ja korjattu 27.11.2026 (0.3.1); uusi kokeilu | tarkistuslista: [palaute_vaihe3.md](palaute_vaihe3.md) luku "Palautekierros 2"; kokeiluaskeleet: [vaihe3a_raportti.md](vaihe3a_raportti.md) luku 2 ja [kayttoohje.md](kayttoohje.md) |
| T-02 | Kuvaa 3–5 tyypillistä **uuden määräyksen** muunnostarvetta (millaisia tekstejä, kaavataso, mitä tuloksella tehdään). Riittää vapaamuotoinen kuvaus tai esimerkkitekstit. Todelliset esimerkit **korvaavat tai täydentävät** laadintatilan synteettisen testiaineiston (`tests/golden/laadinta_odotetut.yaml`, 16 yksikköä, vahvistamaton), jolla laadintatila nyt arvioidaan; merkitse, saako tekstin julkaista säilössä. | vaihe 3, ennen tai kokeilun yhteydessä | avoin | [palaute_vaihe3.md](palaute_vaihe3.md) kohta T-02 |
| T-03 | Tarkista testiaineiston epävarmat annotoinnit (`tarkistettava: true`, 23 yksikköä) ja kolme mallin löytämää lisävaihtoehtoa. | ei kiireellinen; ennen kuin automaatioastetta käytetään päätöksiin | avoin | `tests/golden/keskusta_odotetut.yaml`, `kartat2_4_odotetut.yaml`; [vaihe2_raportti.md](vaihe2_raportti.md) luku 6 |
| T-04 | Tarkista normalisoinnin vahvistettavat kohdat (tekstinpoiminta, esim. `vapaa-⏎ajan`, `MRL128`, `pvpv`). | kun koko koostetta muunnetaan | avoin | muunnosraportin kohta "Vahvistettavat normalisoinnit"; [vaihe1_raportti.md](vaihe1_raportti.md) luku 6 |
| T-05 | Tee koosteen käsikorjaukset (palstajärjestys kartalla 1a, `KAUPUNKIRAKE NTEEN`) tai vahvista, että ne tehdään käyttöliittymän jäsennystaulukossa. | kun koko koostetta muunnetaan | avoin | otosten otsakekommentit `tests/golden/keskusta_otos.txt` |
| T-06 | Hanki **Mistral-avain** (`MISTRAL_API_KEY`), jos Mistral-vertailu halutaan; tarkista Mistralin hinnat. | valinnainen | odottaa (avain) | [vaihe2_raportti.md](vaihe2_raportti.md) luku 5; `knowledge/llm/hinnasto.yaml` |
| T-07 | Valinnainen: SDK-tarkistus käyttöliittymässä. Riittää *Lisäosat → Kaavamääräysavustaja → Tietoja*: "Kielimallien SDK:t: claude ✓" (tekoäly tarkisti QGISin Pythonilla ilman ikkunaa 26.11.2026: anthropic 2.12.0 latautuu `kma_deps`-kansiosta). Kirjaa tulos T-01:n palautteeseen. | vaihe 3, T-01:n yhteydessä | avoin | [kayttoohje.md](kayttoohje.md) luku 1; [vaihe0_kayttajan_tehtavat.md](vaihe0_kayttajan_tehtavat.md) tehtävä 1, kohta E |
| T-08 | Vaihda `metadata.txt`:n sähköpostiosoite (nyt `noreply@example.invalid`). | ennen julkaisua lisäosarekisteriin | avoin | `kaavamaaraysavustaja/metadata.txt` |
| T-15 | Valinnainen: jos haluat paikallisen Ryhti-skeematarkistuksen myös QGISissa, asenna `jsonschema` `kma_deps`-kansioon (`python -m pip install --only-binary=:all: --target "%APPDATA%\QGIS\QGIS3\profiles\default\python\kma_deps" jsonschema` OSGeo4W Shellissä). Ilman sitä vienti ilmoittaa tarkistuksen ohitetuksi; Syken validointi kattaa saman. | valinnainen, vaihe 3 | avoin | [kayttoohje.md](kayttoohje.md) luku 8 |

## Vaihe 4 (kytkentä vektoriaineistoon)

| # | Tehtävä | Milloin | Tila | Ohje / tulos |
|---|---|---|---|---|
| T-09 | Toimita tai osoita voimassa olevan yleiskaavan vektoriaineisto (taso ja kenttä, jossa merkintätunnus on). Ratkaisee myös K1:n (osa-alue vai aluevaraus) päällekkäisyydellä. | vaihe 4 | odottaa (vaihe 4) | suunnitelma luku 9 |

## Vaihe 5 (kaavoittajien kanssa)

| # | Tehtävä | Milloin | Tila | Ohje / tulos |
|---|---|---|---|---|
| T-10 | Testiaineiston vahvistus (`tila: vahvistettu`) ja mittarien uusinta. | vaihe 5 | odottaa | `tests/golden/*_odotetut.yaml` |
| T-11 | Linjausten lukitus, erityisesti L-04, L-05 ja L-15 (ADR-0015). | vaihe 5 | odottaa | `knowledge/org/tampere/linjaukset.yaml`; ADR-0008, ADR-0010 |
| T-12 | Liitteen 4 korjausten vahvistus (`vahvistettava: true`). | vaihe 5 | odottaa | [vaihe0_kayttajan_tehtavat.md](vaihe0_kayttajan_tehtavat.md) tehtävä 7 |
| T-13 | Koosteen tekstin tarkistus alkuperäisiä kaava-asiakirjoja vasten. | vaihe 5 | odottaa | suunnitelma luku 3.7 |

## Vaihe 6 (Arho)

| # | Tehtävä | Milloin | Tila | Ohje / tulos |
|---|---|---|---|---|
| T-14 | Arho-kirjaston latautumistesti. | vaihe 6 | odottaa | [vaihe1_raportti.md](vaihe1_raportti.md) luku 5 |

## Tehdyt ja rajatut (vaihe 0)

Vaiheen 0 tehtävät 1–6 (SDK-asennus, Syke-avain, Claude-piikki, mittarien tavoitteet,
QgsAuthManager, VOOKA-selvitys) on tehty tai rajattu pois; tulokset
[vaihe0_kayttajan_tehtavat.md](vaihe0_kayttajan_tehtavat.md). Tehtävä 7 on nyt T-12.
