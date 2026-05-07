"""Budget tracker. Aborts the run before exceeding the configured USD cap."""
from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float   # USD per 1M input tokens
    output_per_mtok: float  # USD per 1M output tokens


# Pricing snapshot — adjust if Anthropic changes prices. Numbers as of 2026-05.
PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-6": ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-opus-4-7":   ModelPricing(input_per_mtok=15.0, output_per_mtok=75.0),
    "claude-haiku-4-5-20251001": ModelPricing(input_per_mtok=0.80, output_per_mtok=4.0),
}


@dataclass
class Budget:
    cap_usd: float
    spent_usd: float = 0.0
    log: list[tuple[str, float]] = field(default_factory=list)

    def cost_of(self, input_tokens: int, output_tokens: int, pricing: ModelPricing) -> float:
        return (input_tokens / 1_000_000) * pricing.input_per_mtok + (
            output_tokens / 1_000_000
        ) * pricing.output_per_mtok

    def would_exceed(self, input_tokens: int, output_tokens: int, pricing: ModelPricing) -> bool:
        return self.spent_usd + self.cost_of(input_tokens, output_tokens, pricing) > self.cap_usd

    def charge(
        self, label: str, input_tokens: int, output_tokens: int, pricing: ModelPricing
    ) -> None:
        cost = self.cost_of(input_tokens, output_tokens, pricing)
        if self.spent_usd + cost > self.cap_usd:
            raise BudgetExceeded(
                f"Adding {cost:.4f} USD for {label} would exceed cap "
                f"({self.spent_usd:.4f} + {cost:.4f} > {self.cap_usd:.4f})"
            )
        self.spent_usd += cost
        self.log.append((label, cost))
