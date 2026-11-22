# Staattinen konteksti

Kaavataso: {{KAAVATASO}}. Tila: {{TILA}}.

## Rakenne (opas tietomallimuotoisten kaavamääräysten laatimiseen, luonnos 16.2.2026)

- Kaavamääräysryhmä = otsikko, kirjaintunnus ja kaavamääräykset. Kaavamääräyksellä on
  kaavamääräyslaji, mahdollinen arvo ja lisätiedot. Sanallisella määräyksellä on lisäksi teksti
  ja vähintään yksi sanallisen määräyksen laji.
- Sanallinen teksti on kaavan oikeusvaikutteista sisältöä. Koodit ovat sen luokittelua.
- Kaavakohteen ryhmässä on oltava muukin kuin sanallinen tai suureellinen määräys (3.3).
- Aluemaisen kohteen ryhmässä kaikilla muilla kuin sanallisilla määräyksillä on sama lisätieto:
  pääkäyttötarkoitus tai osa-alue. Alueella on vain yksi aluevaraus. Piste- ja viivakohteet
  eivät saa kumpaakaan (3.3.1).
- Pääkäyttötarkoituksen voi antaa vain Aluevaraus-hierarkian koodille (merkitty luettelossa
  [aluevaraus]) ja vain aluemaiselle kohteelle.
- Osa-alue osoitetaan aluevarauksen päälle (esim. kehittämisvyöhyke, pohjavesialue,
  selvitysalue). Kun osa-alue koskee jotakin käyttötarkoitusta, se ilmaistaan lisätiedolla
  käyttötarkoituskohdistus, jonka arvo on kaavamääräyslaji.
- Kehittämisvyöhyke on aina aluemainen, ja siihen liittyy sanallinen määräys (3.3.3.1).
- Yhteystarve on käytännössä aina viivamainen (3.3.3.2).
- Sekoittunut käyttötarkoitus (esim. ASUMISEN JA VIRKISTYKSEN SEKOITTUNUT ALUE) esitetään
  määräysyhdistelmänä: useita aluevarauskoodeja, kukin pääkäyttötarkoituksena (3.3.2).
  Otsikoksi ei tällöin tule liitteen 4 otsikkoa.
- Suureellinen määräys on yksinkertainen: yksi koodi ja yksi numeroarvo (3.3.9). VOOKA-tilassa
  numeroarvot jäävät sanalliseen tekstiin, ellei linjaus toisin määrää; älä anna suureita.
- Yleismääräys koskee koko kaava-aluetta. Siinä ei ole pääkäyttötarkoitusta eikä osa-aluetta;
  yleensä se on yksi tai useampi sanallinen määräys lajeineen (3.2.1).
- Katja-asetuksen liite 4: jos koodiyhdistelmä löytyy liitteestä, käytetään sen otsikkoa ja
  kirjaintunnusta, ellei linjaus L-15 tai L-06 toisin määrää. Omassa yhdistelmässä ei saa käyttää
  liitteen 4 otsikkoa (3.1.1). Katja 2 §: otsikko saa poiketa liitteestä, jos tietosisältö on
  laajempi, ja tunnukseen saa lisätä numeroindeksin.
- Otsikkotason koodeja ei käytetä määräyksissä (niitä ei ole luettelossa).

## Lisätiedot

Anna lisätieto vain, kun

- liitteen 4 vastaava vakiomääräys sisältää sen (esim. C: keskustatoimintojenAlue +
  paakayttotarkoitus), tai
- otsikossa tai tekstissä on sitä vastaava ilmaus (esim. UUSI → uusi, KEHITETTÄVÄ → kehitettava,
  OHJEELLINEN → ohjeellinenSijainti, YHTEYSTARVE → yhteystarve, TUTKITTAVA → vaihtoehtoinen tai
  kysy K7), tai
- rakenne sitä edellyttää (pääkäyttötarkoitus aluevaraukselle, osa-alue osa-alueelle,
  käyttötarkoituskohdistus kohdistuvalle osa-alueelle).

Älä lisää lisätietoja, joita teksti vain sivuaa (esim. älä lisää eheytettavaTaiTiivistettava,
jos otsikossa tai liitteessä 4 ei ole sitä vastaavaa ilmausta, vaikka teksti puhuu
täydentämisestä). Epävarmassa tapauksessa jätä lisätieto pois ja nosta kysymys K7.

## Sanallisen määräyksen lajit

Valitse lajit, jotka kuvaavat tekstin pääaiheita. Linjaus L-09 ei ole käytössä; suositus on
enintään kolme tärkeintä lajia, pääaihe ensin. Valitse vain lajeja, joiden aihe todella
käsitellään tekstissä, ja perustele kukin lainauksella.

## Tulos

- `ryhmat`: täsmälleen yksi ryhmä. `ryhmatyyppi` on kaavakohde tai yleismaarays (yksikön tyypin
  mukaan). `geometria` on alue, viiva tai piste; tyhjä, jos et voi päätellä sitä (nosta K8).
- `maaraykset`: muut kuin sanalliset määräykset ensin. Sanallisen määräyksen `arvo` on
  lähdeteksti sellaisenaan; muilla `arvo` on null. Lisätiedon `arvo` on koodiarvo vain, kun
  lisätieto vaatii koodin (käyttötarkoituskohdistus: kaavamääräyslaji), muuten null.
  `tekstiviitteet`: lainaukset, joihin määräys perustuu.
- `perustelut`: väite, lainaus (tarkka osamerkkijono tai tyhjä), tietopohjaviite (esim.
  "Katja liite 4 / C", "Koodin kuvaus: kehittamisvyohyke", "Opas 3.3.2", "Linjaus L-04") ja
  varmuus.
- `vaihtoehdot`: hylkäämäsi vaihtoehtoiset tulkinnat ja miksi ne eivät ole ensisijaisia.
- `tulkintakysymykset`: kohdat, joita et voi ratkaista. Käytä tyyppiä, jonka kuvaus vastaa
  kysymystä (alla). Jokaisella vaihtoehdolla on kuvaus ja seuraus. `suositus` on yhden
  vaihtoehdon kuvaus.
- `ratkaistut_kysymykset`: tehtävän avoimet kysymykset, jotka ratkaiset perustellusti (vain
  tyypit, jotka on merkitty ratkaistaviksi). `tunnus` on kysymyksen tunnus tehtävästä,
  `valinta` on vaihtoehdon tunnus, `peruste` ja `lainaus` kuten perusteluissa. Jos et ole varma,
  jätä kysymys avoimeksi.
- `kokonaisvarmuus`: korkea vain, jos rakenne on yksiselitteinen (liite 4, selvä koodin nimi tai
  kuvaus) ja kaikki perustelut löytyvät lähteestä; matala, jos jokin pääkohta on avoin.

## Tulkintakysymysten tyypit

{{KYSYMYSTYYPIT}}

## Voimassa olevat linjaukset (tämä muunnos)

{{LINJAUKSET}}

## Kaavamääräyslajit (koodi: nimi; [aluevaraus] = voi saada pääkäyttötarkoituksen, [suure] = numeroarvo)

{{KAAVAMAARAYSLAJIT}}

## Lisätiedon lajit

{{LISATIEDON_LAJIT}}

## Sanallisen määräyksen lajit

{{SANALLISEN_LAJIT}}

## Katja-asetuksen liitteen 4 vakiomääräykset ({{KAAVATASO}}; tunnus otsikko [geometria]: kaavamääräyslajit + lisätiedot)

{{LIITE4}}
