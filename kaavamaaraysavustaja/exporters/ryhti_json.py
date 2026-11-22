"""Ryhti JSON fragments (planService ``PlanRegulationGroup`` / ``GeneralRegulationGroup``).

Per ADR-0007 the fragments are for checking regulation groups (schema and the Syke
validation API), not for delivering existing plans to Ryhti. ``dataType`` values use the
spelling of the Ryhti enumeration (``LocalizedText``, ``Code`` …); the descriptions in the
OpenAPI say ``"code"`` but the enumeration, which the schema validates, is capitalised.
"""

from __future__ import annotations

import uuid
from typing import Any

from kaavamaaraysavustaja.core.model import ConversionProject, GroupProposal, Regulation, SourceUnit, Value

URI = "http://uri.suomi.fi/codelist/rytj/"
# Life cycle status for checking only (kaavaelinkaari 03 = valmistelu); ADR-0007, vaihe 0.
DEFAULT_LIFECYCLE = URI + "kaavaelinkaari/code/03"
EXPORTED_KINDS = ("kaavakohde", "yleismaarays")


def value_json(value: Value) -> dict[str, Any]:
    if value.data_type == "LocalizedText":
        return {"dataType": "LocalizedText", "text": dict(value.text or {})}
    if value.data_type == "Text":
        return {"dataType": "Text", "text": next(iter((value.text or {}).values()), "")}
    if value.data_type == "Code" and value.code:
        data: dict[str, Any] = {
            "dataType": "Code",
            "code": value.code.uri,
            "codeList": value.code.codelist_uri,
        }
        if value.code_title:
            data["title"] = dict(value.code_title)
        return data
    if value.data_type in ("Numeric", "PositiveNumeric", "Decimal", "PositiveDecimal"):
        data = {"dataType": value.data_type, "number": value.number}
        if value.unit:
            data["unitOfMeasure"] = value.unit
        return data
    raise ValueError(f"Arvotyyppiä {value.data_type} ei osata viedä Ryhti-JSONiin")


def regulation_json(regulation: Regulation, lifecycle: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "planRegulationKey": regulation.key,
        "lifeCycleStatus": lifecycle,
        "type": regulation.type.uri,
    }
    if regulation.value is not None:
        data["value"] = value_json(regulation.value)
    if regulation.additional_infos:
        data["additionalInformations"] = [
            {"type": info.type.uri, **({"value": value_json(info.value)} if info.value else {})}
            for info in regulation.additional_infos
        ]
    if regulation.verbal_types:
        data["verbalRegulations"] = [code.uri for code in regulation.verbal_types]
    return data


def recommendation_json(proposal: GroupProposal, lifecycle: str) -> list[dict[str, Any]]:
    return [
        {"planRecommendationKey": rec.key, "lifeCycleStatus": lifecycle, "value": dict(rec.text)}
        for rec in proposal.recommendations
    ]


def group_json(
    proposal: GroupProposal, *, group_number: int | None = None, lifecycle: str = DEFAULT_LIFECYCLE
) -> dict[str, Any]:
    regulations = [regulation_json(r, lifecycle) for r in proposal.regulations]
    recommendations = recommendation_json(proposal, lifecycle)
    if proposal.kind == "yleismaarays":
        data: dict[str, Any] = {
            "generalRegulationGroupKey": proposal.key,
            "titleOfPlanRegulation": dict(proposal.title),
            "planRegulations": regulations,
        }
    else:
        data = {
            "planRegulationGroupKey": proposal.key,
            "titleOfPlanRegulation": dict(proposal.title),
            "planRegulations": regulations,
        }
        if proposal.letter_code:
            data["letterIdentifier"] = proposal.letter_code
        if proposal.color_code:
            data["colorNumber"] = proposal.color_code
    number = proposal.group_number if proposal.group_number is not None else group_number
    if number is not None:
        data["groupNumber"] = number
    if recommendations:
        data["planRecommendations"] = recommendations
    return data


def exported_units(project: ConversionProject, *, include_duplicates: bool = False) -> list[SourceUnit]:
    return [
        u
        for u in project.units
        if u.proposal
        and u.proposal.kind in EXPORTED_KINDS
        and (u.proposal.regulations or u.proposal.recommendations)
        and (include_duplicates or u.duplicates_of is None)
        and u.proposal.status != "hylatty"
    ]


def project_fragments(project: ConversionProject, *, lifecycle: str = DEFAULT_LIFECYCLE) -> dict[str, Any]:
    """All groups of the project: ``planRegulationGroups`` and ``generalRegulationGroups``."""
    plan_groups, general_groups = [], []
    for number, unit in enumerate(exported_units(project), start=1):
        data = group_json(unit.proposal, group_number=number, lifecycle=lifecycle)
        (general_groups if unit.proposal.kind == "yleismaarays" else plan_groups).append(data)
    return {"planRegulationGroups": plan_groups, "generalRegulationGroups": general_groups}


# --------------------------------------------------------------------------------------
# Synthetic test plan for the Syke validation API (plan 6.11 point 3)

# A 1 km square in Tampere (EPSG:3067), shifted per group so the objects do not overlap.
ORIGIN = (327000.0, 6822000.0)


def _geometry(kind: str, index: int) -> dict[str, Any]:
    x0, y0 = ORIGIN[0] + 200.0 * (index % 4), ORIGIN[1] + 200.0 * (index // 4)
    if kind == "viiva":
        geometry = {"type": "LineString", "coordinates": [[x0 + 10, y0 + 10], [x0 + 150, y0 + 150]]}
    elif kind == "piste":
        geometry = {"type": "Point", "coordinates": [x0 + 80, y0 + 80]}
    else:
        geometry = {
            "type": "Polygon",
            "coordinates": [[[x0, y0], [x0 + 180, y0], [x0 + 180, y0 + 180], [x0, y0 + 180], [x0, y0]]],
        }
    return {"srid": "3067", "geometry": geometry}


def synthetic_plan(
    proposals: list[GroupProposal], *, lifecycle: str = DEFAULT_LIFECYCLE, name: str = "testi"
) -> dict[str, Any]:
    """Wrap regulation groups into a synthetic yleiskaava with one plan object per group."""
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "kaavamaaraysavustaja/" + name)
    side = 200.0 * 4
    area = {
        "srid": "3067",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [ORIGIN[0] - 50, ORIGIN[1] - 50],
                    [ORIGIN[0] + side + 50, ORIGIN[1] - 50],
                    [ORIGIN[0] + side + 50, ORIGIN[1] + side * 2 + 50],
                    [ORIGIN[0] - 50, ORIGIN[1] + side * 2 + 50],
                    [ORIGIN[0] - 50, ORIGIN[1] - 50],
                ]
            ],
        },
    }
    plan_objects, relations, plan_groups, general_groups = [], [], [], []
    for index, proposal in enumerate(proposals):
        data = group_json(proposal, group_number=index + 1, lifecycle=lifecycle)
        if proposal.kind == "yleismaarays":
            general_groups.append(data)
            continue
        plan_groups.append(data)
        geometry_kind = (proposal.geometry_types or ["alue"])[0]
        object_key = str(uuid.uuid5(namespace, proposal.key))
        plan_objects.append(
            {
                "planObjectKey": object_key,
                "lifeCycleStatus": lifecycle,
                "undergroundStatus": URI + "RY_MaanalaisuudenLaji/code/01",
                "geometry": _geometry(geometry_kind, index),
                "name": {"fin": proposal.title.get("fin", "Testikohde")},
            }
        )
        relations.append({"planObjectKey": object_key, "planRegulationGroupKey": proposal.key})
    plan: dict[str, Any] = {
        "planKey": str(uuid.uuid5(namespace, "plan")),
        "lifeCycleStatus": lifecycle,
        "legalEffectOfLocalMasterPlans": [URI + "oikeusvaik_YK/code/1"],
        "scale": 10000,
        "geographicalArea": area,
        "planDescription": "Kaavamääräysavustajan testikaava (synteettinen, ei oikea kaava)",
        "planObjects": plan_objects,
        "planRegulationGroups": plan_groups,
        "planRegulationGroupRelations": relations,
    }
    if general_groups:
        plan["generalRegulationGroups"] = general_groups
    return plan
