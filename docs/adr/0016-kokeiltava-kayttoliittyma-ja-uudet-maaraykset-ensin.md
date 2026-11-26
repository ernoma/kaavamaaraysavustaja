# ADR-0016 Kokeiltava käyttöliittymä ja uusien määräysten muunnos ensin

- Tila: hyväksytty 26.11.2026 (käyttäjän ohje vaiheen 2 jälkeen)
- Lähde: käyttäjän ohje 26.11.2026; tarkentaa ADR-0012:ta ja suunnitelman lukua 12
- Korvaa: suunnitelman version 0.2 vaiheen 3 sisällön painotuksen ja UC2:n ajoituksen (vaihe 6)

## Tausta

Vaiheessa 2 hybridimuunnos saavutti testiaineistolla tavoitteet (79 % sellaisenaan). Jäljellä
olevat voimassa olevien määräysten parannukset (annotointien tarkistus, koosteen
käsikorjaukset, Mistral-vertailu) eivät ole kiireellisiä. Käyttäjä haluaa ensin QGISissa
kokeiltavan käyttöliittymän, jonka perusteella hän antaa näkemyksiä jatkokehitykseen.

Työkalua on tarkoitus käyttää myös **täysin uusien sanallisten määräysten** muuntamiseen.
Se voi olla suurempi tarve kuin voimassa olevien määräysten muuntaminen. Suunnitelmassa uusien
määräysten tuki (UC2, laadintatila) oli vaiheessa 6 kaavoittajien työkaluna Arhon rinnalla.

## Päätös

- **Vaiheen 3 ensimmäinen tavoite on kokeiltava QGIS-käyttöliittymä**, ei koko koosteen
  täydellinen muunnos. Paikkatietoasiantuntija kokeilee sitä mahdollisimman aikaisin ja
  antaa palautetta (`docs/kayttajan_tehtavat.md` T-01, T-02).
- **Uuden määräyksen muunnos (laadintatila) tulee vaiheeseen 3 perustasolla**: käyttäjä
  kirjoittaa tai liittää otsikon ja tekstin, ja avustaja ehdottaa rakenteen (koodit,
  lisätiedot, sanallisen määräyksen lajit), Katja-otsikon ja kirjaintunnuksen
  perusteluineen ja tulkintakysymyksineen. Vienti on sama kuin voimassa oleville
  (Ryhti-JSON, raportti, valinnaisesti Arho-YAML). Ei edellytä Arhoa eikä kaavoittajia;
  kokeilijana on paikkatietoasiantuntija. Muotoiluehdotukset tekstiin ovat erillisiä ja
  valinnaisia (laadintatila, periaate P2), eikä niitä tarvita ensimmäiseen versioon.
- **Ensimmäinen kokeiltava versio pidetään pienenä**: telakka, syöte (tekstikenttä), tila
  (voimassa oleva / uusi määräys), muunnos taustatehtävänä (sääntöpohjainen ja valinnaisesti
  kielimalli kustannusarvioineen), ehdotuksen tarkastelu (rakenne kaavoittajan kielellä,
  perustelut, kysymykset) ja vienti. Tarkistusnäkymän muokkaus, jäsennystaulukko ja
  koko koosteen eräkäsittely tulevat palautteen mukaan.
- Voimassa olevien määräysten jatkoparannukset (T-03–T-06) ja vaiheet 4–6 pysyvät
  ennallaan, mutta niiden järjestys ja laajuus tarkistetaan kokeilun palautteen perusteella.

## Seuraukset

- Suunnitelman luvut 12 ja 15 päivitetään (versio 0.3).
- Laadintatila tarvitsee kehotteeseen oman ohjeosan (ei VOOKA-sääntöjä, numeroarvot
  suureiksi, kaavasuositukset tunnistetaan, K13), testitapauksia uusista määräyksistä ja
  arvioinnin; aineistoksi käyttäjän kuvaamat tarpeet (T-02) ja synteettiset esimerkit.
- Ryhtiin ei edelleenkään toimiteta mitään ennen vaihetta 5 (ADR-0012).
