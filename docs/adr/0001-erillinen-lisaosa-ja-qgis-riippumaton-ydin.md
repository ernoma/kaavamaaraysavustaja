# ADR-0001 Erillinen QGIS-lisäosa ja QGIS:stä riippumaton ydin

- Tila: hyväksytty 22.11.2026
- Lähde: toteutussuunnitelma A1, A9; vahvistetut reunaehdot 22.11.2026

## Tausta

Ensimmäinen versio on oltava käytettävissä ilman muutoksia Arhoon, ja ydin on voitava testata
CI:ssä ilman QGISia. Tuettavat QGIS-versiot 3.40–4.x.

## Päätös

- Säilön paketti `kaavamaaraysavustaja/` on samalla QGIS-lisäosan hakemisto (`metadata.txt`,
  `classFactory` paketin `__init__.py`:ssä). `classFactory` tuo `plugin`-alipaketin laiskasti.
- Alipaketit `core`, `knowledge`, `exporters` ja `validation` ovat puhdasta Pythonia (stdlib +
  PyYAML). Vain `plugin` ja `linking` saavat tuoda `qgis`-moduulin.
- Sääntö tarkistetaan testillä `tests/unit/test_architecture.py` (AST-tarkistus ja tuonti
  aliprosessissa, jossa `qgis`, PyQt, `openpyxl` ja kielimallien SDK:t on estetty).
- Qt-tuonnit tehdään `qgis.PyQt`:n kautta (Qt5/Qt6-yhteensopivuus QGIS 4:ssä).
- Lisenssi GPL-2.0-or-later.

## Seuraukset

- Ydin on ajettavissa komentoriviltä (vaihe 1: `kma convert`) ja CI:ssä.
- Lisäosan kehityskäytössä paketti linkitetään QGIS-profiilin `python/plugins`-kansioon
  (ks. `docs/vaihe0_kayttajan_tehtavat.md`). Jakelupaketin kokoaminen (zip, tietopohjan
  mukaan ottaminen) ratkaistaan vaiheessa 3.
