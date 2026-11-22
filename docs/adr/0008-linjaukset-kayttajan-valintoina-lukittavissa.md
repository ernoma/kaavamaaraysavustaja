# ADR-0008 Linjaukset käyttäjän valintoina, jotka voidaan lukita

- Tila: hyväksytty 22.11.2026 (Tampere)
- Lähde: toteutussuunnitelma luvut 6.10 (tulkintakysymysten laajuus), 14 (L-01–L-14);
  vaiheen 0 tehtävä 4

## Tausta

Suunnitelmassa linjaukset L-01–L-07 oli tarkoitus päättää ensimmäisessä linjauspalaverissa,
jonka jälkeen avustaja soveltaisi niitä automaattisesti. Yleiskaavoitus ei ole vielä
linjannut niitä, eikä kaikkiin ole välttämättä yhtä oikeaa vastausta: sopiva tapa voi riippua
kaavasta ja käyttötarkoituksesta (ADR-0007).

## Päätös

- Linjaukset L-01–L-07 ovat **käyttäjän valintoja**: käyttäjä valitsee kulloinkin, miten
  toimitaan. Työkalu tarjoaa linjauksen vaihtoehdot ja suositellun oletuksen. Oletus on
  suunnitelman luvun 14 suositus ADR-0007:n mukaisesti tarkistettuna.
- Kun yleiskaavoitus päättää, että jokin linjaus tehdään aina samalla tavalla, valinta
  **lukitaan**. Lukittu valinta näkyy käyttöliittymässä, mutta sitä ei voi muuttaa. Sen
  perustelu, päivämäärä ja hyväksyjä näytetään.
- Linjaukset ja niiden tila ovat dataa organisaation linjauskirjastossa
  (`knowledge/org/tampere/linjaukset.yaml`, suunnitelman luku 6.6), ei koodissa. Lukituksen
  tekee ja purkaa pääkäyttäjä (L-11) muuttamalla kirjastoa; lukitus versioidaan kuten muutkin
  linjausmuutokset.
- Valinta tallennetaan muunnosprojektiin ja näkyy perusteluissa ja raportissa. Esimerkkejä:
  "L-03: ei pilkota (käyttäjän valinta)" ja "L-03: ei pilkota (Tampereen linjaus, lukittu
  3/2027)".

Linjauskirjaston merkinnän alustava muoto (tarkentuu vaiheessa 1):

```yaml
- tunnus: L-03
  otsikko: Sanallisen tekstin pilkkominen
  vaihtoehdot: [ei_pilkota, kappaleittain, aiheittain]
  oletus: ei_pilkota
  lukittu: false          # true = käyttäjä ei voi muuttaa
  paatos: null            # lukittaessa: perustelu, päivämäärä, hyväksyjä
  versio: 1
```

## Seuraukset

- Tehtävän 4 linjauspalaveri ei ole enää vaiheen 1 edellytys. Palaverissa voidaan lukita
  valintoja sitä mukaa kuin yksimielisyys syntyy.
- Vaiheessa 1 komentorivi ottaa valinnat asetustiedostosta tai valitsimista. Käyttöliittymä
  näyttää ne muunnoksen asetuksina (suunnitelman luku 7.3), ja lukitut valinnat ovat harmaana.
- Valintojen vaihtelu näkyy testiaineistossa. Testiyksikön odotettu tulos kirjataan yhdessä
  valintojen kanssa.
- Laajennettavissa muihin linjauksiin (L-08–L-14) ja tulkintakysymysten laajuuteen *Tampereen
  linjaus* (luku 6.10): laajuudella hyväksytty ratkaisu on käytännössä lukittu linjaus.
