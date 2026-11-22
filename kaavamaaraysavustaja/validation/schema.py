"""JSON Schema validation of Ryhti fragments against the knowledge base schema (plan 6.11 point 1).

``jsonschema`` is optional (development dependency); it is imported lazily so that the core
works without it in QGIS.
"""

from __future__ import annotations

from typing import Any


class SchemaValidatorUnavailable(RuntimeError):
    pass


def validate(instance: Any, definition: str, schema: dict[str, Any]) -> list[str]:
    """Validate ``instance`` against ``#/$defs/<definition>``; return error messages."""
    try:
        import jsonschema  # optional
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise SchemaValidatorUnavailable(
            "Skeemavalidointi vaatii jsonschema-paketin (pip install jsonschema)"
        ) from error
    wrapper = {"$schema": schema.get("$schema"), "$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"}
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
