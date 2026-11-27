"""Policy decisions (linjaukset) as user choices that can be locked (ADR-0008, ADR-0010).

The policy library ``knowledge/org/tampere/linjaukset.yaml`` lists the options and the
recommended default of each policy. A conversion takes its choices from command line
options or a settings file; a locked policy cannot be overridden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kaavamaaraysavustaja.core.model import PolicyChoice
from kaavamaaraysavustaja.knowledge.manifest import knowledge_dir

POLICY_FILE = "org/tampere/linjaukset.yaml"

# Options the rule-based conversion of phase 1 can carry out. The others are valid policy
# options but need the language model or plan objects (later phases).
IMPLEMENTED: dict[str, set[str]] = {
    "L-02": {"maaraystaso"},
    "L-03": {"ei_pilkota", "kappaleittain"},
    "L-05": {"sailytys", "sailytys_ja_rakenteinen_lisays"},
    "L-07": {"sanallisena"},
    "L-15": {"lahde", "katja"},
}


class PolicyError(ValueError):
    """An invalid or forbidden policy choice."""


@dataclass(frozen=True)
class Policy:
    id: str
    title: str
    question: str
    options: dict[str, str]  # value -> description
    default: str
    basis: str
    locked: bool
    decision: dict[str, Any] | None
    version: int
    question_types: tuple[str, ...]
    # Plain-language texts for the user (dock, P1-01/P1-04); never sent to the model.
    explanation: str = ""  # what the policy decides
    labels: dict[str, str] = field(default_factory=dict)  # value -> short plain name
    effects: dict[str, str] = field(default_factory=dict)  # value -> what choosing it does


@dataclass(frozen=True)
class PolicyLibrary:
    version: int
    organisation: str
    policies: dict[str, Policy]

    @classmethod
    def load(cls, path: Path | None = None) -> PolicyLibrary:
        path = path or knowledge_dir() / POLICY_FILE
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyLibrary:
        policies = {}
        for raw in data["linjaukset"]:
            options = {opt["arvo"]: opt.get("kuvaus", "") for opt in raw["vaihtoehdot"]}
            if raw["oletus"] not in options:
                raise PolicyError(f"{raw['tunnus']}: oletus {raw['oletus']!r} ei ole vaihtoehto")
            if raw.get("lukittu") and not raw.get("paatos"):
                raise PolicyError(f"{raw['tunnus']}: lukitulla linjauksella on oltava päätös")
            policies[raw["tunnus"]] = Policy(
                id=raw["tunnus"],
                title=raw["otsikko"],
                question=raw.get("kysymys", ""),
                options=options,
                default=raw["oletus"],
                basis=" ".join(str(raw.get("peruste", "")).split()),
                locked=bool(raw.get("lukittu")),
                decision=raw.get("paatos"),
                version=int(raw["versio"]),
                question_types=tuple(raw.get("tulkintakysymykset") or ()),
                explanation=_plain(raw.get("selite")),
                labels={
                    opt["arvo"]: _plain(opt.get("nimi")) for opt in raw["vaihtoehdot"] if opt.get("nimi")
                },
                effects={
                    opt["arvo"]: _plain(opt.get("vaikutus"))
                    for opt in raw["vaihtoehdot"]
                    if opt.get("vaikutus")
                },
            )
        return cls(int(data["versio"]), data.get("organisaatio", ""), policies)

    def resolve(self, overrides: dict[str, str] | None = None) -> list[PolicyChoice]:
        """Choices for a conversion: defaults, user overrides and locked policies."""
        overrides = dict(overrides or {})
        unknown = sorted(set(overrides) - set(self.policies))
        if unknown:
            raise PolicyError(
                f"Tuntematon linjaus: {', '.join(unknown)}. Linjaukset: {', '.join(self.policies)}"
            )
        choices = []
        for policy in self.policies.values():
            wanted = overrides.get(policy.id)
            if wanted is not None and wanted not in policy.options:
                raise PolicyError(
                    f"{policy.id} ({policy.title}): tuntematon vaihtoehto {wanted!r}. "
                    f"Vaihtoehdot: {', '.join(policy.options)}"
                )
            if policy.locked:
                if wanted is not None and wanted != policy.default:
                    raise PolicyError(
                        f"{policy.id} ({policy.title}) on lukittu: {policy.default} "
                        f"({describe_decision(policy.decision)}). Valintaa {wanted!r} ei voi käyttää."
                    )
                option, source = policy.default, "lukittu"
            elif wanted is not None:
                option, source = wanted, "kayttaja"
            else:
                option, source = policy.default, "oletus"
            implemented = IMPLEMENTED.get(policy.id)
            if implemented is not None and option not in implemented:
                raise PolicyError(
                    f"{policy.id} ({policy.title}): vaihtoehto {option!r} ei ole vielä käytettävissä "
                    f"sääntöpohjaisessa muunnoksessa. Käytettävissä: {', '.join(sorted(implemented))}"
                )
            choices.append(
                PolicyChoice(
                    id=policy.id,
                    option=option,
                    source=source,
                    policy_version=policy.version,
                    title=policy.title,
                    decision=policy.decision if policy.locked else None,
                )
            )
        return choices


def _plain(value: Any) -> str:
    return " ".join(str(value or "").split())


def describe_decision(decision: dict[str, Any] | None) -> str:
    if not decision:
        return "ei päätöstä"
    parts = [str(decision.get(key)) for key in ("hyvaksyja", "paivamaara") if decision.get(key)]
    return ", ".join(parts) or "päätös kirjattu"


def describe_choice(choice: PolicyChoice) -> str:
    """Text for rationales and the report, e.g. ``L-03: ei_pilkota (käyttäjän valinta)``."""
    source = {
        "oletus": "suositeltu oletus",
        "kayttaja": "käyttäjän valinta",
        "lukittu": f"Tampereen linjaus, lukittu: {describe_decision(choice.decision)}",
    }.get(choice.source, choice.source)
    return f"{choice.id}: {choice.option} ({source})"


def parse_overrides(values: list[str] | None) -> dict[str, str]:
    """``["L-03=kappaleittain"]`` → ``{"L-03": "kappaleittain"}``."""
    result: dict[str, str] = {}
    for value in values or []:
        key, sep, option = value.partition("=")
        if not sep or not key.strip() or not option.strip():
            raise PolicyError(f"Linjausvalinta on muotoa L-03=vaihtoehto, saatiin {value!r}")
        result[key.strip().upper()] = option.strip()
    return result


def load_settings(path: Path) -> dict[str, Any]:
    """Conversion settings file (ADR-0010): ``linjaukset: {L-03: kappaleittain}`` and others."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PolicyError(f"Asetustiedosto {path} ei ole YAML-sanakirja")
    known = {
        "linjaukset",
        "kaavataso",
        "tila",
        "kartta",
        "nimi",
        "ratkaisut",
        "kielimalli",
        "malli",
        "budjetti",
        "laatu",
    }
    unknown = sorted(set(data) - known)
    if unknown:
        raise PolicyError(f"Asetustiedostossa tuntemattomia kenttiä: {', '.join(unknown)}")
    policies = data.get("linjaukset") or {}
    if not isinstance(policies, dict):
        raise PolicyError("Asetustiedoston 'linjaukset' on muotoa {L-03: vaihtoehto}")
    data["linjaukset"] = {str(k).upper(): str(v) for k, v in policies.items()}
    if data.get("ratkaisut") is not None and not isinstance(data["ratkaisut"], list):
        raise PolicyError("Asetustiedoston 'ratkaisut' on lista")
    return data
