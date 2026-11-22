# Arho-lisäosasta kopioidut aineistot

| Tiedosto | Lähde | Versio | Lisenssi |
|---|---|---|---|
| `validointisaantojen_paluuarvot.csv` | [GispoCoding/arho-qgis-plugin](https://github.com/GispoCoding/arho-qgis-plugin), `arho_feature_template/resources/configs/validointisaantojen_paluuarvot.csv` | commit `507633d005b4193ccd3a53a1a0f20dc70f41b2b9` (19.8.2025), haettu 22.11.2026 | GPL-2.0 |

Ryhdin validointisäännöt (249 kpl) selkokielisine paluuviesteineen. Tiedosto on kopioitu
tavu tavulta komennolla:

```
gh api -H "Accept: application/vnd.github.raw" "repos/GispoCoding/arho-qgis-plugin/contents/arho_feature_template/resources/configs/validointisaantojen_paluuarvot.csv?ref=507633d005b4193ccd3a53a1a0f20dc70f41b2b9" > validointisaantojen_paluuarvot.csv
```

Tietopohjan rakentaja kopioi sen tiedostoksi `knowledge/ryhti/validation_messages.csv`.

Samalla haettiin Syken julkisen validointirajapinnan kuvaus
`../ryhti-openapi/ryhti-plan-public-validate-api.json`
([sykefi/Ryhti-rajapintakuvaukset](https://github.com/sykefi/Ryhti-rajapintakuvaukset),
`OpenApi/Alueidenkäyttö/Avoin/`, commit `52b4a708cbadc2c0dff5c30cde09214fc54f1928`, CC BY 4.0).

## Kirjastomuodon lähde (vaihe 1)

Arho-viejä (`kaavamaaraysavustaja/exporters/arho_yaml.py`) noudattaa kirjastomuotoa
`format_version: 2`, joka tarkistettiin Arhon lähdekoodista commitissa
`fe456a8bac3e80df5b556ced9b667ba691ce7f72` (19.11.2026), haettu 22.11.2026 (GPL-2.0). Tiedostoja ei
kopioitu säilöön; ne luettiin komennoilla:

```
gh api -H "Accept: application/vnd.github.raw" "repos/GispoCoding/arho-qgis-plugin/contents/arho_feature_template/core/template_manager.py?ref=fe456a8bac3e80df5b556ced9b667ba691ce7f72"
gh api -H "Accept: application/vnd.github.raw" "repos/GispoCoding/arho-qgis-plugin/contents/arho_feature_template/core/models.py?ref=fe456a8bac3e80df5b556ced9b667ba691ce7f72"
gh api -H "Accept: application/vnd.github.raw" "repos/GispoCoding/arho-qgis-plugin/contents/arho_feature_template/resources/libraries/regulation_groups/katja_yleiskaava.yaml?ref=fe456a8bac3e80df5b556ced9b667ba691ce7f72"
gh api -H "Accept: application/vnd.github.raw" "repos/GispoCoding/arho-qgis-plugin/contents/tests/test_library_format.py?ref=fe456a8bac3e80df5b556ced9b667ba691ce7f72"
```

Havainnot:

- `TemplateManager`: `LIBRARY_FORMAT_VERSION = 2`; ilman `format_version`-kenttää luettu
  tiedosto on muotoa 1. Uudempi muoto hylätään. `library_type` on `regulation_group`.
  Kirjoitettaessa tyhjät arvot (None, "", []) jätetään pois.
- `RegulationGroup.from_template_dict`: `heading` (kielistetty), `letter_code`,
  `color_code`, `group_number`, `plan_regulations`, `plan_propositions` (`Proposition(**…)`),
  `category` (oletus "Muut"). Arhon oma kirjasto käyttää lisäksi kenttää `geometry`
  (`[Alue, Piste]`).
- `Regulation.from_template_dict`: `regulation_code` (koodiarvo; tuntematon koodi →
  `TemplateSyntaxError`), arvokentät (`value_data_type`, `text_value`, `numeric_value`,
  `unit`, `code_list`, `code_value` …), `additional_information` (`type` + arvokentät),
  `regulation_number`, `subject_identifiers`, `verbal_regulation_types` (koodiarvot).
- `AttributeValueDataType`: `LocalizedText`, `Text`, `Numeric`, `PositiveNumeric`, `Decimal`,
  `PositiveDecimal`, `Code`, … (sama kirjoitusasu kuin Ryhdin enumeraatiossa).
- `katja_yleiskaava.yaml`: koodiarvoinen lisätieto on muotoa `type: kayttotarkoituskohdistus`
  + `code_value: tuulivoimalaAlue` (kaavamääräyslaji koodiarvona). Muiden koodistojen arvo
  on URI (`code_value: http://uri.suomi.fi/codelist/rytj/oikeusvaik_YK/code/12`).
