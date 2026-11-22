"""Output JSON Schema for regulation conversion, with code enums from the knowledge base.

The model can only return codes that exist, are valid, are not header-level codes and
belong to the plan level's extension (määrityshierarkia) on the given day (plan 6.8).
Structured outputs require ``additionalProperties: false`` and ``required`` on every object.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from kaavamaaraysavustaja.knowledge.codelists import (
    ADDITIONAL_INFO_TYPE,
    REGULATION_TYPE,
    VERBAL_REGULATION_TYPE,
    CodelistIndex,
)

PLAN_LEVELS = ("yleiskaava", "asemakaava", "maakuntakaava")
CONFIDENCE = ["korkea", "keskitaso", "matala"]
QUESTION_TYPES = [f"K{n}" for n in range(1, 16)]


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable_string() -> dict[str, Any]:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def code_enums(index: CodelistIndex, plan_level: str, on: date | None = None) -> dict[str, list[str]]:
    if plan_level not in PLAN_LEVELS:
        raise ValueError(f"Tuntematon kaavataso: {plan_level}")
    return {
        "regulation_types": sorted(c.value for c in index.usable_codes(REGULATION_TYPE, plan_level, on)),
        "additional_info_types": sorted(
            c.value for c in index.usable_codes(ADDITIONAL_INFO_TYPE, plan_level, on)
        ),
        # The verbal regulation type code list has no plan-level extensions.
        "verbal_types": sorted(c.value for c in index.usable_codes(VERBAL_REGULATION_TYPE)),
    }


def conversion_schema(index: CodelistIndex, plan_level: str, on: date | None = None) -> dict[str, Any]:
    enums = code_enums(index, plan_level, on)
    additional_info = _object(
        {
            "laji": {"type": "string", "enum": enums["additional_info_types"]},
            "arvo": _nullable_string(),
        }
    )
    regulation = _object(
        {
            "laji": {"type": "string", "enum": enums["regulation_types"]},
            "arvo": _nullable_string(),
            "lisatiedot": {"type": "array", "items": additional_info},
            "sanallisen_lajit": {"type": "array", "items": {"type": "string", "enum": enums["verbal_types"]}},
            "tekstiviitteet": {"type": "array", "items": {"type": "string"}},
        }
    )
    group = _object(
        {
            "otsikko": {"type": "string"},
            "kirjaintunnus": _nullable_string(),
            "ryhmatyyppi": {"type": "string", "enum": ["kaavakohde", "yleismaarays"]},
            "geometria": {"type": "array", "items": {"type": "string", "enum": ["alue", "viiva", "piste"]}},
            "maaraykset": {"type": "array", "items": regulation},
            "suositukset": {"type": "array", "items": {"type": "string"}},
        }
    )
    option = _object({"kuvaus": {"type": "string"}, "seuraus": {"type": "string"}})
    return _object(
        {
            "ryhmat": {"type": "array", "items": group},
            "perustelut": {
                "type": "array",
                "items": _object(
                    {
                        "vaite": {"type": "string"},
                        "lainaus": {"type": "string"},
                        "tietopohjaviite": {"type": "string"},
                        "varmuus": {"type": "string", "enum": CONFIDENCE},
                    }
                ),
            },
            "vaihtoehdot": {
                "type": "array",
                "items": _object({"kuvaus": {"type": "string"}, "miksi_ei_ensisijainen": {"type": "string"}}),
            },
            "tulkintakysymykset": {
                "type": "array",
                "items": _object(
                    {
                        "tyyppi": {"type": "string", "enum": QUESTION_TYPES},
                        "kysymys": {"type": "string"},
                        "vaihtoehdot": {"type": "array", "items": option},
                        "suositus": {"type": "string"},
                        "peruste": {"type": "string"},
                    }
                ),
            },
            "ratkaistut_kysymykset": {
                "type": "array",
                "items": _object(
                    {
                        "tunnus": {"type": "string"},
                        "valinta": {"type": "string"},
                        "peruste": {"type": "string"},
                        "lainaus": {"type": "string"},
                    }
                ),
            },
            "kokonaisvarmuus": {"type": "string", "enum": CONFIDENCE},
        }
    )
