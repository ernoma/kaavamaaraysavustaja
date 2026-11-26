# Vaihe 0: käyttäjän tehtävät

> Kaikkien vaiheiden avoimet käyttäjän tehtävät seurataan tiedostossa
> [kayttajan_tehtavat.md](kayttajan_tehtavat.md). Tämä tiedosto säilyttää vaiheen 0 ohjeet ja tulokset.

Nämä vaiheen 0 tehtävät vaativat Tampereen työaseman, omat tunnukset tai kaavoittajien
päätöksiä, joten niitä ei voi tehdä säilössä automaattisesti. Valmiit skriptit ja pohjat on
tehty. Kirjaa tulokset kunkin tehtävän *Tulokset*-kohtaan tai ADR:ään ja pyydä sitten
tekoälyä jatkamaan.

| # | Tehtävä | Kesto | Tulos kirjataan | Tila 22.11.2026 |
|---|---|---|---|---|
| 1 | SDK-asennustesti Tampereen QGIS-työasemalla | 1–2 h | ADR-0002 | tehty; päätös C, välityspalvelinta ei testata |
| 2 | Syken kehittäjäportaali ja validointirajapinnan testi | 1 h | tämä tiedosto | tehty |
| 3 | Claude-piikin live-ajo | 15 min | ADR-0005 | tehty |
| 4 | Ensimmäinen linjauspalaveri (L-01–L-07, mittarit) | 2 h + valmistelu | `docs/linjaukset.md` (vaihe 1) | mittarit: alustavat tavoitteet käyttöön; L-01–L-07 käyttäjän valintoja, lukittavissa (ADR-0008) |
| 5 | QgsAuthManager-avainten ja lisäosan latauksen testi | 30 min | ADR-0004 | tehty |
| 6 | VOOKA-soveltamisprofiilin ja digitalOrigin-koodien selvitys | 2–4 h | tämä tiedosto, L-02 ja L-12 | rajattu pois (ADR-0007) |
| 7 | Liitteen 4 korjausten vahvistus | 30 min | `knowledge/katja/annex4_corrections.yaml` | siirretty myöhemmäksi |

Muista: säilö on julkinen. API-avaimia, välityspalvelimen tunnuksia tai Tampereen sisäisiä
osoitteita ei kirjoiteta tähän tiedostoon eikä mihinkään säilön tiedostoon.

---

## 1 SDK-asennustesti Tampereen QGIS-työasemalla (OSGeo4W, välityspalvelin)

Tavoite: selvittää, miten `anthropic`- ja `mistralai`-SDK:t saadaan QGISin Pythoniin, ja
toimiiko niiden HTTP-liikenne välityspalvelimen läpi (ADR-0002).

**Valmistelu:** kopioi säilö työasemalle (esim. `git clone https://github.com/ernoma/kaavamaaraysavustaja`
tai zip GitHubista) ja selvitä välityspalvelimen osoite (esim. selaimen tai QGISin asetuksista:
*Asetukset → Valinnat → Verkko*).

**A. Avaa OSGeo4W Shell** (Käynnistä-valikko → QGIS → OSGeo4W Shell). Aja:

```bat
python --version
python -c "import sys; print(sys.executable)"
python -m pip --version
```

**B. Asennus käyttäjän kansioon (vaihtoehto A).** Korvaa `http://proxy.example:8080`
oikealla osoitteella; jos välityspalvelin vaatii tunnuksen, älä kirjoita salasanaa
komentoon vaan käytä ympäristömuuttujaa tai organisaation ohjetta.

```bat
set HTTPS_PROXY=http://proxy.example:8080
set HTTP_PROXY=http://proxy.example:8080
python -m pip install --user --proxy %HTTPS_PROXY% "anthropic>=2.12" "mistralai>=1.0"
```

**C. Asennus lisäosan omaan kansioon (vaihtoehto C, ei admin-oikeuksia):**

```bat
python -m pip install --target "%APPDATA%\QGIS\QGIS3\profiles\default\python\kma_deps" --proxy %HTTPS_PROXY% "anthropic>=2.12" "mistralai>=1.0"
```

**D. Tarkistus komentoriviltä** (säilön juuresta):

```bat
python tools\check_sdk_env.py
```

**E. Tarkistus QGISin Python-konsolissa** (*Lisäosat → Python-konsoli*). Jos käytit
vaihtoehtoa C, lisää kansio ensin polkuun:

```python
import sys, os

sys.path.insert(0, os.path.expandvars(r"%APPDATA%\QGIS\QGIS3\profiles\default\python\kma_deps"))
exec(open(r"C:\polku\kaavamaaraysavustaja\tools\check_sdk_env.py", encoding="utf-8").read())
```

Skripti ei lähetä avaimia eikä sisältöä: se tekee yhden tunnistautumattoman HTTPS-pyynnön
kuhunkin palveluun ja odottaa vastausta 401/404 (= palvelu tavoitettavissa).

**Kirjaa (ADR-0002, kohta "Ratkaisua varten tarvittava tieto"):**

| Kohta | Tulos (22.11.2026, tekoälyn ajama) |
|---|---|
| QGIS-versio ja Python-versio | QGIS 3.44.7-Solothurn, Python 3.12.12 (OSGeo4W), pip 24.0 |
| Onnistuiko `pip install --user` (B)? Virheilmoitus, jos ei | `--dry-run` onnistui; ei asennettu, koska käyttäjäkansiossa on jo muiden työkalujen paketteja |
| Onnistuiko `--target` (C)? | kyllä: `anthropic` 2.12.0, `mistralai` 3.8.0 → `%APPDATA%\QGIS\QGIS3\profiles\default\python\kma_deps` |
| Asentuivatko käännetyt paketit (`pydantic_core`, `jiter`) ilman kääntäjää? | kyllä, valmiit wheelit (`--only-binary=:all:`) |
| Ristiriidat QGISin mukana tulevien pakettien kanssa (pip-varoitukset) | ei pip-varoituksia; päällekkäisiä `python-dateutil` ja `idna` → kansio `sys.path`in loppuun (ADR-0002) |
| Yhteydet komentoriviltä: Claude / Mistral / Syke (HTTP-koodi tai virhe) | 401 / 401 / 401 (testiympäristö) |
| Yhteydet QGIS-konsolista ilman `HTTPS_PROXY`-muuttujaa | testattu QGIS-prosessissa ilman käyttöliittymää (`python-qgis`): toimii |
| `anthropic-SDK: yhteys toimii` -rivi QGIS-konsolissa? | kyllä (QGIS-prosessi ilman käyttöliittymää) |
| Tarvittiinko varmenteiden asetuksia (`SSL_CERT_FILE`, organisaation juurivarmenne)? | ei (OSGeo4W asettaa `SSL_CERT_FILE`:n itse) |
| Suositus: A, C vai E (Qt-verkko ilman SDK:ta) | C; välityspalvelimen takana olevaa työasemaa ei testattu |

Jäljellä (valinnainen, 5 min): sama tarkistus QGISin *Python-konsolissa* käyttöliittymän kanssa
yllä olevalla E-kohdan komennolla; vaihda `sys.path.insert(0, …)` muotoon `sys.path.append(…)`
ja polku säilön polkuun `F:\tyo\Arho_ja_tekoaly\kaavamaaraysavustaja\tools\check_sdk_env.py`.

---

## 2 Syken kehittäjäportaali ja julkisen validointirajapinnan testi

1. Rekisteröidy testiportaaliin **https://api-test-developer.ymparisto.fi/** (tuotanto:
   https://api-developer.ymparisto.fi/). Käytä työsähköpostia.
2. Tilaa (*Subscribe*) tuote, johon **Ryhti Plan Public Validate API** kuuluu, ja kopioi
   tilausavain (*Primary key*) profiilisivulta.
3. Tarkista portaalin rajapintakuvauksesta testiympäristön osoite. Säilön kuvaus
   (`lahtoaineistot/ryhti-openapi/ryhti-plan-public-validate-api.json`) osoittaa tuotantoon
   `https://api.ymparisto.fi/ryhti/plan-public`. Jos testiavaimella on eri osoite, anna se
   skriptille `--url`-valitsimella.
4. Testiympäristön osoite on `https://api-test.ymparisto.fi/ryhti/plan-public` (tarkistettu
   22.11.2026: vastaa ilman avainta 401). Skripti käyttää sitä oletuksena; tuotantoon `--env prod`.
5. **Tallenna avain** Windowsin käyttäjäkohtaiseen ympäristömuuttujaan `RYHTI_API_KEY` (samoin kuin
   `ANTHROPIC_API_KEY` on tallennettu). Aja PowerShellissä; avain kysytään piilotettuna eikä se
   jää komentohistoriaan:

```powershell
[Environment]::SetEnvironmentVariable("RYHTI_API_KEY", [Net.NetworkCredential]::new("", (Read-Host "Ryhti API -avain" -AsSecureString)).Password, "User")
```

   Muuttuja näkyy uusissa ohjelmissa; `syke_validate.py` lukee sen myös suoraan rekisteristä,
   joten jo avoinna oleva päätteen tai Clauden istunto riittää. QGIS-lisäosassa avain tallennetaan
   myöhemmin QgsAuthManageriin (ADR-0004); ympäristömuuttuja on kehityskäyttöä varten.
   Poisto tarvittaessa: `[Environment]::SetEnvironmentVariable("RYHTI_API_KEY", $null, "User")`.
6. Aja säilön juuresta (tai pyydä tekoälyä ajamaan):

```powershell
.\.venv\Scripts\python tools\syke_validate.py --dry-run
```

```powershell
.\.venv\Scripts\python tools\syke_validate.py --out syke_vastaus.json
```

Skripti lähettää synteettisen yleiskaavan (yksi C-aluevaraus Tampereen alueella, kunta 837,
kaavalaji 21). **HTTP 200 tai 422 tarkoittaa, että avain ja yhteys toimivat**; 422:n
virheluettelo on juuri se, mitä halutaan nähdä (mitkä säännöt laukeavat ja millä viesteillä).
401/403 = avain tai tilaus ei kelpaa. Älä committaa `syke_vastaus.json`-tiedostoa, jos siinä on
tunnisteita; muuten se on hyödyllinen vaiheen 1 testiaineistoksi (`tests/data/`).

Kaavalaji- ja elinkaarikoodit (`--plan-type 21`, `kaavaelinkaari/code/03`,
`RY_MaanalaisuudenLaji/code/01`) ovat oletuksia: tarkista ne vastauksen virheistä.

**Tulokset:**

| Kohta | Tulos |
|---|---|
| Portaali ja tuote, jonka tilasit | testiportaali (api-test-developer.ymparisto.fi), tilausavain haettu |
| Testiympäristön osoite | `https://api-test.ymparisto.fi/ryhti/plan-public` + `/api/Plan/Validate` |
| HTTP-koodi | **200** (synteettinen testikaava läpäisi validoinnin, vastausrunko tyhjä) |
| Laukeavat säännöt (sääntötunnisteet) | perustapauksessa ei yhtään; tahallisesti virheelliset muunnelmat alla |
| Huomioita (esim. puuttuvat pakolliset kentät) | `planType` annetaan pelkkänä koodiarvona (`21`); URI → 422 `quality__req_invalid_query_param`, `2` (otsikkotaso) → HTTP 500. Skripti korjattu. |

Tahallisesti virheelliset muunnelmat (testiympäristö 22.11.2026, kaavalaji 21, kunta 837):

| Muunnelma | HTTP | Sääntö |
|---|---|---|
| Tuntematon kaavamääräyslaji (`eiOlemassa`) | 400 | `quality__req_json_deserialization_failure` (enumeraatio `EPlanRegulationType`) |
| Poistunut koodi `muuArkeologinenKohde` + `paakayttotarkoitus` | 422 | vain `quality__req_codelist_additionalinfotype_mainuseclass_areareservation`; poistunutta koodia ei tunnistettu poistuneeksi |
| Ei `paakayttotarkoitus`-lisätietoa | 422 | `quality__req_geom_areaobject_additionalinfo_mainuseclass_section_area_mandatory` |
| Asemakaavan koodi `asuinpientaloalue` yleiskaavassa | **200** | ei mitään: kaavalajin määrityshierarkiaa ei tarkisteta |
| `sanallinenMaarays` ilman `verbalRegulations`-koodia | 422 | `quality__req_codelist_spatialplanregulation_verbal_regulation_codevalue` (+ pääkäyttötarkoitus puuttuu) |
| Kirjaintunnus puuttuu | 422 | `quality__req_planregulationgroup_letteridentifier_not_null` |
| Sama yleiskaava kaavalajilla 31 (asemakaava) | **200** | ei mitään |

Johtopäätökset vaiheeseen 1:

- Rajapinta tarkistaa enumeraation, aluevarauslaajennuksen, pakolliset lisätiedot,
  sanallisen määräyksen lajin ja kirjaintunnuksen.
- Se ei tarkista poistuneita koodeja eikä kaavalajin määrityshierarkiaa. Avustajan omat
  säännöt R-01 (voimassaolo) ja määrityshierarkiatarkistus ovat siis tarpeen.
- Syken säännöt eivät myöskään estä laajennuksen ulkopuolista koodia, joten se kannattaa
  sallia varoituksella eikä estää.
- Vastauksissa on `ruleId` ja suomenkielinen `localizedMessage.fi`. Rajapinnan `ruleId` on eri
  muodossa kuin tietopohjan `ryhti/validation_messages.csv`:n tunniste:
  `quality__req_planregulationgroup_letteridentifier_not_null` vastaa CSV:n tunnistetta
  `quality/req-planregulationgroup-letteridentifier-not-null` (`__` → `/`, `_` → `-`).
  Vaiheessa 1 tunnisteet normalisoidaan ennen yhdistämistä.

---

## 3 Claude-piikin live-ajo

**Tehty 22.11.2026** Tampereen työasemalla (avain käyttäjän ympäristömuuttujasta
`ANTHROPIC_API_KEY`). Kaksi ajoa: skeema hyväksyttiin, vastausaika 26 s / 21 s, toisella ajolla
28 210 tokenia luettiin välimuistista, kaikki lainaukset löytyivät lähteestä, sanallinen teksti
säilyi merkki merkiltä ja tulkintakysymys K1 nousi. Tulokset ja sisältöhavainnot: ADR-0005.
Vastaus: `tests/recorded_llm/spike_c1.json`.

Uusintaa varten (avain on jo tallennettu käyttäjän ympäristömuuttujaan; uusi PowerShell-ikkuna
näkee sen):

```powershell
.\.venv\Scripts\python tools\spike_claude.py --live --out tests\recorded_llm\spike_c1.json
```

Mallille lähtee vain esimerkkimääräyksen teksti (*c-1 Täydentyvä keskusta*) sekä yleiskaavan
koodiluettelo ja liitteen 4 vakiomääräykset kontekstina. Kirjaa ADR-0005:een: onnistuiko
skeema (184 + 41 + 38 enumeraatioarvoa), vastausaika (ensimmäinen ajo sisältää skeeman
käännön), tokenit ja välimuistin osumat toisella ajolla, löytyivätkö lainaukset lähteestä ja
tuliko tulkintakysymys K1 (aluevaraus vai osa-alue). Tallennettu vastaus kelpaa testiadapterin
aineistoksi (`tests/recorded_llm/`), sillä siinä ei ole avainta.

---

## 4 Ensimmäinen linjauspalaveri

**Osallistujat:** 2–3 kaavoittajaa (yleiskaavoitus), paikkatietoasiantuntija, kehittäjä.
**Kesto:** 2 h. **Ennakkoaineisto:** toteutussuunnitelman luvut 6.10, 8 ja 14, laaturaportti
`docs/laaturaportti_liite3.md` sekä 30 testiyksikön ehdokaslista koosteesta (kehittäjä valitsee).

### Asialista

1. **Tavoitteet ja mittarit** (15 min): sovitaan luvun 2.3 tavoitearvot (taulukko alla).
2. **L-01 Muunnoksen yksikkö** (10 min): kooste vai yksittäinen lähdekaava.
   Suositus: kirjasto koosteesta (yhteiset ryhmät), Ryhti-vienti lähdekaavoittain.
3. **L-02 Rakenteistamisen laajuus** (15 min): VOOKA-minimi / määräystason rakenne / koko kaava
   kohteineen. Suositus: määräystaso + kytkentä vektoriaineistoon; tarkentuu tehtävän 6
   selvityksellä.
4. **L-03 Sanallisen tekstin pilkkominen** (10 min): ei pilkota / kappaleittain / aiheittain.
   Suositus VOOKA-tilassa: ei pilkota.
5. **L-04 Sanallisen määräyksen tyyppi yleiskaavassa** (15 min): `sanallinenMaarays` vai
   alakoodit (suunnittelu-, rakentamis-, suojelumääräys). Huom. muistion 16.2.2026 kohta 34
   ehdottaa alakoodien poistoa.
6. **L-05 Tiettyjä alueita koskevat yleismääräykset** (15 min): säilytys / rakenteinen lisäys /
   siirto. Esimerkki: "Yleiskaavan RA ja R -alueilla…". Suositus VOOKA: säilytys + rakenteinen
   lisäys (`rakennusluvanPeruste` + oikeusvaik_YK 12).
7. **L-06 Kirjaintunnukset** (10 min): alkuperäiset vai Katjan mukaiset (c-1 vs. C-1).
   Suositus VOOKA: alkuperäiset.
8. **L-07 Paikkasidonnaiset numeroarvot** (10 min): sanallisena vai omat kohteet (Kalevan
   70 000 k-m²). Suositus VOOKA: sanallisena.
9. **Liitteen 4 korjaukset** (10 min): `vahvistettava: true` -korjaukset (tehtävä 7).
10. **Testiaineisto ja annotointi** (10 min): 30 yksikköä vaiheeseen 1, vastuut ja aikataulu,
    80–120 yksikköä vaiheeseen 2.
11. **Seuraavat linjaukset** (5 min): L-08–L-14 seuraavaan palaveriin.

### Mittarien tavoitearvot (luku 2.3)

**Päätös 22.11.2026:** alustavat tavoitteet otetaan käyttöön sellaisinaan, ikään kuin
yleiskaavoitus olisi ne sopinut. Yleiskaavoituksen kanssa niitä ei ole vielä käsitelty, ja
niitä voidaan säätää myöhemmin tarpeen mukaan.

| Mittari | Alustava tavoite | Käytössä |
|---|---|---|
| Merkinnät, joiden ehdotus hyväksytään sellaisenaan | ≥ 70 % | ≥ 70 % |
| Korkean varmuuden ehdotuksista oikein | ≥ 98 % | ≥ 98 % |
| Tunnetuista monitulkintaisista kohdista nousee tulkintakysymykseksi | ≥ 90 % | ≥ 90 % |
| Voimassa olevan kaavan määräystekstin muutokset | 0 kpl | 0 kpl |
| Ryhmät latautuvat Arhoon ja läpäisevät Ryhdin määräystason validoinnin | 100 % hyväksytyistä | 100 % hyväksytyistä |
| Käsittelyaika merkintää kohden verrattuna käsin tehtyyn | vähintään puolittuu | vähintään puolittuu |
| Kustannus koko koosteen muunnokselle (lisäehdotus) | ≤ 30 $ | ≤ 30 $ |

**Päätös 22.11.2026 (ADR-0008):** L-01–L-07 ovat käyttäjän valintoja. Työkalu tarjoaa
vaihtoehdot ja suositellun oletuksen, ja käyttäjä valitsee kulloinkin, miten toimitaan. Kun
yleiskaavoitus päättää, että jokin asia tehdään aina samalla tavalla, valinta lukitaan
linjauskirjastossa, eikä sitä voi enää muuttaa käyttöliittymässä. Palaveria ei siis tarvita
ennen vaihetta 1. Yllä olevat suositukset ovat oletusten lähtökohta, ja ne tarkistetaan
ADR-0007:n näkökulmasta: määräykset muunnetaan uusien yleiskaavojen pohjaksi, ei
VOOKA-toimitukseksi.

Kirjaa päätökset muodossa *L-xx, päätös, perustelu, päivämäärä, hyväksyjä*. Kehittäjä vie ne
vaiheessa 1 tiedostoon `knowledge/org/tampere/linjaukset.yaml`.

---

## 5 QgsAuthManager-avainten ja lisäosan latauksen testi

**Osittain tehty 22.11.2026:** avainten tallennus, luku, päivitys ja poisto testattiin QGIS
3.44.7:ssä ilman käyttöliittymää, kertakäyttöisessä profiilissa ja testiavaimella. Kaikki
toimivat, eikä avain näkynyt asetustiedostoissa (ADR-0004). Lisäosapaketti ja tietopohja
latautuvat QGISin Pythonissa (TP-2026.11-1). **Jäljellä käyttäjälle** (käyttöliittymä):
lisäosan käyttöönotto lisäosien hallinnassa, *Tietoja*-ikkuna ja pääsalasanaikkuna alla olevilla
ohjeilla. **Käyttöliittymäosa tehty 22.11.2026** (käyttäjä, QGIS 3.44.7): onnistui,
tunniste `QgsSettings`issa sama kuin tallennetun määrityksen (ADR-0004).

**Lisäosan lataus:** linkki on luotu tälle työasemalle 22.11.2026 (`default`-profiili). Muilla
koneilla linkitä paketti QGIS-profiilin lisäosakansioon (PowerShell, säilön juuresta):

```powershell
New-Item -ItemType Junction -Path "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\kaavamaaraysavustaja" -Target (Resolve-Path .\kaavamaaraysavustaja)
```

Käynnistä QGIS, ota *Kaavamääräysavustaja* käyttöön lisäosien hallinnassa (kokeelliset
lisäosat sallittava) ja valitse *Lisäosat → Kaavamääräysavustaja → Tietoja*. Ikkunan pitäisi
näyttää "Tietopohja TP-2026.11-1".

**Avainten tallennus** QGISin Python-konsolissa (käytä testiarvoa, ei oikeaa avainta):

```python
from kaavamaaraysavustaja.plugin import auth

cfg_id = auth.store_api_key("claude", "testiavain-123")  # kysyy pääsalasanan
print(cfg_id, auth.stored_authcfg_id("claude"))
print(auth.load_api_key("claude") == "testiavain-123")  # True
auth.store_api_key("claude", "testiavain-456")  # päivitys samaan määritykseen
print(auth.load_api_key("claude"))
auth.remove_api_key("claude")
print(auth.load_api_key("claude"))  # None (tai ANTHROPIC_API_KEY)
```

Tarkista myös *Asetukset → Valinnat → Tunnistautuminen*, että määritys "Kaavamääräysavustaja –
Claude API" näkyy ja katoaa poiston jälkeen, ja ettei avain näy tiedostossa
`QGIS3.ini`. Kirjaa ADR-0004:ään QGIS-versio, toimiko jokainen rivi, ja mahdolliset
virheilmoitukset (erityisesti `storeAuthenticationConfig`-paluuarvon muoto).

---

## 6 VOOKA-soveltamisprofiilin ja digitalOrigin-koodien selvitys (L-02, L-12)

**Rajattu pois 22.11.2026 (ADR-0007).** Voimassa olevien kaavojen määräyksiä ei viedä
Ryhtiin VOOKA-aineistona, vaan niitä käytetään uusien yleiskaavojen valmistelussa. Alla oleva
selvitysohje säilytetään siltä varalta, että VOOKA-toimitus tulee myöhemmin ajankohtaiseksi.
VOOKA-profiili: https://iri.suomi.fi/model/vooka/.

**Lähteet:** https://ryhti.syke.fi/alueidenkaytto/tietomallimuotoinen-kaavoitus/
(soveltamisprofiilit, VOOKA), Syken validointisäännöt, sykefi/Ryhti-rajapintakuvaukset
(*Kysymykset-ja-vastaukset*), tarvittaessa kysymys Syken Ryhti-tukeen.

**Selvitettävät kysymykset:**

1. Mitkä kaavamääräystason tiedot VOOKA-profiili vaatii (pakolliset / suositellut)? Riittääkö
   kaavan rajaus ja kaava-asiakirjat, vai vaaditaanko kaavamääräysryhmiä ja -kohteita?
2. Saako voimassa olevan kaavan sanallisen määräyksen siirtää yhtenä sanallisena määräyksenä
   (L-03), ja miten sanallisen määräyksen laji valitaan (L-04)?
3. Mitkä Ryhdin validointisäännöt eivät koske VOOKA-kaavoja (esim. liitteen 4 otsikot,
   kirjaintunnukset, elinkaaren tila)? Sääntötunnisteet kirjataan.
4. Mikä elinkaaren tila (`kaavaelinkaari`) ja mitkä päivämäärät annetaan voimassa olevalle
   kaavalle?
5. Miten koosteen merkinnät kohdistetaan useaan lähdekaavaan (L-01, K15)?
6. **digitalOrigin** (koodisto RY_DigitaalinenAlkupera, haettu koodistopalvelusta 22.11.2026):

   | Koodi | Nimi |
   |---|---|
   | 01 | Tietomallin mukaan laadittu |
   | 02 | Kokonaan digitoitu |
   | 03 | Osittain digitoitu (osa kaavasta, esim. rajauksen lisäksi aluevaraukset, digitoitu jälkikäteen; tulkinta tehtävä alkuperäisistä asiakirjoista) |
   | 04 | Rajaus digitoitu |
   | 0401 | Rajaus useamman kunnan alueella |

   Kysymys: onko avustajan tuottama kaava (määräykset rakenteistettu, kohteet vektoriaineistosta)
   "02 Kokonaan digitoitu" vai "03 Osittain digitoitu", ja riippuuko vastaus siitä,
   rakenteistetaanko kaikki määräykset? Vaikuttaako arvo validointiin?

**Tulokset:**

| # | Vastaus | Lähde |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |

---

## 7 Liitteen 4 korjausten vahvistus

**Siirretty myöhemmäksi 22.11.2026.** Korjaukset pysyvät tietopohjassa merkinnällä
`vahvistettava: true`. Vaiheessa 1 avustajan kannattaa näyttää ne käyttäjälle
vahvistamattomina.

Korjaustiedostossa `knowledge/katja/annex4_corrections.yaml` on korjauksia, joissa
`vahvistettava: true`. Ne perustuvat koodistojen muutoslokiin tai rivin otsikkoon, mutta
asiantuntijan on hyväksyttävä ne:

| Korjaus | Kysymys |
|---|---|
| YK-046-c, YK-047-c | Tuuli- ja aurinkovoimatuotannon energiahuollon alueilla on toinenkin kaavamääräyslaji (`tuulivoimalaAlue` / `aurinkovoimalaAlue`). Tarkoituksellinen vai virhe? |
| YK-163, YK-216, MK-105, MK-134 | Valtakunnallisesti merkittävä arkeologinen kohde → `arkeologinenKohde` + lisätieto `valtakunnallinen`. Oikea korvaus? |
| AK-119 | Saunan rakennusala → `rakennusala` + käyttötarkoituskohdistus `sauna`. |
| AK-057-a/b | Jalankulkukatu, jolla tontille ajo sallittu: `tontilleAjoSallittu` lisätiedon lajiksi. |
| MK-110 | Koodisarakkeessa värikoodi → `luonnonRauhanKannaltaTarkeaAlue` (otsikon perusteella). |

Lisäksi laaturaportin huomioissa on koodeja, jotka eivät kuulu välilehden kaavalajin
määrityshierarkiaan (esim. `tie` yleiskaavassa, `valtatie` maakuntakaavassa). Ne voivat olla
koodiston tai taulukon puutteita: kannattaa kysyä YM:ltä/Sykeltä.

Hyväksytyistä muutetaan `vahvistettava: false`; hylätyt poistetaan tai korjataan, ja tietopohja
rakennetaan uudelleen (`python tools\build_knowledge.py`).

---

## Muut huomiot

- `kaavamaaraysavustaja/metadata.txt`: QGIS vaatii sähköpostiosoitteen. Paikalla on
  `noreply@example.invalid`; vaihda haluamaasi julkiseen osoitteeseen ennen julkaisua
  lisäosarekisteriin.
