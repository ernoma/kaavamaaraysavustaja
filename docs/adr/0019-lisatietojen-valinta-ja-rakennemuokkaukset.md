# ADR-0019 Lisätietojen valinta käsin: rakennemuokkausten luettelo muunnosprojektissa

- Tila: hyväksytty 27.11.2026 (versio 0.3.4)
- Lähde: [`palaute_vaihe3.md`](../palaute_vaihe3.md) havainto P3-01; ADR-0014 (päätösloki),
  ADR-0017 (telakka), ADR-0018 (täydennys: kaavamääräyslaji koodistosta)

## Tausta

Versiossa 0.3.3 käyttäjä voi valita kaavamääräyslajin kansallisesta koodistosta, kun sopivaa
Katja-koodia ei löydy (K5, `koodi:<arvo>`). Lisätietoja ei voinut valita. Esimerkiksi
voimassa olevan määräyksen *Työpaikkojen ja elinkeinojen alue, jolla ympäristö asettaa
toiminnan laadulle erityisiä vaatimuksia* rakenteeksi tulee *Työpaikkojen alue* +
pääkäyttötarkoitus, mutta lisätieto *ympäristö asettaa toiminnan laadulle erityisiä vaatimuksia*
(vrt. liitteen 4 rivi 16 TY) puuttuu. Lisätiedon pitää voida lisätä myös rakenteeseen, joka tuli
liitteestä 4, koodin nimestä tai sanastosta, ja käyttäjän pitää voida poistaa lisätieto, myös
avustajan ehdottama.

Tallennusmuodolle oli kaksi vaihtoehtoa:

1. **Päätösloki uudella valintamuodolla** (esim. `Decision`, jonka tyyppi on oma ja valinta
   `lisaa:<koodi>`). Päätös on kuitenkin vastaus tulkintakysymykseen: yksi vastaus kysymystyyppiä
   ja yksikköä kohden (`merge_decisions`), ja sen vaihtoehto on kysymyksen vaihtoehto
   (`apply_answers` varoittaa muusta). Ratkaistut kysymykset lähetetään kielimallille, ja
   asetustiedoston ratkaisupohja listaa ne. Useita lisätietoja, poistoja ja kohdemääräyksiä
   olisi pitänyt koodata valintamerkkijonoon, ja kysymystyyppien K1–K15 merkitys olisi
   hämärtynyt.
2. **Erillinen käyttäjän muokkausten luettelo** muunnosprojektissa.

## Päätös

- **Rakennemuokkaukset ovat oma luettelonsa** `ConversionProject.edits` (`StructureEdit`).
  Muokkaus on `lisaa_lisatieto` tai `poista_lisatieto`. Siinä on lisätiedon laji (`info`),
  arvo, jos lisätiedon laji sitä vaatii (`value`, esim. käyttötarkoituskohdistus → kaavamääräyslaji),
  ja kohdemääräys (`regulation`; tyhjä = ryhmän päämääräys). Koodit tallennetaan URIna
  koodistoversioineen. Yksikkö tunnistetaan otsikosta ja kirjaintunnuksesta kuten päätöksissä
  (`decisions.targets`), joten muokkaus säilyy uudelleenajossa ja aiempaa muunnosta avattaessa.
  Lisäksi tallentuvat tekijä, aika ja valinnainen perustelu.
- **Muokkaus koskee vain merkintää, jolle se tehtiin.** Laajuutta *kaikki samankaltaiset* ei
  ole; tarve selviää palautteesta.
- **Päämääräys** on ryhmän ensimmäinen muu kuin sanallinen tai suureellinen määräys. Muut ei-
  sanalliset määräykset (esim. suure) voi valita kohteeksi erikseen; niihin muokkaus kohdistuu
  kaavamääräyslajin perusteella. Koska päämääräykseen kohdistuva muokkaus ei sido koodia, se
  säilyy, vaikka päämääräyksen laji vaihtuisi (esim. K5:n koodivalinta muuttuu).
- **Muokkaukset tehdään sääntöpohjaisen rakenteen päälle** ennen kirjaintunnuksen ja otsikon
  valintaa (`convert.apply_user_edits`). Jos muokattu koodiyhdistelmä vastaa liitteen 4 riviä,
  kirjaintunnus otetaan siltä riviltä. Muuten käytetään sen rivin tunnusta, josta rakenne tuli
  (esim. TP), ja perustelu kehottaa tarkistamaan tunnuksen. Toisto ei muuta mitään: jo olemassa
  olevaa lisätietoa ei lisätä toista kertaa, eikä puuttuvaa poisteta. Lisäys, jolle ei ole
  kohdemääräystä, kirjataan perusteluun (varmuus matala).
- **Perustelu** näkyy Perustelut-osassa ja raportissa: *Käyttäjä lisäsi lisätiedon ”…” (koodi)
  määräykseen ”…”* (menetelmä `kayttaja`, varmuus korkea).
- **Käyttäjän muokkaama ryhmä** saa tilan `muokattu`. Sitä ei lähetetä kielimallille
  (`hybrid.needs_model`), eikä se näy kustannusarviossa eikä lähetettävässä sisällössä. Jos
  ryhmälle on aiempi kielimallivastaus (sama sisältöavain), se käytetään uudelleen ilman kutsua
  ja muokkaukset tehdään sen päälle. Käyttäjä muokkaa siis sitä rakennetta, jonka hän näki.
  Muiden ryhmien kielimallipyyntö ei muutu.
- **Valittavat lisätiedot**: kaavatason määrityshierarkiaan kuuluvat voimassa olevat
  lisätiedon lajit ilman otsikkotason koodeja. Lisätiedon arvot ovat dataa
  (`rules_v1.yaml`, `lisatietojen_arvot`): koodiarvo valitaan koodistosta. Kaavamääräyslaji-
  arvoina tarjotaan samat koodit kuin K5:ssä (`convert.choosable_codes`). Lajit, joiden arvo on
  luku, arvoväli tai aikaväli tai jonka koodisto ei ole tietopohjassa (rakennusluvan peruste),
  eivät vielä ole valittavissa. Tarkistussääntö R-06 lukee käyttötarkoituskohdistuksen ja
  poisluettavan käyttötarkoituksen samasta datasta.
- **Sääntömoottori tarkistaa tuloksen** tavalliseen tapaan (esim. R-05 suureen lisätiedoista,
  R-06 kohdistuksen arvosta, R-07 pääkäyttötarkoituksesta ja R-08 saman pääkäyttötarkoituksen
  tai osa-alueen vaatimuksesta). Avustaja ei estä ristiriitaista muokkausta; virhe näkyy
  selkokielisenä, ja muokkauksen voi poistaa.
- Linjauksen L-05 rakenteista lisäystä ei tehdä, jos käyttäjä on poistanut saman lisätiedon.
- Asetustiedoston kenttä `muokkaukset` ja `kma convert --projekti` toimivat kuten
  `ratkaisut`.
- Projektin muoto on 2 (`format_version`); muodon 1 projektit avautuvat ennallaan.

## Seuraukset

- `core/edits.py` sisältää muokkausten logiikan (valittavat lajit ja arvot, tunnistus,
  yhdistäminen, soveltaminen ja perustelut), `core/workflow.py` telakan näkymän
  (`edit_view`, `add_info`, `remove_info`, `pending_edits`). Telakka vain kokoaa widgetit.
- Ilman muokkauksia muunnostulos ja kielimallin pyyntö ovat ennallaan, joten tietopohjan tunnus
  ei muuttunut (sääntötiedoston versio 2: lisätietojen arvot).
- Useamman kaavamääräyslajin valinta ja muut rakennemuutokset (geometria, kirjaintunnus,
  otsikko) voidaan lisätä samaan luetteloon uusina toimintoina.
