"""Code list index (``knowledge/codelists/index.json``) lookups.

The index is generated from the koodistot.suomi.fi JSON exports by
``tools/build_knowledge.py``. Field names are English because the file is machine
generated and mirrors the code list API (ADR-0003).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from kaavamaaraysavustaja.knowledge.manifest import knowledge_dir

URI_PREFIX = "http://uri.suomi.fi/codelist/rytj/"

REGULATION_TYPE = "RY_Kaavamaarayslaji"
ADDITIONAL_INFO_TYPE = "RY_Kaavamaarayksen_Lisatiedonlaji"
VERBAL_REGULATION_TYPE = "RY_Sanallisen_Kaavamaarayksen_Laji"


@dataclass(frozen=True)
class Membership:
    start: str | None
    end: str | None

    def valid_on(self, day: date) -> bool:
        iso = day.isoformat()
        return (self.start is None or self.start <= iso) and (self.end is None or iso <= self.end)


@dataclass(frozen=True)
class Code:
    codelist: str
    value: str
    uri: str
    name: dict[str, str]
    description: dict[str, str]
    short_name: str | None
    parent: str | None
    level: int | None
    status: str
    start_date: str | None
    end_date: str | None
    header_level: bool
    memberships: dict[str, Membership] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.status == "VALID"

    def in_extension(self, extension: str, on: date | None = None) -> bool:
        membership = self.memberships.get(extension)
        if membership is None:
            return False
        return membership.valid_on(on or date.today())


class CodelistIndex:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self._codes: dict[tuple[str, str], Code] = {}
        self._by_uri: dict[str, Code] = {}
        for codelist, content in data["codelists"].items():
            for value, raw in content["codes"].items():
                code = Code(
                    codelist=codelist,
                    value=value,
                    uri=raw["uri"],
                    name=raw.get("name", {}),
                    description=raw.get("description", {}),
                    short_name=raw.get("short_name"),
                    parent=raw.get("parent"),
                    level=raw.get("level"),
                    status=raw["status"],
                    start_date=raw.get("start_date"),
                    end_date=raw.get("end_date"),
                    header_level=raw.get("header_level", False),
                    memberships={
                        name: Membership(m.get("start"), m.get("end"))
                        for name, m in raw.get("memberships", {}).items()
                    },
                )
                self._codes[(codelist, value)] = code
                self._by_uri[code.uri] = code

    @classmethod
    def load(cls, path: Path | None = None) -> CodelistIndex:
        path = path or knowledge_dir() / "codelists" / "index.json"
        with path.open(encoding="utf-8") as handle:
            return cls(json.load(handle))

    def codelists(self) -> list[str]:
        return list(self.data["codelists"])

    def version(self, codelist: str) -> str:
        return self.data["codelists"][codelist]["version"]

    def get(self, codelist: str, value: str) -> Code | None:
        return self._codes.get((codelist, value))

    def by_uri(self, uri: str) -> Code | None:
        return self._by_uri.get(uri)

    def codes(self, codelist: str) -> list[Code]:
        return [code for (name, _), code in self._codes.items() if name == codelist]

    def usable_codes(self, codelist: str, extension: str | None = None, on: date | None = None) -> list[Code]:
        """Valid, non-header codes, optionally limited to an extension (määrityshierarkia)."""
        return [
            code
            for code in self.codes(codelist)
            if code.is_valid
            and not code.header_level
            and (extension is None or code.in_extension(extension, on))
        ]
