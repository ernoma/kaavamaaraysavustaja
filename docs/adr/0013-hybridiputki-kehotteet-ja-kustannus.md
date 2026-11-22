# ADR-0013 Hybridiputki, kehotteet datana, kustannusarvio ja Mistral-adapteri

- Tila: hyväksytty 22.11.2026 (vaihe 2)
- Lähde: toteutussuunnitelma luvut 6.5 (kohta 5), 6.8 ja 6.9; ADR-0005; vaiheen 1 raportin luku 7

## Tausta

Vaihe 1 ratkaisee sääntöpohjaisesti liitteen 4 mukaiset ja määreelliset merkinnät. Avoimiksi
jäävät erityisesti K5 (lähin koodi), K8 (geometria), K1/K2 (rakenne) ja sanallisen määräyksen
lajit. Kielimallin on täydennettävä vain nämä, eikä se saa muuttaa voimassa olevan kaavan
tekstiä (P2, R-19). Kehotteet ovat muuttuvaa tietoa, ja kustannuksen on oltava ennakoitavissa.

## Päätös

- **Putki** (`core/hybrid.py`): sääntöpohjainen muunnos → kielimalli niille yksiköille, joiden
  varmuus ei ole korkea (informatiiviset merkinnät jäävät käyttäjälle) → sääntömoottori →
  varmuus. Saman sisällön yksiköt (kaksoiskappaleet) käsitellään yhdellä kutsulla.
  Malli saa vaiheen 1 rakenteen, perustelut, sääntötulokset, avoimet tulkintakysymykset,
  ratkaistut kohdat (linjaus tai käyttäjä) ja ajon linjausvalinnat.
- **Teksti tulee aina lähteestä.** Malli vain luokittelee sanallisen määräyksen (lajit ja L-04:n
  sallima alakoodi). Mallin palauttama teksti ei päädy ryhmään; poikkeama kirjataan
  perusteluksi. R-19 on siksi ehdoton myös hybridissä.
- **Lainausten tarkistus**: perustelun ja tekstiviitteen lainauksen on oltava yksikön otsikon
  tai tekstin osamerkkijono (välilyönnit yhdistettyinä, kirjainkoko ohitettuna). Muuten
  perustelu hylätään ("Hylätty perustelu …") ja ryhmän varmuus on matala.
- **Varmuus (luku 6.9)**: korkea vain, kun mallin rakenne on sama kuin sääntöpohjainen
  (ei-tyhjä) rakenne, malli ei itse arvioi varmuutta matalaksi, kaikki lainaukset löytyvät eikä
  ole sääntövirheitä, -varoituksia tai avoimia kysymyksiä. Ilman yhtäpitävyyttä enintään
  keskitaso. Mallin tarkistustiedot tallentuvat ryhmään (`model_check`).
- **Kysymykset**: samaa tyyppiä oleva mallin kysymys yhdistetään sääntöpohjaiseen
  (ei kaksoiskappaleita; mallin näkemys lisätään perusteeseen). Linjauksen ratkaisema tyyppi
  merkitään linjauksella ratkaistuksi. Malli saa ratkaista vain tyypit, jotka on merkitty
  `mallin_ratkaistavissa` (K2, K5, K7, K8, K12, K13); K1, K3, K4, K6, K9, K10, K11, K14 ja K15
  jäävät käyttäjälle tai linjaukselle.
- **Kehotteet v1 ovat dataa** `knowledge/prompts/v1/`: `kehote.yaml` (versio ja osat),
  `jarjestelmaohje.md`, `konteksti.md` (paikkamerkit, joihin tietopohjasta generoidaan
  koodit kuvauksineen, liite 4, K1–K15 ja linjaukset), `kysymystyypit.yaml` ja
  `esimerkit.yaml`. Esimerkit ovat synteettisiä, jotta testiaineisto ei vuoda kehotteeseen;
  hyväksytyt muunnokset (`hyvaksytyt.yaml`) tulevat mukaan samalla sanastohaulla (sanan alut,
  otsikko kahdella painolla, ei upotuksia). Esimerkit ovat tehtäväosassa, joten staattinen
  osa on sama koko ajon ajan ja välimuisti osuu. Kehoteversio tallentuu projektiin.
- **Lisätietojen linjaus** (spiken havainto `eheytettavaTaiTiivistettava`): lisätieto annetaan
  vain, kun liite 4, otsikon tai tekstin määre tai rakenne sen osoittaa; muuten K7.
- **Kustannus** (`core/llm/budget.py`, hinnat `knowledge/llm/hinnasto.yaml`): arvio ennen ajoa
  merkkimäärästä (ei SDK:ta), ajokohtainen budjettiraja (`--budjetti`, oletus 2 $). Kun seuraava
  kutsu ylittäisi rajan, loput yksiköt jäävät sääntöpohjaisiksi ja ne luetellaan.
  `--arvio` näyttää arvion kutsumatta mallia. Tokenit, kustannus, malli, kehoteversio,
  budjetti ja mallin vastaukset tallentuvat provenance-tietoihin. Prompt caching:
  Clauden staattinen konteksti `cache_control`-merkinnällä (ADR-0005).
- **Uudelleenkäyttö**: `kma convert --projekti vanha.kma.json` käyttää aiemman projektin
  saman kehoteversion vastauksia sisältöavaimella (ei kustannusta). Samaa muotoa käyttävät
  tallennetut vastaukset `tests/recorded_llm/` (`ReplayProvider`), joten CI ajaa hybridin
  ilman verkkoa ja SDK:ita. `RecordingProvider` tallentaa live-ajon (ei avaimia).
- **Mistral** (`core/llm/mistral.py`): virallinen `mistralai`-SDK (3.x, `mistralai.client.Mistral`,
  Apache-2.0: yhteensopiva GPL-2.0-or-later-lisenssin GPLv3-vaihtoehdon kanssa), tuotu
  laiskasti. `response_format` `json_schema` (strict), lämpötila 0, yksi korjauskierros, jos
  vastaus ei ole JSONia tai ei vastaa skeemaa (`jsonschema`, jos asennettu). Välimuistia ei
  oleteta. Oletusmalli `mistral-large-latest`; hinnat merkitty vahvistamattomiksi.
- **Komentorivi**: `--kielimalli ei|claude|mistral` (oletus `ei`), `--malli`, `--laatu`,
  `--budjetti`, `--arvio`, `--eteneminen`; samat asetustiedostoon (`kielimalli`, `malli`,
  `laatu`, `budjetti`).

- **Kehote v2** (`knowledge/prompts/v2/`, aktiivinen): ensimmäisessä live-ajossa (v1) malli
  nosti K7:n lähes jokaisesta valinnaisesta lisätiedosta ja K1:n, K6:n ja K8:n tapauksissa,
  jotka nimi, liite 4 tai teksti ratkaisee; sellaisenaan hyväksyttäviä oli 50 %. v2 lisää
  kysymysten kynnyksen tyypeittäin, kieltää kysymykset valinnaisista lisätiedoista (ne
  kirjataan hylättyinä vaihtoehtoina) ja rajaa lainaukset yksikön omaan tekstiin. v1 säilyy
  tietopohjassa ja sen tallenne vertailussa (`golden_v2_claude_kehote_v1.json`).

## Seuraukset

- Ilman kielimallia kaikki toimii kuten vaiheessa 1, eikä SDK:ita tarvita.
- Kehotteen muutos muuttaa kehoteversion, jolloin aiemmat vastaukset eivät enää käy
  uudelleen sellaisinaan (`--projekti` ohittaa ne), ja tallennetut testivastaukset on
  äänitettävä uudelleen.
- Kun malli on eri mieltä sääntöpohjaisen vaiheen kanssa, ehdotus on enintään keskitasoa,
  vaikka malli olisi oikeassa. Tämä on tarkoituksellista (luku 6.9); kalibrointi mitataan.
