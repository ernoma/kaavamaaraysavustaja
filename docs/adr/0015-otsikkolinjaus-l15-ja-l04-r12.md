# ADR-0015 Otsikkolinjaus L-15 sekä L-04:n ja R-12:n suhde

- Tila: hyväksytty 22.11.2026 (vaihe 2)
- Lähde: vaiheen 1 raportin havainnot 4 ja 5; opas 3.1.1 ja 3.3.3.1; Katja 2 §; ADR-0008, ADR-0010

## Tausta

1. Opas 3.1.1: jos koodiyhdistelmä löytyy liitteestä 4, käytetään sen otsikkoa. Katja 2 §:
   otsikko saa poiketa liitteestä, jos tietosisältö on laajempi. Esimerkiksi c-1 *Täydentyvä
   keskusta* (kehittämisvyöhyke + osa-alue + kohdistus keskustatoimintoihin) vastaa liitteen 4
   otsikkoa *Keskustatoimintojen kehittämisvyöhyke*. R-15 antaa tästä huomion.
2. Opas 3.3.3.1 edellyttää kehittämisvyöhykkeelle sanallista *suunnittelumääräystä*. L-04:n
   oletus on yläkoodi *sanallinen määräys*, joten R-12 antaa kehittämisvyöhykkeistä huomion.
   Syken testirajapinta hyväksyi c-1:n yläkoodilla (vaihe 1), eli Ryhti ei tarkista tätä.

## Päätös

- Uusi linjaus **L-15 Ryhmän otsikko, kun koodiyhdistelmä vastaa liitteen 4 määräystä**:
  `lahde` (oletus) säilyttää lähteen otsikon ja kirjaa liitteen otsikon perusteluun; `katja`
  käyttää liitteen 4 otsikkoa. Oletus perustuu lähdeuskollisuuteen ja jäljitettävyyteen
  (ADR-0007): kaavoittaja tunnistaa merkinnän voimassa olevan kaavan otsikosta, ja
  sanallinen määräys laajentaa tietosisältöä. Ei lukittu; päätetään vaiheessa 5.
- **L-04 v2** saa vaihtoehdon `kehittamisvyohyke_suunnittelumaarays`: yläkoodi muuten, mutta
  kehittämisvyöhykkeen sanallinen määräys on suunnittelumääräys (opas 3.3.3.1). Oletus säilyy
  yläkoodina (muistion kohta 34, KATJA III). R-12:n alatapaus pysyy huomiona ja viittaa
  vaihtoehtoon; virheeksi sitä ei nosteta, koska Ryhti ei tarkista sitä.
- Linjauskirjaston versio on 2. Molemmat vaihtoehdot ovat käytettävissä sääntöpohjaisessa ja
  hybridimuunnoksessa (`core/policy.py`, `IMPLEMENTED`).

## Seuraukset

- R-15:n huomio näkyy edelleen oletuksella; perusteluissa kerrotaan, miksi lähteen otsikko
  säilyy (L-15). Valinnalla `--linjaus L-15=katja` huomio poistuu.
- Vaiheen 5 linjauspalaverissa päätetään L-04 ja L-15 yhdessä, koska kumpikin koskee
  oppaan luonnoksen ja asetuksen välistä tulkintaa.
