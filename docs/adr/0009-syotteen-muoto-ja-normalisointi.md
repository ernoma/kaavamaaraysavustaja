# ADR-0009 Syötteen muoto: tekstitiedosto, ohjerivit ja normalisoinnin erolista

- Tila: hyväksytty 22.11.2026 (vaihe 1)
- Lähde: toteutussuunnitelma luvut 2.4, 3.7, 6.5 (kohdat 1–3); CLAUDE.md säännöt 1, 5 ja 6

## Tausta

Ydin ei saa tuoda PDF-kirjastoja eikä PDF:ää lähetetä kielimallille. Tampereen koosteen
selite on monipalstainen: merkinnän nimi versaalilla, tunnus osin tekstinä (`c-1`, `km`,
`R(200)`), tavutus palstan vaihtuessa (`käyt -` / `tötarkoituksesta`), sivun otsikot toistuvat
palstojen välissä ja jotkin tunnukset kahdentuvat poiminnassa (`pvpv`). Käyttäjän on voitava
korjata jäsennys ilman ohjelmointia.

## Päätös

- **Ytimen syöte on UTF-8-tekstitiedosto**, jossa on selitteen rivit sellaisinaan.
  `tools/extract_pdf_text.py` poimii PDF:stä paikallisen tiedoston (`work/`, ei säilöön) ja
  lisää sivurivit. PDF-kirjasto on `pypdf` (BSD, kehitysriippuvuus). PyMuPDF:ää ei käytetä,
  koska sen AGPL-lisenssi ei ole GPL-2.0-yhteensopiva. Arkkitehtuuritesti ja ruff kieltävät
  PDF-kirjastot ytimessä.
- **Jäsennys on sääntöpohjainen** ja tuntee koosteen muodon: sivun otsikko (kokoelma,
  lähdekaavat päivämäärineen, `KARTTA n`), `Kaavamerkinnät ja -määräykset`,
  `YLEISMÄÄRÄYS`-lohkot (otsikko = alkurivit ilman pistettä), versaaliotsikot, kirjaintunnukset
  otsikon alussa tai omalla rivillään sekä väliotsikot (`MAANKÄYTTÖ` ym., luettelo
  `core/ingest.py`:ssä). Otsikko jatkuu seuraavalle riville, jos rivi päättyy välilyöntiin,
  yhdysmerkkiin tai pilkkuun.
- **Käyttäjä korjaa jäsennyksen muokkaamalla tekstitiedostoa.** Tyhjä rivi katkaisee otsikon
  ja on tekstissä kappaleraja (L-03 *kappaleittain*). Pelkkiä välilyöntejä sisältävä rivi on
  palstanvaihto, ei kappaleraja. Ohjerivit:

  | Ohje | Merkitys |
  |---|---|
  | `@sivu 3` | sivunumero (poimintatyökalu lisää) |
  | `@kartta Kartta 1 - Yhdyskuntarakenne` | kartta, jos sivun otsikko puuttuu |
  | `@lahdekaavat Nimi\|pvm; Nimi2\|pvm` | lähdekaavat, jos sivun otsikko puuttuu |
  | `@osio LIIKENNEJÄRJESTELMÄ` | väliotsikko, jota jäsennin ei tunne |
  | `@merkinta [tunnus] OTSIKKO` | rivi on merkinnän otsikko |
  | `@yleismaarays [otsikko]` | yleismääräys, otsikko annettuna tai ilman |
  | `@teksti rivi` | rivi on määräystekstiä, vaikka se on versaalilla |
  | `@geometria alue\|viiva\|piste` | seuraavan merkinnän geometriavihje |
  | `# …` | kommentti |

- **Normalisointi säilyttää alkuperäisen.** Yksikköön tallennetaan `raw_text` (rivit
  sellaisinaan), `normalized_text` ja erolista (`normalization_diff`): tavutukset, pehmeät
  tavuviivat, nollaleveät merkit, ylimääräiset välilyönnit, kahdentuneet tunnukset ja
  epäilyttävät merkkijonot. Tavutus " -" rivin lopussa poistetaan. Ilman välilyöntiä oleva
  yhdysmerkki poistetaan, paitsi jos sanan rajalla on sama vokaali (`vapaa-ajan`). Tällöin
  merkki säilytetään ja kohta merkitään vahvistettavaksi. Isossa sanassa oleva pieni l
  korjataan I:ksi (`ERITASOLllTTYMÄ`) ja merkitään vahvistettavaksi. Muut epäilyttävät
  kohdat (`MRL128`, `vapaaajan`, `..`) vain merkitään.
- **VOOKA-tilassa viedään normalisoitu teksti**, jonka käyttäjä on tarkistanut erolistasta.
  Sääntö R-19 tarkistaa, että sanallinen teksti on merkki merkiltä normalisoitu lähdeteksti ja
  että normalisointi muutti vain asettelua ja erolistan sisältömuutoksia
  (`normalization_preserves_content`).

## Seuraukset

- Jäsennin on koosteen muotoon sidottu. Uusi lähde (toinen kunta tai kaava-asiakirja) voi
  vaatia uusia tunnisteita tai ohjerivejä. Väliotsikoiden luettelo on koodissa, koska se
  kuvaa syötemuotoa eikä Katjan tai Tampereen tulkintaa. `@osio` riittää poikkeuksiin.
- Tunnistamattomat rivit ohitetaan varoituksella, joten mitään ei katoa huomaamatta.
- Koosteen Kartta 1:n PDF-poiminnassa tunnettu jäsennysvirhe on `VESIVÄYLÄ`, joka liittyy
  seuraavaan otsikkoon. Korjaus on tyhjä rivi väliin (testiaineistossa tehty).
- Käyttöliittymässä (vaihe 3) samat korjaukset tehdään jäsennystaulukossa. Taustalla on
  sama tekstimuoto.
