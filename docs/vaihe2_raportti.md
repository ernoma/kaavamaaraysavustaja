# Vaihe 2: kielimalli, perustelut ja tulkintakysymykset – raportti

*22.11.2026 · tietopohja TP-2026.11-3 · kehotteet prompts/v1 v1 · avustaja 0.2.0*

Vaihe 2 ei edellytä Arhoa eikä kaavoittajia (ADR-0012). Testiaineiston odotukset ovat
kehittäjän annotoimia (`tila: vahvistamaton`), joten mittarit kertovat vastaavuuden
suunnitelman suosituksiin, eivät kaavoittajien hyväksyntää.

## 1 Mitä tehtiin

| Osa | Toteutus | ADR |
|---|---|---|
| Hybridiputki | `core/hybrid.py`: sääntöpohjainen → kielimalli vain yksiköille, joiden varmuus ei ole korkea → sääntömoottori → varmuus. Kaksoiskappaleet yhdellä kutsulla. Malli saa vaiheen 1 rakenteen, perustelut, sääntötulokset, avoimet kysymykset, ratkaistut kohdat ja linjausvalinnat. | 0013 |
| Tekstin koskemattomuus | Sanallinen teksti tulee aina lähteestä; malli vain luokittelee sen. R-19 on ehdoton myös hybridissä. | 0013 |
| Lainausten tarkistus ja varmuus | Lainauksen on oltava otsikon tai tekstin osamerkkijono, muuten perustelu hylätään ja varmuus on matala. Korkea varmuus vaatii mallin ja sääntöpohjaisen rakenteen yhtäpitävyyden. | 0013 |
| Kehotteet v1 dataksi | `knowledge/prompts/v1/`: järjestelmäohje, staattinen konteksti (koodit kuvauksineen, liite 4, K1–K15, linjaukset), kysymystyypit ja synteettiset esimerkit sanastohakuun. Manifestissa ja rakentajassa käsin ylläpidettävinä. Lisätietojen linjaus (vain kun liite 4, määre tai rakenne osoittaa). | 0013 |
| Tulkintakysymykset ja päätösloki | `core/decisions.py`: ratkaisut asetustiedostosta (`ratkaisut`), laajuus merkintä / projekti, tallennus projektiin, `--projekti` uudelleenajoon, ratkaisupohja `<nimi>_ratkaisut.yaml`. Mallin kysymykset yhdistetään ilman kaksoiskappaleita. | 0014 |
| Linjaus L-15 ja L-04/R-12 | L-15 otsikon valinta (oletus lähteen otsikko, Katja 2 §), L-04:n vaihtoehto kehittämisvyöhykkeen suunnittelumääräykselle. | 0015 |
| Kustannus ja budjetti | `core/llm/budget.py`, hinnat `knowledge/llm/hinnasto.yaml`: arvio ennen ajoa, `--budjetti`, `--arvio`. Tokenit, kustannus, malli, kehoteversio ja vastaukset provenance-tietoihin. Prompt caching käytössä. | 0013 |
| Mistral-adapteri | `core/llm/mistral.py`: `mistralai`-SDK laiskasti, JSON-skeema, yksi korjauskierros. Testit injektoidulla asiakkaalla. | 0013 |
| Jäsennin kartoille 1a–2 | Alaotsikot kappaleiksi, numeroidut osa-alueet alakohdiksi (K9), tavutettu yleismääräysotsikko, alaosiot, kartan 1c selite, `@merkinta` isolla tunnuksella. | 0009 |
| Testiaineisto | 107 yksikköä: Kartta 1 (30), keskustan kartat 1a–2 (52), kantakaupungin kartat 2–4 (25); odotetut lajit ja tarkistettavat kohdat. | – |
| Arviointiajuri | `tools/evaluate.py`: sääntöpohjainen vs. hybridi, tallennetut vastaukset `tests/recorded_llm/`, live-ajo jatkettavana. Laatuportti `tests/golden/test_golden_v2.py`. | – |

<!-- mittarit täydennetään live-ajon jälkeen -->
