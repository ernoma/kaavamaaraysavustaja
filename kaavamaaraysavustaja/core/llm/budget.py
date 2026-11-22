"""Cost estimate before a run and a per-run budget limit (plan 6.8, ADR-0013).

Prices are data (``knowledge/llm/hinnasto.yaml``). The estimate counts characters (no SDK
needed); the actual cost is computed from the token usage the provider returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from kaavamaaraysavustaja.core.llm.base import Usage
from kaavamaaraysavustaja.knowledge.base import KnowledgeBase


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class Prices:
    model: str
    provider: str
    input: float  # USD per million tokens
    output: float
    cache_write: float
    cache_read: float
    verified: bool

    def cost(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.input
            + usage.output_tokens * self.output
            + usage.cache_creation_input_tokens * self.cache_write
            + usage.cache_read_input_tokens * self.cache_read
        ) / 1_000_000


@dataclass(frozen=True)
class Pricing:
    models: dict[str, Prices]
    output_tokens_per_unit: int
    chars_per_token: float

    @classmethod
    def load(cls, kb: KnowledgeBase) -> Pricing:
        data = yaml.safe_load((kb.directory / kb.manifest["hinnasto"]).read_text(encoding="utf-8"))
        models = {
            name: Prices(
                model=name,
                provider=raw.get("toimittaja", ""),
                input=float(raw["syote"]),
                output=float(raw["tuloste"]),
                cache_write=float(raw.get("valimuisti_kirjoitus", raw["syote"])),
                cache_read=float(raw.get("valimuisti_luku", raw["syote"])),
                verified=bool(raw.get("tarkistettu")),
            )
            for name, raw in data["mallit"].items()
        }
        estimate = data.get("arvio") or {}
        return cls(
            models,
            int(estimate.get("tulostetokenit_yksikko", 3000)),
            float(estimate.get("merkkia_per_token", 3.0)),
        )

    def prices(self, model: str) -> Prices:
        if model in self.models:
            return self.models[model]
        raise KeyError(f"Mallin {model} hintaa ei ole hinnastossa (knowledge/llm/hinnasto.yaml).")

    def tokens(self, text: str) -> int:
        return int(len(text) / self.chars_per_token) + 1


@dataclass
class Estimate:
    model: str
    units: int
    static_tokens: int
    task_tokens: int  # all units together
    output_tokens: int
    usd: float
    cached: bool
    verified_prices: bool
    first_call_usd: float = 0.0  # includes the cache write
    next_call_usd: float = 0.0

    def describe(self) -> str:
        cache = "välimuisti käytössä" if self.cached else "ei välimuistia"
        note = "" if self.verified_prices else " (hinta vahvistamaton)"

        def n(value: int) -> str:
            return f"{value:,}".replace(",", " ")

        return (
            f"{self.units} yksikköä mallille {self.model}: staattinen konteksti noin {n(self.static_tokens)} "
            f"tokenia ({cache}), tehtävät noin {n(self.task_tokens)} ja tulosteet noin {n(self.output_tokens)} "
            f"tokenia; arvio {self.usd:.2f} ${note}"
        )


def estimate(
    pricing: Pricing,
    model: str,
    system_and_context: str,
    tasks: list[str],
    *,
    cached: bool,
    schema_text: str = "",
) -> Estimate:
    prices = pricing.prices(model)
    static = pricing.tokens(system_and_context) + pricing.tokens(schema_text)
    task_tokens = sum(pricing.tokens(t) for t in tasks)
    output = pricing.output_tokens_per_unit * len(tasks)
    if not tasks:
        usd = 0.0
    elif cached:
        usd = (
            static * prices.cache_write
            + static * (len(tasks) - 1) * prices.cache_read
            + task_tokens * prices.input
            + output * prices.output
        ) / 1_000_000
    else:
        usd = (
            static * len(tasks) * prices.input + task_tokens * prices.input + output * prices.output
        ) / 1_000_000
    per_task = (
        (task_tokens / len(tasks) * prices.input + pricing.output_tokens_per_unit * prices.output) / 1_000_000
        if tasks
        else 0.0
    )
    first = static * (prices.cache_write if cached else prices.input) / 1_000_000 + per_task
    following = static * (prices.cache_read if cached else prices.input) / 1_000_000 + per_task
    return Estimate(
        model, len(tasks), static, task_tokens, output, usd, cached, prices.verified, first, following
    )


@dataclass
class Budget:
    """Per-run limit in USD. ``None`` = no limit (not recommended for live runs)."""

    limit: float | None
    spent: float = 0.0
    calls: int = 0
    stopped: list[str] = field(default_factory=list)  # unit ids left without a model call

    def allows(self, next_cost: float) -> bool:
        return self.limit is None or self.spent + next_cost <= self.limit

    def add(self, cost: float) -> None:
        self.spent += cost
        self.calls += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "raja_usd": self.limit,
            "kaytetty_usd": round(self.spent, 4),
            "kutsuja": self.calls,
            "budjetin_takia_ohitetut": self.stopped,
        }
