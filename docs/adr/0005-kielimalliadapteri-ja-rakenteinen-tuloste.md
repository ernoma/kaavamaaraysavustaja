# ADR-0005 Kielimalliadapteri ja rakenteinen tuloste

- Tila: hyväksytty 22.11.2026; Claude-adapterin live-ajo tekemättä (ei tunnistetietoja kehitysympäristössä)
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
- Avoin: toimiiko näin suuri enumeraatioskeema rakenteisen tulosteen rajoissa ja kuinka kauan
  skeeman ensikäännös kestää; kirjataan live-ajon jälkeen.
- Lainausten tarkistus tehdään itse (citations ei toimi rakenteisen tulosteen kanssa).
