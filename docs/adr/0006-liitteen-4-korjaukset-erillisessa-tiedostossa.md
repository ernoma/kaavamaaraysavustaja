# ADR-0006 Liitteen 4 korjaukset erillisessä tiedostossa

- Tila: hyväksytty 22.11.2026
- Lähde: toteutussuunnitelma 3.3

## Päätös

- LIITE 3 -taulukkoa ei muokata. Korjaukset kirjataan solutasolla tiedostoon
  `knowledge/katja/annex4_corrections.yaml` (välilehti, rivi, sarake, alkuperäinen arvo,
  korjattu arvo, perustelu, lähde, `vahvistettava`).
- Rakentaja tarkistaa, että alkuperäinen arvo on yhä taulukossa; jos ei ole (taulukko on
  päivittynyt), rakennus pysähtyy. Kohdistamaton korjaus on myös virhe.
- Korjaus ratkaisee havainnon vain, jos korjattu arvo läpäisee saman tarkistuksen.
- Tyhjämerkit koodien ympäriltä poistetaan automaattisesti ja raportoidaan huomiona.
- Vakiomääräysluettelon rivi viittaa siihen kohdistuneisiin korjauksiin (`korjaukset`), ja
  avoimet havainnot näkyvät rivillä (`avoimet_havainnot`).
- Laaturaportti `docs/laaturaportti_liite3.md` generoidaan jokaisella rakennuksella.

## Seuraukset

- Korjaukset, joissa `vahvistettava: true`, käydään läpi linjauspalaverissa tai YM:n kanssa.
- Kun KATJA III -taulukko tulee, uusi taulukko rakennetaan omaksi tietopohjaversiokseen ja
  vanhat korjaukset joko poistuvat (korjattu lähteessä) tai pysäyttävät rakennuksen.
