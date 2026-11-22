"""The active knowledge base (tietopohja) as one object: manifest, code lists, annex 4,
vocabulary, rules metadata, Ryhti validation messages, policies and approved conversions.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from kaavamaaraysavustaja.knowledge.codelists import URI_PREFIX, Code, CodelistIndex
from kaavamaaraysavustaja.knowledge.manifest import knowledge_dir, load_manifest


@dataclass
class KnowledgeBase:
    directory: Path
    manifest: dict[str, Any]
    index: CodelistIndex
    annex: dict[str, list[dict[str, Any]]]  # plan level -> annex 4 rows
    corrections: dict[str, dict[str, Any]]  # correction id -> correction
    vocabulary: dict[str, Any]
    rules: dict[str, Any]
    approved: list[dict[str, Any]]
    ryhti_messages: dict[str, str] = field(default_factory=dict)  # rule_key(rule id) -> plain message
    schema: dict[str, Any] | None = None

    @classmethod
    def load(cls, directory: Path | None = None) -> KnowledgeBase:
        directory = directory or knowledge_dir()
        manifest = load_manifest(directory)

        def read_yaml(relative: str) -> Any:
            return yaml.safe_load((directory / relative).read_text(encoding="utf-8"))

        annex_doc = read_yaml(manifest["katja"]["liite4"])
        corrections = read_yaml(manifest["katja"]["korjaukset"])["korjaukset"]
        messages: dict[str, str] = {}
        with (directory / manifest["ryhti"]["validointiviestit"]).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                messages[rule_key(row["Sääntö_ID_en"])] = row["Selkokielinen paluuarvo"].strip()
        return cls(
            directory=directory,
            manifest=manifest,
            index=CodelistIndex.load(directory / manifest["koodistoindeksi"]),
            annex=annex_doc["kaavalajit"],
            corrections={c["id"]: c for c in corrections},
            vocabulary=read_yaml(manifest["sanasto"]),
            rules=read_yaml(manifest["saannot"]),
            approved=read_yaml(manifest["hyvaksytyt"])["ryhmat"],
            ryhti_messages=messages,
        )

    @property
    def version(self) -> str:
        return self.manifest["tietopohja"]

    @property
    def valid_on(self) -> date:
        return date.fromisoformat(str(self.manifest["voimassa_alkaen"]))

    def load_schema(self) -> dict[str, Any]:
        if self.schema is None:
            path = self.directory / self.manifest["ryhti"]["skeema"]
            self.schema = json.loads(path.read_text(encoding="utf-8"))
        return self.schema

    # -- codes ----------------------------------------------------------------------------

    def code(self, codelist: str, value: str) -> Code | None:
        return self.index.get(codelist, value)

    def uri(self, codelist: str, value: str) -> str:
        code = self.index.get(codelist, value)
        return code.uri if code else f"{URI_PREFIX}{codelist}/code/{value}"

    def codelist_version(self, codelist: str) -> str | None:
        try:
            return self.index.version(codelist)
        except KeyError:
            return None

    def ryhti_message(self, rule_id: str) -> str | None:
        return self.ryhti_messages.get(rule_key(rule_id))


def normalize_ryhti_rule_id(rule_id: str) -> str:
    """Syke API ``quality__req_a_b`` → CSV form ``quality/req-a-b`` (vaihe 0, tehtävä 2)."""
    rule_id = rule_id.strip()
    if "/" in rule_id:
        return rule_id
    category, sep, rest = rule_id.partition("__")
    if not sep:
        return rule_id.replace("_", "-")
    return f"{category}/{rest.replace('_', '-')}"


def rule_key(rule_id: str) -> str:
    """Comparison key for Ryhti rule ids: the CSV has odd spellings such as
    ``additionalInfoType`` and ``section-area -mandatory``."""
    return "".join(normalize_ryhti_rule_id(rule_id).split()).lower()