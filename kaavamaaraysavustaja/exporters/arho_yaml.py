"""Arho regulation group library (``format_version: 2``, ``library_type: regulation_group``).

The format follows the Arho plugin source (GispoCoding/arho-qgis-plugin, commit
fe456a8bac3e80df5b556ced9b667ba691ce7f72, see lahtoaineistot/arho/LAHDE.md):
``core/template_manager.py`` (format version, upgrade, empty values dropped) and
``core/models.py`` (``RegulationGroup/Regulation/AdditionalInformation/AttributeValue.
from_template_dict``). Code-valued additional information is written like Arho's own
``katja_yleiskaava.yaml``: a regulation type code as its value, other code lists as a URI.

General regulations are not part of the library format (Arho enters them on the plan).
"""

from __future__ import annotations

from typing import Any

import yaml

from kaavamaaraysavustaja.core.model import ConversionProject, GroupProposal, Regulation, Value
from kaavamaaraysavustaja.exporters.ryhti_json import exported_units

FORMAT_VERSION = 2
LIBRARY_TYPE = "regulation_group"
ARHO_SOURCE_COMMIT = "fe456a8bac3e80df5b556ced9b667ba691ce7f72"
GEOMETRY = {"alue": "Alue", "viiva": "Viiva", "piste": "Piste"}
REGULATION_TYPE = "RY_Kaavamaarayslaji"


def clean(data: Any) -> Any:
    """Drop None, empty strings and empty lists like Arho's ``TemplateManager._clean_data``."""
    if isinstance(data, dict):
        cleaned = {k: clean(v) for k, v in data.items()}
        return {k: v for k, v in cleaned.items() if v is not None and v != "" and v != []}
    if isinstance(data, list):
        return [clean(item) for item in data]
    return data


def value_fields(value: Value | None, *, code_only: bool = False) -> dict[str, Any]:
    if value is None:
        return {}
    if value.data_type == "Code" and value.code:
        code = value.code.value if value.code.codelist == REGULATION_TYPE else value.code.uri
        return {"code_value": code} if code_only else {"value_data_type": "Code", "code_value": code}
    if value.data_type in ("LocalizedText", "Text"):
        return {"value_data_type": value.data_type, "text_value": dict(value.text or {})}
    return {"value_data_type": value.data_type, "numeric_value": value.number, "unit": value.unit}


def regulation_dict(regulation: Regulation) -> dict[str, Any]:
    return {
        "regulation_code": regulation.type.value,
        **value_fields(regulation.value),
        "additional_information": [
            {"type": info.type.value, **value_fields(info.value, code_only=True)}
            for info in regulation.additional_infos
        ],
        "verbal_regulation_types": [code.value for code in regulation.verbal_types],
    }


def group_dict(proposal: GroupProposal) -> dict[str, Any]:
    return {
        "heading": dict(proposal.title),
        "letter_code": proposal.letter_code,
        "color_code": proposal.color_code,
        "group_number": proposal.group_number,
        "category": proposal.category,
        "geometry": [GEOMETRY[g] for g in proposal.geometry_types if g in GEOMETRY],
        "plan_regulations": [regulation_dict(r) for r in proposal.regulations],
        "plan_propositions": [{"value": dict(rec.text)} for rec in proposal.recommendations],
    }


def library(
    project: ConversionProject, *, name: str | None = None, include_incomplete: bool = False
) -> dict[str, Any]:
    """Library dict. Groups with rule errors are left out unless ``include_incomplete``."""
    groups = []
    for unit in exported_units(project):
        proposal = unit.proposal
        if proposal.kind != "kaavakohde":
            continue
        if not include_incomplete and proposal.results("virhe"):
            continue
        groups.append(group_dict(proposal))
    meta = project.meta
    return clean(
        {
            "format_version": FORMAT_VERSION,
            "name": name or f"{meta.title} (muunnettu)",
            "version": 1,
            "description": (
                f"Kaavamääräysavustaja {meta.assistant_version} · tietopohja {meta.knowledge_version} · "
                f"{meta.map or 'kaikki kartat'} · sääntöpohjainen muunnos, tarkistamaton"
            ),
            "library_type": LIBRARY_TYPE,
            "plan_regulation_groups": groups,
        }
    )


def dumps(data: dict[str, Any]) -> str:
    # No line folding: the verbal text must stay character by character as in the source.
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=2**31 - 1
    )
