# ADR-0011 Viejät ja validointi vaiheessa 1

- Tila: hyväksytty 22.11.2026 (vaihe 1)
- Lähde: toteutussuunnitelma luvut 6.11 ja 6.12; ADR-0007; vaiheen 0 tehtävä 2

## Tausta

Vaiheen 1 tuotokset ovat muunnosprojekti (`*.kma.json`), Arhon kirjasto, Ryhti-fragmentit ja
raportti. ADR-0007:n mukaan päätuotos on Arhon kirjasto. Ryhti-JSONia tarvitaan vain
määräystason tarkistukseen. Arhon kirjastomuoto ja Ryhdin skeema muuttuvat itsenäisesti.

## Päätös

- **Arho-kirjasto** (`exporters/arho_yaml.py`) noudattaa Arhon lähdekoodin muotoa
  `format_version: 2`, joka tarkistettiin commitissa `fe456a8` (`lahtoaineistot/arho/LAHDE.md`).
  Koodiarvoinen lisätieto kirjoitetaan kuten Arhon omassa `katja_yleiskaava.yaml`issa
  (`code_value: keskustatoimintojenAlue`, muun koodiston arvo URI:na). Tyhjät arvot jätetään
  pois kuten Arhon `TemplateManager`. Pitkiä rivejä ei taiteta, jotta sanallinen teksti säilyy
  merkki merkiltä. Kategoria on `Kartta / väliotsikko`, geometria `Alue | Viiva | Piste`.
- **Kirjastoon viedään oletuksena vain ryhmät, joissa ei ole sääntövirheitä.**
  Yleismääräyksiä ja informatiivisia merkintöjä ei viedä, koska kirjastomuodossa ei ole
  yleismääräyksiä. Myöskään toisen kartan kaksoiskappaleita ei viedä. `--myos-keskeneraiset`
  vie myös virheelliset ryhmät, esimerkiksi Arhossa täydennettäviksi.
- **Ryhti-fragmentit** (`exporters/ryhti_json.py`) ovat `planRegulationGroups[]` ja
  `generalRegulationGroups[]` tietopohjan skeeman mukaan. `dataType` kirjoitetaan
  enumeraation mukaisesti (`Code`, `LocalizedText`), ei OpenAPI-kuvauksen tekstin
  mukaisesti (`"code"`). Elinkaaren tila on tarkistusta varten `kaavaelinkaari/03`. Avaimet
  ovat deterministisiä UUID5-tunnisteita projektin nimestä ja yksiköstä, joten uudelleenajo
  tuottaa samat avaimet.
- **Skeemavalidointi** (`validation/schema.py`) käyttää `jsonschema`-pakettia
  laiskasti. Paketti on kehitysriippuvuus, ja ilman sitä validointi ohitetaan ilmoituksella.
  Testit validoivat jokaisen fragmentin.
- **Syken validointi** (`validation/syke_public_api.py`, stdlib) käärii ryhmän synteettiseen
  yleiskaavaan: yksi kaavakohde ryhmää kohden geometrialla, joka vastaa ryhmän geometriaa.
  Oletuksena on testiympäristö, `planType` pelkkänä koodiarvona (`21`) ja kunta 837.
  Sääntötunnisteet normalisoidaan (`quality__req_a_b` → `quality/req-a-b`) ennen yhdistämistä
  tietopohjan viesteihin. Kaavatason säännöt (`lifecycle/…`, kaavan aluerajaus) suodatetaan
  pois, koska ne koskevat synteettistä kaavaa. `kma validate --syke` validoi oletuksena enintään viisi
  sellaisenaan hyväksyttävää ryhmää, yhden pyynnön ryhmää kohden. Verkkotestit on merkitty
  `@pytest.mark.live`, eikä CI aja niitä.
- **Raportti** (`exporters/report.py`) on Markdown ja CSV (Excel-yhteensopiva UTF-8 BOM).
  HTML on valinnainen (`--html`). Raportissa on tietopohjan, koodistojen, sääntöjen ja
  linjausten versiot, linjausvalinnat, yhteenveto sekä jokaisesta yksiköstä lähdeteksti,
  vahvistettavat normalisoinnit, rakenne kaavoittajan kielellä ja teknisesti, perustelut,
  tulkintakysymykset ja sääntötulokset Ryhdin vastaavine sääntötunnisteineen.

## Seuraukset

- Arhon latautumista ei voi testata ilman QGISia. Käsin tehtävä testiohje on
  `docs/vaihe1_raportti.md`:ssä, ja automaattinen latautumistesti Arhon mallilla on vaiheen 3 työtä.
- Jos Arhon kirjastomuoto muuttuu (`format_version` 3), viejään tehdään uusi versio ja
  LAHDE.md:hen kirjataan uusi commit.
- Syken vastausmuoto (`ruleId`, `localizedMessage.fi`) tunnetaan vaiheen 0 testistä. Jäsennin
  kerää kaikki `ruleId`-kentät rakenteesta riippumatta.
