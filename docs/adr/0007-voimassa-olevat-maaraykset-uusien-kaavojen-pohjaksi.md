# ADR-0007 Voimassa olevat määräykset uusien kaavojen pohjaksi, ei VOOKA-toimitusta Ryhtiin

- Tila: hyväksytty 22.11.2026 (Tampere)
- Lähde: toteutussuunnitelma luvut 2, 14 (L-02, L-12); vaiheen 0 tehtävä 6

## Tausta

Suunnitelmassa oletettiin, että voimassa olevien yleiskaavojen määräykset voitaisiin viedä
Ryhtiin VOOKA-soveltamisprofiilin mukaisina
([VOOKA-profiili](https://iri.suomi.fi/model/vooka/)). Siksi vaiheeseen 0 kuului VOOKA-profiilin
vaatimusten ja `digitalOrigin`-koodien selvitys (L-02, L-12).

## Päätös

- Voimassa olevien kaavojen kaavakohteita ja kaavamääräyksiä **ei toimiteta rakenteisesti
  Ryhtiin VOOKA-aineistona**, ainakaan aluksi. VOOKA-profiilin vaatimuksia ja
  `digitalOrigin`-koodeja ei selvitetä nyt.
- Voimassa olevien yleiskaavojen sanalliset määräykset muunnetaan rakenteisiksi
  kaavamääräysryhmiksi **uusien yleiskaavojen valmistelun pohjaksi**. Pääasiallinen tuotos on
  Arhon kaavamääräysryhmäkirjasto (tarkennettu ADR-0012:lla: päätuotos on tarkistettu
  muunnosprojekti, ja Arhon kirjasto on yksi sen vientimuodoista). Ryhti-JSON tuotetaan määräystason tarkistusta varten
  (Syken validointirajapinta tavallisella profiililla, jolla uudet kaavat validoidaan).

## Seuraukset

- Tehtävä 6 (VOOKA ja digitalOrigin) poistuu vaiheesta 0. L-12 (digitaalinen alkuperä) ei
  koske avustajaa. L-02:n vaihtoehto "VOOKA-minimi" ei ole enää ajankohtainen; rakenteistaminen
  tehdään määräysryhmätasolla.
- Lähdeuskollinen muunnos säilyy: voimassa olevan kaavan sanallinen teksti siirretään
  kirjastoon merkki merkiltä (P2, R-19), koska se on hyväksytyn kaavan sisältöä. Uutta kaavaa
  laadittaessa kaavoittaja muokkaa tekstiä itse, ja avustajan muotoiluehdotukset ovat
  erillisiä (laadintatila). Termi *VOOKA-tila* tarkoittaa jatkossa tätä lähdeuskollista
  muunnosta, ei Ryhti-toimitusta. Nimeä voidaan tarkentaa vaiheessa 1 (esim. "lähdetila").
- Suunnitelman VOOKA-suositukset (L-03–L-07, K3, K4, K10, K14) arvioidaan uudelleen siitä
  näkökulmasta, mikä toimii parhaiten uuden kaavan pohjana. Esimerkiksi paikkasidonnainen
  numeroarvo (L-07, K4) voi olla kirjastossa sanallisena, koska uuden kaavan kohteet
  piirretään erikseen.
- Ryhti-validoinnin tulkinta: Syken rajapinnan virheet kertovat, kelpaako ryhmä uuteen
  yleiskaavaan. Kaavatason pakollisia tietoja (elinkaari, rajaus) täytetään testiä varten
  synteettisinä.
