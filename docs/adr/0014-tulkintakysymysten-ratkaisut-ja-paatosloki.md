# ADR-0014 Tulkintakysymysten ratkaisut ja päätösloki muunnosprojektissa

- Tila: hyväksytty 22.11.2026 (vaihe 2)
- Lähde: toteutussuunnitelma luvut 6.4 (`decisions`), 6.10 ja 7.2; ADR-0008, ADR-0010, ADR-0012

## Tausta

Paikkatietoasiantuntija ratkaisee tulkintakysymykset muunnoskohtaisesti (ADR-0012).
Ratkaisujen on säilyttävä, kun muunnos ajetaan uudelleen (uusi tietopohja, korjattu syöte,
kielimalli), ja niiden laajuus on voitava valita: tämä merkintä tai kaikki samankaltaiset.
Käyttöliittymä tulee vaiheessa 3, joten vaiheessa 2 riittää asetustiedosto.

## Päätös

- Ratkaisut annetaan asetustiedoston kentässä `ratkaisut`:

  ```yaml
  ratkaisut:
    - kysymys: u004-K1          # tai otsikko + tunnus + tyyppi
      otsikko: TÄYDENTYVÄ KESKUSTA
      tunnus: c-1
      tyyppi: K1
      valinta: osa_alue
      laajuus: projekti          # merkinta | projekti
      perustelu: c-alueet ovat C-alueiden päällä
      ratkaisija: paikkatietoasiantuntija
  ```

  Yksikkö tunnistetaan ensisijaisesti otsikosta ja tunnuksesta (yksikkötunnus voi muuttua,
  kun syötettä korjataan). Laajuus `linjaus` ei ole sallittu: Tampereen linjaus lukitaan
  linjauskirjastossa (ADR-0008).
- **Laajuus `projekti`** koskee samankaltaisia yksiköitä: sama tunnuksen perusosa (c-1 … c-4),
  sama otsikko ilman määreitä tai sama teksti. Merkintäkohtainen ratkaisu voittaa
  projektilaajuisen.
- **Vaikutus**: K8 (geometria) ja K6 (informatiivinen vai määräys) sekä K1 (aluevaraus) muuttavat
  sääntöpohjaisen vaiheen syötettä; kaikki ratkaisut sulkevat kysymyksen
  (`resolved_by: kayttaja`) ja välitetään kielimallille ratkaistuina. Tuntematon valinta tai
  ratkaisu ilman vastaavaa yksikköä on varoitus, joka näkyy komentorivillä ja projektissa.
- **Päätösloki** tallentuu projektiin (`decisions`: kysymys, yksikkö, valinta, laajuus,
  ratkaisija, aika, perustelu, tyyppi, otsikko, tunnus). `kma convert --projekti
  vanha.kma.json` ottaa aiemman projektin ratkaisut (ja kielimallivastaukset, ADR-0013);
  asetustiedoston uudempi ratkaisu korvaa saman kysymyksen vanhan.
- `kma convert` kirjoittaa avoimista kysymyksistä pohjan `<nimi>_ratkaisut.yaml`, jonka
  rivit voi ottaa käyttöön poistamalla kommenttimerkin.

## Seuraukset

- Vaiheen 3 käyttöliittymä käyttää samaa mallia (`Decision`, `core/decisions.py`):
  tulkintakysymyskortin "Sovella kaikkiin c-2…c-4-merkintöihin" on laajuus `projekti`.
- Kaikkien kysymystyyppien rakenteellisia seurauksia ei vielä toteuteta (esim. K2:n "yksi
  pääkäyttötarkoitus" tai K9:n jako); ratkaisu sulkee kysymyksen, ja rakenne muokataan
  vaiheessa 3 käsin tai kielimalli ottaa ratkaisun huomioon.
