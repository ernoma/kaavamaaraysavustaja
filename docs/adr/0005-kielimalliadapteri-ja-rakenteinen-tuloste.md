# ADR-0005 Kielimalliadapteri ja rakenteinen tuloste

- Tila: hyväksytty 22.11.2026; Claude-adapterin live-ajo tehty 22.11.2026 (ks. Live-ajo)
- Lähde: toteutussuunnitelma A3, A6, 6.8

## Päätös

- Rajapinta `core.llm.base.LLMProvider.generate_structured(StructuredRequest) -> StructuredResponse`.
  Pyyntö jakautuu vakaaseen osaan (ohje, staattinen konteksti; välimuistitetaan) ja
  vaihtuvaan osaan (määräysyksikkö).
- Tulosteskeema (`core.llm.schema.conversion_schema`) generoidaan tietopohjasta kaavatason
  mukaan. Kaavamääräyslajit, lisätiedon lajit ja sanallisen määräyksen lajit ovat
  enumeraatioita, joissa on vain voimassa olevat, ei-otsikkotason koodit, jotka kuuluvat
  kaavatason määrityshierarkiaan. Avaimet ovat suomeksi kuten suunnitelman tulosteskeemassa.
- Claude-adapteri (`core.llm.claude.ClaudeProvider`): virallinen `anthropic`-SDK, oletusmalli
  `claude-opus-5-5`, `output_config.format` (`json_schema`), `output_config.effort` laatutasona
  (oletus `medium`), staattinen konteksti `cache_control`-merkinnällä. Palvelinpuolen
  kieltäytymisvara (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) on päällä
  oletuksena ja kytkettävissä pois; varamallin käyttö näkyy varoituksena. `refusal` ja
  `max_tokens` käsitellään omina virheinään.
- SDK tuodaan vasta adapteria luotaessa. Testiadapteri `FakeProvider` palauttaa tallennetun
  tai funktion tuottaman vastauksen, joten CI ei käytä verkkoa.
- Mistral-adapteri tehdään vaiheessa 2 samalla rajapinnalla.

## Seuraukset

- Piikki `tools/spike_claude.py` muuntaa esimerkin *c-1 Täydentyvä keskusta*; live-ajo:
  `--live` (kustannus noin 0,05–0,15 $). Yleiskaavan skeemassa on 184 kaavamääräyslajia,
  41 lisätiedon lajia ja 38 sanallisen määräyksen lajia enumeraatioina.
- Lainausten tarkistus tehdään itse (citations ei toimi rakenteisen tulosteen kanssa).

## Live-ajo 22.11.2026

`tools/spike_claude.py --live`, malli `claude-opus-5-5`, effort `medium`, Tampereen
työaseman kehitysympäristö (`anthropic` 2.12.0). Vastaus on tallennettu tiedostoon
`tests/recorded_llm/spike_c1.json` (ei avainta).

| Kohta | 1. ajo | 2. ajo |
|---|---|---|
| Skeema (184 + 41 + 38 enumeraatioarvoa) hyväksyttiin | kyllä | kyllä |
| `stop_reason` | `end_turn` | `end_turn` |
| Vastausaika (sisältää skeeman ensikäännöksen 1. ajossa) | 26,2 s | 21,1 s |
| Syötetokenit: välimuistiin kirjoitettu / luettu / muut | 28 210 / 0 / 265 | 0 / 28 210 / 265 |
| Tulostetokenit | 2 843 | 2 678 |
| Lainaukset löytyvät lähdetekstistä | kaikki | kaikki |

Sisältöhavainnot (1. ajo):

- Sanallisen määräyksen arvo on merkki merkiltä lähdeteksti (VOOKA).
- Kaavamääräyslaji `keskustatoimintojenAlue` + `paakayttotarkoitus`; tulkintakysymys **K1**
  (pääkäyttötarkoitus vai osa-alue, pienaakkosinen c-1) nousi odotetusti.
- Malli lisäsi lisätiedon `eheytettavaTaiTiivistettava` keskitason varmuudella ja nosti siitä
  oman tulkintakysymyksen (kehitettava / ei lisätietoa). Tämä pitää ratkaista linjauksella
  (lisätiedot vain, kun lähdeteksti tai liite 4 sen osoittaa?).
- Kalevan 70 000 k-m² säilyi sanallisena ja `sallittuKerrosala` esitettiin hylättynä
  vaihtoehtona perusteluineen (vastaa L-07:n suositusta).
- Sanallisen määräyksen lajit: `kehittamisperiaate`, `taydennysrakentaminen`, `kaupanOhjaus`.
- Malli merkitsi K2-tyypiksi kysymyksen, joka ei välttämättä vastaa suunnitelman K2-määritelmää.
  Tulkintakysymysten tyyppien kuvaukset pitää antaa kehotteessa (vaihe 1).

Suuren enumeraatioskeeman riski on näin poistunut: skeema kääntyy ja välimuisti osuu.
