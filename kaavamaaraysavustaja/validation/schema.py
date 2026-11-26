"""JSON Schema validation of Ryhti fragments against the knowledge base schema (plan 6.11 point 1).

``jsonschema`` is optional (development dependency); it is imported lazily so that the core
works without it in QGIS.
"""

from __future__ import annotations

import copy
from typing import Any


class SchemaValidatorUnavailable(RuntimeError):
    pass


_DISCRIMINATED: dict[int, dict[str, Any]] = {}


def _data_type(definition: str) -> str:
    """``PositiveNumericValue`` → ``PositiveNumeric``; ``NumericRange`` and ``SpotElevation`` as such."""
    return definition.removesuffix("Value")


def discriminated_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """``$defs`` where a ``oneOf`` of value types is told apart by ``dataType``.

    The OpenAPI document generated from Ryhti's C# classes lists the attribute value types in a
    ``oneOf`` without a discriminator, so e.g. ``{"dataType": "PositiveNumeric", "number": 6000}``
    matches four alternatives and fails. Each alternative gets ``dataType`` = its own type.
    """
    key = id(schema)
    if key not in _DISCRIMINATED:
        defs = copy.deepcopy(schema["$defs"])

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                alternatives = node.get("oneOf")
                if (
                    isinstance(alternatives, list)
                    and alternatives
                    and all(
                        isinstance(a, dict) and "dataType" in defs.get(_ref_name(a), {}).get("properties", {})
                        for a in alternatives
                    )
                ):
                    node["oneOf"] = [
                        {"allOf": [a, {"properties": {"dataType": {"const": _data_type(_ref_name(a))}}}]}
                        for a in alternatives
                    ]
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)

        visit(defs)
        _DISCRIMINATED[key] = defs
    return _DISCRIMINATED[key]


def _ref_name(node: dict[str, Any]) -> str:
    return str(node.get("$ref", "")).rsplit("/", 1)[-1]


def validate(instance: Any, definition: str, schema: dict[str, Any]) -> list[str]:
    """Validate ``instance`` against ``#/$defs/<definition>``; return error messages."""
    try:
        import jsonschema  # optional
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise SchemaValidatorUnavailable(
            "Skeemavalidointi vaatii jsonschema-paketin (pip install jsonschema)"
        ) from error
    defs = discriminated_defs(schema)
    wrapper = {"$schema": schema.get("$schema"), "$defs": defs, "$ref": f"#/$defs/{definition}"}
    validator = jsonschema.Draft202012Validator(wrapper)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(juuri)'}: {e.message}" for e in errors]


def validate_fragments(fragments: dict[str, Any], schema: dict[str, Any]) -> dict[str, list[str]]:
    """Errors per group key for ``planRegulationGroups`` and ``generalRegulationGroups``."""
    problems: dict[str, list[str]] = {}
    for group in fragments.get("planRegulationGroups", []):
        errors = validate(group, "PlanRegulationGroup", schema)
        if errors:
            problems[group.get("planRegulationGroupKey", "?")] = errors
    for group in fragments.get("generalRegulationGroups", []):
        errors = validate(group, "GeneralRegulationGroup", schema)
        if errors:
            problems[group.get("generalRegulationGroupKey", "?")] = errors
    return problems
