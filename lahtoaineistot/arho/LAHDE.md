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
