"""Client of the Syke public plan validation API (Ryhti Plan Public Validate API), stdlib only.

Based on ``tools/syke_validate.py`` and the phase 0 test (docs/vaihe0_kayttajan_tehtavat.md,
task 2): ``planType`` is the bare code value (``21``), the test environment is the default
and rule ids are normalised (``quality__req_a_b`` → ``quality/req-a-b``) before they are
matched with ``knowledge/ryhti/validation_messages.csv``.

The key comes from the caller (QGIS: ``QgsAuthManager``; development: ``RYHTI_API_KEY``).
It is never logged or stored (CLAUDE.md rule 7).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from kaavamaaraysavustaja.knowledge.base import normalize_ryhti_rule_id

BASE_URLS = {
    "test": "https://api-test.ymparisto.fi/ryhti/plan-public",
    "prod": "https://api.ymparisto.fi/ryhti/plan-public",
}
VALIDATE_PATH = "/api/Plan/Validate"
ENV_KEY = "RYHTI_API_KEY"

# Rules about the plan as a whole (life cycle, plan boundary) that a synthetic test plan
# triggers but that say nothing about the regulation groups (plan 6.11 point 3).
PLAN_LEVEL_RULE_PREFIXES = ("lifecycle/",)
PLAN_LEVEL_RULE_PARTS = ("spatialplan-area-reservation-cover", "geographicarea", "spatialplancase")


@dataclass
class SykeFinding:
    rule_id: str  # as returned by the API
    rule: str  # normalised, e.g. quality/req-planregulationgroup-letteridentifier-not-null
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def plan_level(self) -> bool:
        return self.rule.startswith(PLAN_LEVEL_RULE_PREFIXES) or any(
            p in self.rule for p in PLAN_LEVEL_RULE_PARTS
        )


@dataclass
class SykeResult:
    status: int
    findings: list[SykeFinding]
    body: Any

    @property
    def ok(self) -> bool:
        return self.status == 200

    def regulation_findings(self) -> list[SykeFinding]:
        return [f for f in self.findings if not f.plan_level]


class SykeError(RuntimeError):
    pass


def api_key() -> str | None:
    """Development key from ``RYHTI_API_KEY`` (on Windows also the user environment in the registry)."""
    key = os.environ.get(ENV_KEY)
    if key or sys.platform != "win32":
        return key
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            return winreg.QueryValueEx(handle, ENV_KEY)[0] or None
    except OSError:
        return None


def validate_url(
    *, plan_type: str = "21", area: str = "837", env: str = "test", url: str | None = None
) -> str:
    # A full code URI is rejected with quality__req_invalid_query_param: send the bare value.
    plan_type = plan_type.rstrip("/").rsplit("/", 1)[-1]
    base = (url or BASE_URLS[env]).rstrip("/")
    if not base.endswith(VALIDATE_PATH):
        base += VALIDATE_PATH
    return f"{base}?{urllib.parse.urlencode({'planType': plan_type, 'administrativeAreaIdentifiers': area})}"


def parse_findings(body: Any) -> list[SykeFinding]:
    """Collect every object with a ``ruleId`` (any nesting); fall back to ``errors`` lists."""
    found: list[SykeFinding] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            rule_id = node.get("ruleId") or node.get("RuleId")
            if isinstance(rule_id, str):
                message = node.get("localizedMessage") or node.get("message") or ""
                if isinstance(message, dict):
                    message = message.get("fi") or message.get("fin") or next(iter(message.values()), "")
                details = {
                    k: v for k, v in node.items() if k not in ("ruleId", "localizedMessage", "message")
                }
                found.append(SykeFinding(rule_id, normalize_ryhti_rule_id(rule_id), str(message), details))
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(body)
    if not found and isinstance(body, dict) and isinstance(body.get("errors"), dict):
        for path, messages in body["errors"].items():
            for message in messages if isinstance(messages, list) else [messages]:
                found.append(SykeFinding(path, normalize_ryhti_rule_id(path), str(message)))
    return found


def validate_plan(
    plan: dict[str, Any],
    *,
    key: str,
    plan_type: str = "21",
    area: str = "837",
    env: str = "test",
    url: str | None = None,
    timeout: float = 60,
) -> SykeResult:
    if not key:
        raise SykeError(f"API-avain puuttuu (kehityksessä ympäristömuuttuja {ENV_KEY}).")
    request = urllib.request.Request(
        validate_url(plan_type=plan_type, area=area, env=env, url=url),
        data=json.dumps(plan, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Ocp-Apim-Subscription-Key": key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, text = response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode("utf-8", "replace")
    except urllib.error.URLError as error:
        raise SykeError(f"Yhteysvirhe: {error.reason} (tarkista välityspalvelin: HTTPS_PROXY)") from error
    if status in (401, 403):
        raise SykeError(f"HTTP {status}: API-avain puuttuu, on väärä tai tilaus ei kata rajapintaa.")
    try:
        body: Any = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        body = text
    return SykeResult(status, parse_findings(body) if body is not None else [], body)
