from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TokenPrice:
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float

class PricingRegistry:
    """Editable price registry; no current vendor prices are embedded in code."""
    def __init__(self, prices: dict[tuple[str, str], TokenPrice] | None = None) -> None:
        self._prices = prices or {}

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "PricingRegistry":
        prices = {}
        for key, value in config.items():
            provider, model = key.split("/", 1)
            prices[(provider, model)] = TokenPrice(**value)
        return cls(prices)

    def estimate(self, provider: str, model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> float:
        price = self._prices.get((provider, model))
        if price is None:
            return 0.0
        uncached = max(0, input_tokens - cached_input_tokens)
        return (uncached * price.input_per_million + cached_input_tokens * price.cached_input_per_million + output_tokens * price.output_per_million) / 1_000_000
