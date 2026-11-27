# CLAUDE.md

Ohjeet tekoälyavusteiselle kehitykselle tässä säilössä. Kokonaiskuva ja vaiheistus:
[`docs/Toteutussuunnitelma_Kaavamaaraysavustaja.md`](docs/Toteutussuunnitelma_Kaavamaaraysavustaja.md).
Arkkitehtuuripäätökset: [`docs/adr/`](docs/adr/).

Kaavamääräysavustaja muuntaa sanalliset kaava- ja yleismääräykset Katja-asetuksen
(YM 311/2024) mukaisiksi kaavamääräysryhmiksi: Ryhti-JSONiksi ja valinnaisesti Arhon
kaavamääräysryhmäkirjastoksi (YAML). Käyttöliittymäteksti on suomeksi, koodi englanniksi;
alla jokaisesta termistä molemmat.

Päävastuullinen käyttäjä on paikkatietoasiantuntija. Lisäosan on toimittava QGISissa ilman
Arhoa ja ilman kaavoittajia. Arho-integraatio (vaihe 6) ja kaavoittajia edellyttävät
tehtävät (vaihe 5) tehdään vasta, kun työkalu toimii itsenäisesti (ADR-0012).

## Sanasto

**Kaavamääräysryhmä (plan regulation group)**:
Otsikon ja kirjaintunnuksen alle koottu joukko kaavamääräyksiä, joka liitetään kaavakohteisiin.
Ryhti `PlanRegulationGroup`, Arho `plan_regulation_groups[]`.
_Vältä_: merkintä (merkintä on kartan esitystapa), määräysryhmä

**Kaavamääräys (plan regulation)**:
Yksi määräys, jolla on kaavamääräyslaji, mahdollinen arvo ja lisätiedot. Ryhti `PlanRegulation`.

**Kaavamääräyslaji (regulation type)**:
Koodiston RY_Kaavamaarayslaji koodi, joka luokittelee määräyksen koneluettavasti, esim.
`keskustatoimintojenAlue`. Koodissa `type_code`, tallennetaan aina URI:na.
_Vältä_: määräystyyppi, kaavamerkintä

**Lisätiedon laji (additional information type)**:
Koodiston RY_Kaavamaarayksen_Lisatiedonlaji koodi, joka täydentää kaavamääräystä, esim.
`paakayttotarkoitus`, `osaAlue`, `kayttotarkoituskohdistus`. Osalla on arvo (esim. kohdistuksen
kaavamääräyslaji). Ryhti `AdditionalInformation`.

**Sanallisen määräyksen laji (verbal regulation type)**:
Koodiston RY_Sanallisen_Kaavamaarayksen_Laji koodi, joka luokittelee sanallisen määräyksen
aiheen (esim. `kehittamisperiaate`). Jokaisella sanallisella määräyksellä on vähintään yksi.
Ryhti `verbalRegulations`.

**Sanallinen määräys (verbal regulation)**:
Kaavamääräys, jonka laji on `sanallinenMaarays` tai sen alakoodi ja arvo kielistetty teksti.
Teksti on kaavan oikeusvaikutteista sisältöä; koodit ovat sen luokittelua.

**Yleismääräys (general regulation)**:
Koko kaava-aluetta koskeva määräys, joka ei liity yksittäiseen kaavakohteeseen.
Ryhti `GeneralRegulationGroup`. Arhon kirjastomuodossa ei ole yleismääräyksiä.
_Vältä_: yleinen määräys

**Kaavasuositus (plan recommendation)**:
Ei-velvoittava suositus; ei velvoittavia ilmauksia ("tulee", "täytyy"). Ryhti
`PlanRecommendation`, Arho `plan_propositions[]`.
_Vältä_: kaavaehdotus (kaavaehdotus on elinkaaren vaihe)

**Aluevaraus (area reservation)**:
Kaavakohde, jonka pääkäyttötarkoitus osoitetaan: lisätieto `paakayttotarkoitus` koodille, joka
kuuluu Aluevaraus-määrityshierarkiaan. Alueella on vain yksi aluevaraus.
_Vältä_: käyttötarkoitusalue

**Osa-alue (sub-area)**:
Aluevarauksen päälle osoitettava alue, jolla on lisätieto `osaAlue` (esim. kehittämisvyöhyke).

**Pääkäyttötarkoitus (main use)**:
Lisätieto `paakayttotarkoitus`; vain Aluevaraus-määrityshierarkian koodeille ja aluemaisille
kohteille.

**Suure (quantity)**:
Määräys, jolla on numeerinen arvo ja yksikkö (Suure-määrityshierarkia), esim. sallittu kerrosala.
Suureellinen määräys on yksinkertainen: yksi koodi ja yksi arvo.

**Määrityshierarkia (definition hierarchy, extension)**:
Koodiston laajennus, joka kertoo, mitkä koodit kuuluvat millekin kaavalajille tai roolille:
Aluevaraus, Yleiskaava, Asemakaava, Maakuntakaava, Suure. Jäsenyydellä voi olla
voimassaoloaika. Koodissa `extension` / `memberships`.
_Vältä_: laajennus yksinään ilman koodistoa

**Otsikkotason koodi (header-level code)**:
Koodistoa jäsentävä koodi, jota ei käytetä määräyksissä. Tunnistetaan kuvauksesta
("otsikkotason koodi"), ei hierarkiatasosta. Koodissa `header_level`.

**VOOKA-tila (VOOKA mode)**:
Voimassa olevan kaavan muunnos. Sanallinen teksti siirtyy merkki merkiltä muuttumattomana.
Tulosta käytetään uusien yleiskaavojen pohjana (esim. Arho-kirjastona). Sitä ei toimiteta Ryhtiin
VOOKA-soveltamisprofiilin mukaisena aineistona (ADR-0007), vaikka termi tulee profiilista.

**Laadintatila (drafting mode)**:
Uuden kaavan laatiminen; avustaja saa ehdottaa muotoiluja erillisinä ja valinnaisina.

**Linjaus (policy decision)**:
Versioitu tulkintakohta (esim. L-03), jolla on vaihtoehdot ja suositeltu oletus. Käyttäjä
valitsee vaihtoehdon muunnoskohtaisesti. Kun Tampere päättää linjauksesta, se **lukitaan**
(`lukittu: true`), jolloin valintaa ei voi muuttaa ja sitä sovelletaan automaattisesti
(ADR-0008). Koodissa `Decision` / `policy`.
_Vältä_: sääntö (sääntö on sääntömoottorin tarkistus)

**Tulkintakysymys (interpretation question)**:
Monitulkintainen kohta vaihtoehtoineen (tyypit K1–K15), jonka käyttäjä ratkaisee.

**Tietopaketti, tietopohja (knowledge package, knowledge base)**:
Versioitu muuttuva tieto `knowledge/`-kansiossa: koodistot, Katja-liite 4, korjaukset, säännöt,
kehotteet, Ryhti-skeema ja linjaukset. Tietopohja on niiden yhdistelmä, jolla on tunnus
(esim. TP-2026.11-3) ja manifesti tarkistussummineen.

**Vakiomääräysluettelo (standard regulation list)**:
Katja-asetuksen liite 4 koneluettavana (`knowledge/katja/annex4_*.yaml`).

## Arkkitehtuurisäännöt

1. **Ydin ilman QGISia.** `core`, `knowledge`, `exporters` ja `validation` eivät tuo `qgis`-,
   `PyQt`- tai `openpyxl`-moduulia. Vain `plugin` ja `linking` saavat tuoda QGISin.
   Tarkistaa `tests/unit/test_architecture.py`.
2. **Valinnaiset SDK:t laiskasti.** `anthropic` ja `mistralai` tuodaan vain adapterin sisällä
   (funktiossa), jotta ydin toimii ilman niitä.
3. **Muuttuva tieto on dataa.** Koodiarvoja, liitteen 4 rivejä, sääntöjen metatietoa, kehotteita
   tai skeemaa ei kovakoodata. Ne luetaan tietopohjasta. Tallenna aina koodin URI ja
   koodistoversio.
4. **Tietopohja rakennetaan työkalulla.** `knowledge/` on generoitua paitsi käsin ylläpidettävät
   `katja/annex4_corrections.yaml`, `rules/rules_v1.yaml` (sääntöjen metatieto ja lisätietojen
   arvot),
   `rules/sanasto_v1.yaml` (täsmäyksen sanasto), `org/tampere/linjaukset.yaml` (linjaukset,
   ADR-0008, ADR-0010), `org/tampere/hyvaksytyt.yaml` (hyväksytyt muunnokset),
   `prompts/v1/`–`prompts/v3/` (kehotteet, aktiivinen v3: `kehote.yaml`, `jarjestelmaohje.md`,
   `jarjestelmaohje_laadinta.md`, `konteksti.md`, `laadintaohje.md`, `kysymystyypit.yaml`,
   `esimerkit.yaml`; ADR-0013, ADR-0017; VOOKA-pyynnön on pysyttävä samana kuin v2:ssa, ellei
   tallenteita äänitetä uudelleen) ja `llm/hinnasto.yaml` (kielimallien hinnat). Muuta lähdettä tai rakentajaa ja aja `python tools/build_knowledge.py`, myös
   käsin ylläpidettävän tiedoston muutoksen jälkeen (tarkistussummat). Kehotteen muutos
   kasvattaa kehoteversiota, ja tallennetut vastaukset (`tests/recorded_llm/`) äänitetään
   uudelleen. Lähdeaineistoja (`lahtoaineistot/`) ei muokata.
5. **Kielimallille ei koskaan lähetetä PDF:iä tai kuvia**, vain käyttäjän hyväksymä
   määräysteksti ja tarvittava konteksti. Mallin koodikentät ovat enumeraatioita.
6. **VOOKA-tilassa sanallinen teksti on koskematon.**
7. **Ei salaisuuksia säilöön tai lokeihin.** API-avaimet `QgsAuthManager`iin
   (`plugin/auth.py`); kehityksessä ympäristömuuttujat `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`,
   `RYHTI_API_KEY`. Avainta ei kirjoiteta projektitiedostoon, `QgsSettings`iin, lokiin,
   testiaineistoon eikä commitiin.
8. **Pidä yksinkertaisena.** Yksi kehittäjä tekoälyavusteisesti: stdlib + PyYAML ytimessä, ei
   omaa sääntökieltä, ei taustapalvelua.
9. Lisenssi GPL-2.0-or-later. Uudet riippuvuudet GPL-yhteensopivia.
10. **Ei Arho-riippuvuutta.** Mikään toiminto tai hyväksymiskriteeri ei saa edellyttää Arhoa,
    Arhon tietokantaa tai kaavoittajien työpanosta ennen vaiheita 5–6 (ADR-0012). Arhon
    kirjasto-YAML on valinnainen vientimuoto.

## Komennot

Kehitysympäristö (Windows, PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,llm]"
```

| Tehtävä | Komento |
|---|---|
| Testit | `.\.venv\Scripts\python -m pytest` |
| Lint ja muotoilu | `.\.venv\Scripts\ruff check .` ja `.\.venv\Scripts\ruff format .` |
| Tietopohjan rakennus | `.\.venv\Scripts\python tools\build_knowledge.py` |
| Tietopohja ajan tasalla? (CI) | `.\.venv\Scripts\python tools\build_knowledge.py --check` |
| Claude-piikki (kuiva / live) | `.\.venv\Scripts\python tools\spike_claude.py [--live]` |
| Syken validointitesti | `.\.venv\Scripts\python tools\syke_validate.py` |
| PDF:n tekstinpoiminta (paikallinen, `work/`) | `.\.venv\Scripts\python tools\extract_pdf_text.py <pdf> --out work\kooste.txt` |
| Muunnos (sääntöpohjainen) | `.\.venv\Scripts\kma convert work\kooste.txt --kartta 1 [--linjaus L-03=kappaleittain] [--asetukset valinnat.yaml]` |
| Hybridimuunnos (arvio / ajo) | `.\.venv\Scripts\kma convert work\kooste.txt --kartta 1 --kielimalli claude --arvio` ja `… --budjetti 3 [--projekti aiempi.kma.json]` |
| Tarkistus (säännöt, skeema, Syke) | `.\.venv\Scripts\kma validate <projekti>.kma.json [--syke]` |
| Arviointi testiaineistolla | `.\.venv\Scripts\python tools\evaluate.py [--yksikot] [--hybridi claude] [--vertailu]` |
| Laadintatilan arviointi (uudet määräykset) | `.\.venv\Scripts\python tools\evaluate.py --laadinta [--hybridi claude] [--vertailu]` |
| Hybridin arviointi live (arvio ensin, tallentaa vastaukset) | `.\.venv\Scripts\python tools\evaluate.py --hybridi claude --live --arvio` |
| Verkkotestit (avain tarvitaan) | `.\.venv\Scripts\python -m pytest -m live` |
| QGIS-savutesti (paikallinen, ei CI) | `C:\OSGeo4W\bin\python-qgis.bat tests\qgis\qgis_smoke.py` tai `$env:KMA_QGIS_PYTHON="C:\OSGeo4W\bin\python-qgis.bat"; .\.venv\Scripts\python -m pytest -m qgis` |

CI (`.github/workflows/ci.yml`) ajaa ruffin, tietopohjan `--check`-tarkistuksen ja pytestin
ilman QGISia ja ilman verkkoa. `@pytest.mark.live`- ja `@pytest.mark.qgis`-testit eivät aja
oletuksena. Telakan logiikka on `core/workflow.py`:ssä, jotta se testataan CI:ssä; `plugin/`
vain kokoaa widgetit ja ajaa työn `QgsTask`issa (ADR-0017). Hybridin laatuportti toistaa tallennetut
vastaukset (`tests/recorded_llm/`). Paikalliset työtiedostot
(PDF-poiminnat, muunnostulokset) kuuluvat `work/`-kansioon, joka ei mene säilöön.

Ympäristöhuomio: tämän kehityskoneen Bash-työkalu kaatuu, jos komennossa on ä/ö-merkkejä.
Kirjoita Python-skriptit tiedostoihin, käytä glob-kuvioita (esim. `"LIITE 3*.xlsx"`) tai
PowerShelliä.

## Käyttäjän tehtävät

Käyttäjälle jäävät tehtävät (paikkatietoasiantuntija, kaavoittajat, avaimet, työasema) kirjataan
**aina** tiedostoon [`docs/kayttajan_tehtavat.md`](docs/kayttajan_tehtavat.md) tunnisteella
T-nn, vaiheella ja tilalla, ennen committia. Vaiheen alussa käy lista läpi; kun käyttäjä kertoo
tehneensä tehtävän, päivitä tila. Vaiheraporttiin riittää viittaus listaan.

Painotus (ADR-0016): ensin QGISissa kokeiltava käyttöliittymä, myös uusien sanallisten
määräysten muuntamiseen; käyttäjän palaute ohjaa jatkokehitystä.

## Git ja GitHub

- Tee commitit ja pushaa ne GitHubiin (`origin`, haara `main`) kysymättä erikseen varmistusta. Kysy ensin vain, jos siihen on erityisen hyvä syy, esimerkiksi:
  - muutos on vaikeasti peruttava (force push, historian uudelleenkirjoitus, haarojen tai tiedostojen poistaminen)
  - commitiin päätyisi salaisuuksia, henkilötietoja tai aineistoja, joiden julkaisuoikeus on epävarma (säilö on julkinen)
  - muutos poikkeaa siitä, mitä on pyydetty
- Commit-viestit kirjoitetaan suomeksi.
