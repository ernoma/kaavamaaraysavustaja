"""Rule engine v1 (plan 6.7, annex B). Rule metadata is data (``knowledge/rules/rules_v1.yaml``);
the checks are small Python functions in :mod:`checks`. No rule language of our own.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from kaavamaaraysavustaja.core.model import RuleResult, SourceUnit
from kaavamaaraysavustaja.core.rules.checks import CHECKS, CheckContext
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase


class RuleEngine:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.rules: list[dict[str, Any]] = kb.rules["saannot"]
        missing = [r["tunnus"] for r in self.rules if r["tarkistus"] not in CHECKS]
        if missing:
            raise RuntimeError(f"Sääntöjen tarkistusfunktiot puuttuvat: {', '.join(missing)}")

    def active(self, plan_level: str, mode: str, on: date | None = None) -> list[dict[str, Any]]:
        on = on or self.kb.valid_on
        result = []
        for rule in self.rules:
            if plan_level not in rule.get("kaavatasot", [plan_level]):
                continue
            if rule.get("tilat") and mode not in rule["tilat"]:
                continue
            validity = rule.get("voimassa") or {}
            start, end = validity.get("alkaen"), validity.get("paattyen")
            if start and str(start) > on.isoformat() or end and str(end) < on.isoformat():
                continue
            result.append(rule)
        return result

    def check(self, unit: SourceUnit, *, plan_level: str, mode: str) -> list[RuleResult]:
        if unit.proposal is None:
            return []
        ctx = CheckContext(self.kb, unit, unit.proposal, plan_level, mode)
        results = []
        for rule in self.active(plan_level, mode):
            for finding in CHECKS[rule["tarkistus"]](ctx):
                severity = (rule.get("tapaukset") or {}).get(finding.case, rule["vakavuus"])
                results.append(
                    RuleResult(
                        rule_id=rule["tunnus"],
                        severity=severity,
                        message=finding.message,
                        target=finding.target,
                        source=rule.get("lahde", ""),
                        ryhti_rules=list(rule.get("ryhti") or []),
                    )
                )
        return results

    def apply(self, unit: SourceUnit, *, plan_level: str, mode: str) -> None:
        if unit.proposal is not None:
            unit.proposal.rule_results = self.check(unit, plan_level=plan_level, mode=mode)
