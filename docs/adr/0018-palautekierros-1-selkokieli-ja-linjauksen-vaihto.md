# ADR-0018 Palautekierros 1: selkokieli, linjauksen vaihto kortista ja vienti ilman korvaamista

- Tila: hyväksytty 27.11.2026 (versio 0.3.1)
- Lähde: [`palaute_vaihe3.md`](../palaute_vaihe3.md) havainnot P1-01–P1-09; ADR-0008, ADR-0013,
  ADR-0017

## Tausta

Paikkatietoasiantuntijan ensimmäinen kokeilu (27.11.2026) osoitti, että telakassa näkyi
selittämättömiä tunnisteita (ADR-nnnn, L-nn, K-nn, tietopohjan ja kehotteen versio), linjausten
vaikutus jäi epäselväksi, linjauksella ratkaistua kysymystä ei voinut muuttaa kortissa, Kartta-
kenttä toimi vain toisessa syötetavassa ja vienti korvasi tiedostot kysymättä. Ytimen tekstit
(perustelut, kysymysten perusteet, sääntöjen viestit) menevät osin kielimallin pyyntöön, ja
VOOKA-pyynnön on pysyttävä merkki merkiltä samana (ADR-0017), joten niitä ei voi muuttaa.

## Päätös

- **Selkokieli näyttökerroksessa.** `core/workflow.py` selittää ytimen tekstien tunnisteet
  vasta näytettäessä (`plain_text`): linjaus nimellään (*linjaus Kirjaintunnukset (L-06):
  lähteen tunnus*), tulkintakysymys tyypillään (*Kirjaintunnus (tulkintakysymys K14)*), sääntö
  sanalla *tarkistussääntö*; ADR-viitteet poistetaan ja tiedostoviitteet nimetään. Ytimen
  tallentamat tekstit ja kielimallin pyynnöt eivät muutu. Tunniste näkyy vain toissijaisena
  (sulkeissa tai työkaluvihjeessä). Otsakkeessa tietopohja on muodossa *Koodistot ja säännöt:
  marraskuu 2026*, ja tunnukset ovat työkaluvihjeessä.
- **Linjausten selkokieliset tekstit ovat dataa** linjauskirjastossa: `selite` linjaukselle
  sekä `nimi` ja `vaikutus` vaihtoehdolle. Niitä ei lähetetä kielimallille, joten niiden
  muutos ei muuta linjausta eikä kehotetta (vain tiedoston versio kasvaa). Kielimallin
  kontekstiin menevä `kuvaus` on ennallaan.
- **Vain muutetut linjausvalinnat ovat ohituksia.** Oletusarvo pysyy muunnoksessa
  suositeltuna oletuksena (`oletus`), vaikka linjausosio olisi auki.
- **Linjauksen vaihto kysymyskortista** (täydentää ADR-0017:ää): linjauksella ratkaistun
  kysymyksen kortti tarjoaa saman muunnoskohtaisen linjausvalinnan kuin Syöte-välilehti
  (`set_policy`), ja muunnos ajetaan uudelleen. Valinta kirjataan linjausvalintana
  (`PolicyChoice`, lähde `kayttaja`), ei tulkintakysymyksen ratkaisuna. Lukittua linjausta ei
  voi vaihtaa (ADR-0008); kortti kertoo, kuka päätti ja milloin. Kortti kertoo jokaisen
  kysymyksen ratkaisijan (käyttäjä, kielimalli, linjaus, lukittu linjaus, muunnostila) ja
  muutostavan (`question_view`). Käyttäjän oman ratkaisun voi aina vaihtaa tai poistaa.
- **Kartta** on liitetyn tekstin karttavalinta, joka näytetään vain, kun tekstissä on useita
  karttoja. Yksi määräys ei kuulu karttaan. Tekstin ainoa kartta kirjataan muunnokseen ilman
  valintaa.
- **Ryhti-JSON-näkymä** muodostetaan samalla viejällä kuin vienti (`ryhti_text`).
- **Vienti ei korvaa tiedostoja oletuksena**: valittujen muotojen tiedostojen ollessa jo
  olemassa nimeen lisätään juokseva numero (`free_stem`). Korvaaminen on erillinen valinta,
  ja telakka kysyy vahvistuksen. Tiedostonimen ehdotus tulee ensimmäisen kaavamääräysryhmän
  otsikosta tai kirjaintunnuksesta ja päivittyy, ellei käyttäjä ole muuttanut nimeä.

## Seuraukset

- Uudet ytimen tekstimuodot (esim. uusi tunnistetyyppi) on lisättävä `plain_text`iin; testi
  `tests/unit/test_workflow_palaute.py` tarkistaa, ettei telakan teksteissä ole selittämättömiä
  tunnisteita.
- `workflow.export` palauttaa `ExportResult`in (polut, käytetty nimi, korvatut tiedostot).
- Tietopohjan tunnus (TP-2026.11-3) ei muuttunut, koska muunnostulokset eivät muutu;
  linjauskirjaston tiedostoversio on 3.
