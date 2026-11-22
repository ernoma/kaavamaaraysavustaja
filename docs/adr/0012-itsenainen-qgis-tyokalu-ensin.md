# ADR-0012 Itsenäinen QGIS-työkalu ensin, Arho ja kaavoittajat myöhemmin

- Tila: hyväksytty 22.11.2026 (käyttäjän ohje)
- Lähde: käyttäjän ohje vaiheen 1 jälkeen; tarkentaa ADR-0001:tä ja ADR-0007:ää
- Korvaa: toteutussuunnitelman version 0.1 vaiheistuksen (luku 12) vaiheet 3–5

## Tausta

Suunnitelman versiossa 0.1 Arho ja kaavoittajat olivat mukana jo varhaisissa vaiheissa:
vaiheen 1 hyväksymiskriteeri oli "YAML latautuu Arhoon", vaiheen 2 testiaineiston annotoivat
kaavoittajat ja vaiheen 3 QGIS-lisäosa pilotoitiin kaavoittajien kanssa ja vietiin Arhoon.
Työkalu olisi siten ollut käyttökelpoinen vasta, kun Arho ja kaavoittajien työpanos olisivat
olleet käytettävissä.

## Päätös

- **Päävastuullinen käyttäjä on paikkatietoasiantuntija.** Hän tekee muunnokset, ratkaisee
  tulkintakysymykset muunnoskohtaisesti, kytkee kaavamääräysryhmät vektoriaineistoon ja
  validoi tuloksen.
- **Lisäosan on oltava itsessään toimiva QGISissa ilman Arhoa ja ilman kaavoittajia.**
  Syöte, muunnos (sääntöpohjainen ja kielimalli), tarkistus, kytkentä vektoriaineistoon,
  validointi (paikallinen ja Syken testiympäristö) ja vienti tehdään lisäosalla yksin.
- **Arho on tavoiteltu integraatio, ei edellytys.** Arhon kirjasto-YAML tuotetaan edelleen
  yhtenä vientimuotona, koska viejä on jo olemassa. Arhoon lataamisen testaus, Arhon
  tuontitoimintojen ohjattu käyttö ja käyttöliittymäintegraatio tehdään vasta, kun
  työkalu toimii itsenäisesti käytettävästi ja tehokkaasti (vaihe 6).
- **Kaavoittajia edellyttävät tehtävät tehdään, kun lisäosa toimii** (vaihe 5): odotettujen
  tulosten vahvistus, linjausten lukitus, pilotti kaavoittajien kanssa ja uusien määräysten
  laatiminen (laadintatila). Sitä ennen linjauksia käytetään suositelluin oletuksin ja
  muunnoskohtaisin valinnoin (ADR-0008), ja testiaineiston annotoivat kehittäjä ja
  paikkatietoasiantuntija (`tila: vahvistamaton`).
- **Ryhtiin ei toimiteta aineistoa ennen kaavoittajien validointia.** Ryhti-JSONia
  tuotetaan ja validoidaan Syken testiympäristössä jo aiemmin, mutta toimittaminen Ryhtiin
  (ADR-0007:n rajaus huomioiden) on mahdollista vasta vaiheen 5 jälkeen.

## Seuraukset

- Vaiheistus muuttuu (suunnitelma luku 12, versio 0.2): 2 kielimalli → 3 itsenäinen
  QGIS-lisäosa → 4 kytkentä vektoriaineistoon → 5 kaavoittajien validointi → 6 Arho-integraatio
  ja uudet kaavat.
- Vaiheen 1 Arho-latautumistesti (`docs/vaihe1_raportti.md` luku 5) ei ole avoin tehtävä
  nyt. Se tehdään vaiheessa 6, jolloin myös automaattinen latautumistesti Arhon mallilla
  toteutetaan (ADR-0011).
- Hyväksymiskriteerit vaiheissa 2–4 eivät saa edellyttää Arhoa eikä kaavoittajia. Mittarit
  mitataan vahvistamattomalla testiaineistolla, ja ne mitataan uudelleen vaiheessa 5.
- ADR-0007:n "pääasiallinen tuotos on Arhon kirjasto" tarkentuu: päätuotos on tarkistettu
  muunnosprojekti kaavamääräysryhmineen. Arhon kirjasto on yksi sen vientimuodoista.
- Kytkennän (vaihe 4) tuotos on QGISissa käytettävä kytketty kaavakohdetaso ja koko kaavan
  Ryhti-JSON. Arhon *Tuo kaavakohteita* ja *Tuo kaavasuunnitelma* -polut siirtyvät vaiheeseen 6.
- Riski: kaavoittajien näkemys tulee myöhään. Sitä lievitetään raportilla, joka näyttää
  rakenteen kaavoittajan kielellä, ja säilyttämällä jokaisen tulkintavalinnan
  muunnosprojektissa, jolloin vahvistus vaiheessa 5 on katselmointia eikä uudelleentyötä.
