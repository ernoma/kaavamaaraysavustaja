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

# Synthetic geometry in Tampere (EPSG:3067). Area reservations (main use) are adjacent
# 200 m squares in a row so that together they cover the plan boundary exactly (Ryhti rule
# req-geom-spatialplan-area-reservation-cover). Sub-areas, lines and points lie inside the
# first square. Without any area reservation a carrier group (W Vesialue) covers the plan.
ORIGIN = (327000.0, 6822000.0)
SIZE = 200.0
CARRIER_TITLE = "Testikaavan kantava aluevaraus (synteettinen)"


def _square(x0: float, y0: float, size: float) -> dict[str, Any]:
    ring = [[x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]]
    return {"type": "Polygon", "coordinates": [ring]}


def _inner_geometry(kind: str, index: int) -> dict[str, Any]:
    x0, y0 = ORIGIN[0] + 20 + 5 * index, ORIGIN[1] + 20 + 5 * index
    if kind == "viiva":
        return {"type": "LineString", "coordinates": [[x0, y0], [x0 + 120, y0 + 120]]}
    if kind == "piste":
        return {"type": "Point", "coordinates": [x0 + 60, y0 + 60]}
    return _square(x0, y0, 100.0)


def is_area_reservation(proposal: GroupProposal) -> bool:
    return any(
        info.type.value == "paakayttotarkoitus" for r in proposal.regulations for info in r.additional_infos
    )


def carrier_group(lifecycle: str, namespace: uuid.UUID) -> dict[str, Any]:
    return {
        "planRegulationGroupKey": str(uuid.uuid5(namespace, "carrier")),
        "titleOfPlanRegulation": {"fin": CARRIER_TITLE},
        "letterIdentifier": "W",
        "groupNumber": 0,
        "planRegulations": [
            {
                "planRegulationKey": str(uuid.uuid5(namespace, "carrier/r")),
                "lifeCycleStatus": lifecycle,
                "type": URI + "RY_Kaavamaarayslaji/code/vesialue",
                "additionalInformations": [
                    {"type": URI + "RY_Kaavamaarayksen_Lisatiedonlaji/code/paakayttotarkoitus"}
                ],
            }
        ],
    }


def synthetic_plan(
    proposals: list[GroupProposal], *, lifecycle: str = DEFAULT_LIFECYCLE, name: str = "testi"
) -> dict[str, Any]:
    """Wrap regulation groups into a synthetic yleiskaava with one plan object per group."""
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "kaavamaaraysavustaja/" + name)
    plan_objects, relations, plan_groups, general_groups = [], [], [], []

    def add_object(group_key: str, title: str, geometry: dict[str, Any]) -> None:
        object_key = str(uuid.uuid5(namespace, group_key))
        plan_objects.append(
            {
                "planObjectKey": object_key,
                "lifeCycleStatus": lifecycle,
                "undergroundStatus": URI + "RY_MaanalaisuudenLaji/code/01",
                "geometry": {"srid": "3067", "geometry": geometry},
                "name": {"fin": title},
            }
        )
        relations.append({"planObjectKey": object_key, "planRegulationGroupKey": group_key})

    reservations = 0
    for index, proposal in enumerate(proposals):
        data = group_json(proposal, group_number=index + 1, lifecycle=lifecycle)
        if proposal.kind == "yleismaarays":
            general_groups.append(data)
            continue
        plan_groups.append(data)
        kind = (proposal.geometry_types or ["alue"])[0]
        if kind == "alue" and is_area_reservation(proposal):
            geometry = _square(ORIGIN[0] + SIZE * reservations, ORIGIN[1], SIZE)
            reservations += 1
        else:
            geometry = _inner_geometry(kind, index)
        add_object(proposal.key, proposal.title.get("fin", "Testikohde"), geometry)
    if reservations == 0:
        carrier = carrier_group(lifecycle, namespace)
        plan_groups.insert(0, carrier)
        add_object(carrier["planRegulationGroupKey"], CARRIER_TITLE, _square(ORIGIN[0], ORIGIN[1], SIZE))
        reservations = 1
    area = {
        "srid": "3067",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [ORIGIN[0], ORIGIN[1]],
                    [ORIGIN[0] + SIZE * reservations, ORIGIN[1]],
                    [ORIGIN[0] + SIZE * reservations, ORIGIN[1] + SIZE],
                    [ORIGIN[0], ORIGIN[1] + SIZE],
                    [ORIGIN[0], ORIGIN[1]],
                ]
            ],
        },
    }
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
