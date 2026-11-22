# ADR-0010 Linjauskirjaston muoto ja muunnoksen valinnat

- Tila: hyväksytty 22.11.2026 (vaihe 1)
- Lähde: ADR-0007, ADR-0008; toteutussuunnitelma luvut 6.6, 6.10, 14

## Tausta

ADR-0008 päätti, että linjaukset L-01–L-07 ovat käyttäjän valintoja ja suositellulla
oletuksella, ja että ne voidaan lukita. Merkinnän muoto jätettiin tarkennettavaksi
vaiheessa 1, samoin se, miten komentorivi saa valinnat.

## Päätös

- **Linjauskirjasto** on käsin ylläpidettävä `knowledge/org/tampere/linjaukset.yaml`. Se on
  tietopohjan manifestissa tarkistussummineen (`linjaukset`). Jokaisella linjauksella on
  `tunnus`, `otsikko`, `kysymys`, `vaihtoehdot` (`arvo` ja `kuvaus`), `oletus`, `peruste`,
  `lukittu`, `paatos` (`perustelu`, `paivamaara`, `hyvaksyja`), `versio` ja
  `tulkintakysymykset` (K-tyypit, jotka linjaus ratkaisee). Rakentaja pysäyttää
  rakennuksen, jos oletus ei ole vaihtoehto tai lukitulta puuttuu päätös.
- **Oletukset** ovat luvun 14 suosituksia ADR-0007:n valossa:

  | Linjaus | Oletus | Muutos suunnitelmaan |
  |---|---|---|
  | L-01 Muunnoksen yksikkö | `kooste` | Ryhti-vientiä lähdekaavoittain ei tehdä (ADR-0007) |
  | L-02 Rakenteistamisen laajuus | `maaraystaso` | VOOKA-minimi poistettu vaihtoehdoista |
  | L-03 Tekstin pilkkominen | `ei_pilkota` | ennallaan |
  | L-04 Sanallisen määräyksen tyyppi | `sanallinenMaarays` | linjattu: yläkoodi (muistion kohta 34) |
  | L-05 Tiettyjä alueita koskevat yleismääräykset | `sailytys` | rakenteinen lisäys (MRL 72 §) on uuden kaavan oikeusvaikutuspäätös, joten se ei ole oletus; valittavissa |
  | L-06 Kirjaintunnukset | `alkuperaiset` | ennallaan |
  | L-07 Paikkasidonnaiset numeroarvot | `sanallisena` | ennallaan |

- **Valinnat muunnokselle** tulevat järjestyksessä oletus → asetustiedosto → komentorivi:

  ```powershell
  kma convert kooste.txt --kartta 1 --linjaus L-03=kappaleittain --linjaus L-06=katja
  kma convert kooste.txt --asetukset valinnat.yaml
  ```

  Asetustiedosto (`valinnat.yaml`) on YAML: `linjaukset: {L-03: kappaleittain}` sekä
  valinnaisesti `kartta`, `kaavataso`, `tila` ja `nimi`. Tuntematon kenttä, linjaus tai
  vaihtoehto on virhe.
- **Lukittua linjausta ei voi ohittaa.** Eri vaihtoehdon valinta on virhe, ja muunnos
  keskeytyy viestillä, jossa on päätöksen hyväksyjä ja päivämäärä. Sama vaihtoehto on sallittu.
- **Vaiheen 1 toteutus**: vaihtoehdot `L-02 koko_kaava`, `L-03 aiheittain`, `L-05 siirto` ja
  `L-07 omat_kohteet` ovat kirjastossa, mutta niiden valinta keskeyttää muunnoksen, koska ne
  vaativat kielimallin tai kaavakohteet (vaiheet 2 ja 4). Luettelo on koodissa
  (`core/policy.py`, `IMPLEMENTED`).
- **Tallennus ja näkyvyys**: valinnat tallentuvat muunnosprojektiin (`policy_choices`:
  tunnus, vaihtoehto, lähde `oletus | kayttaja | lukittu`, linjauksen versio, päätös).
  Linjauksen ratkaisema tulkintakysymys merkitään ratkaistuksi (`resolved_by: linjaus L-03`),
  ja perusteluissa sekä raportissa näkyy esim. "L-03: ei_pilkota (suositeltu oletus)".
- **Hyväksytyt muunnokset** (linjauskirjasto suunnitelman luvun 6.5 kohdassa 4a) ovat
  erillisessä käsin ylläpidettävässä tiedostossa `knowledge/org/tampere/hyvaksytyt.yaml`.
  Se on vaiheessa 1 tyhjä.

## Seuraukset

- Lukitus on tietopohjan muutos: uusi linjauksen versio, uusi tietopohjan versio ja
  `build_knowledge.py`. Vanhat muunnosprojektit kertovat, millä linjausversiolla ne tehtiin.
- Testiaineiston odotetut tulokset koskevat oletusvalintoja. Muut valinnat testataan
  yksikkötesteissä.
- L-08–L-14 voidaan lisätä samaan tiedostoon. Kun niitä käytetään muunnoksessa, ne lisätään
  `core/policy.py`:n tarkistuksiin.
