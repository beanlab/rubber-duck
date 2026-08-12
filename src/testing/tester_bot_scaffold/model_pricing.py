from dataclasses import dataclass
from decimal import Decimal


PER_MILLION_TOKENS = Decimal("1000000")


@dataclass(frozen=True)
class TokenPricing:
    input: Decimal
    cached_input: Decimal | None
    output: Decimal


@dataclass(frozen=True)
class TokenCost:
    input_cost: Decimal
    output_cost: Decimal

    @property
    def total(self) -> Decimal:
        return self.input_cost + self.output_cost


def _price(input_rate: str, cached_input_rate: str | None, output_rate: str) -> TokenPricing:
    return TokenPricing(
        input=Decimal(input_rate),
        cached_input=Decimal(cached_input_rate) if cached_input_rate else None,
        output=Decimal(output_rate),
    )


# Standard API text-token prices in USD per 1M tokens, verified against
# https://developers.openai.com/api/docs/pricing on 2026-07-11.
MODEL_PRICING = {
    "gpt-4": _price("30.00", None, "60.00"),
    "gpt-4-turbo": _price("10.00", None, "30.00"),
    "gpt-4o": _price("2.50", "1.25", "10.00"),
    "gpt-4o-mini": _price("0.15", "0.075", "0.60"),
    "gpt-4.1": _price("2.00", "0.50", "8.00"),
    "gpt-4.1-mini": _price("0.40", "0.10", "1.60"),
    "gpt-4.1-nano": _price("0.10", "0.025", "0.40"),
    "gpt-5": _price("1.25", "0.125", "10.00"),
    "gpt-5-mini": _price("0.25", "0.025", "2.00"),
    "gpt-5-nano": _price("0.05", "0.005", "0.40"),
    "gpt-5-pro": _price("15.00", None, "120.00"),
    "gpt-5-chat-latest": _price("1.25", "0.125", "10.00"),
    "gpt-5-codex": _price("1.25", "0.125", "10.00"),
    "gpt-5.1": _price("1.25", "0.125", "10.00"),
    "gpt-5.1-chat-latest": _price("1.25", "0.125", "10.00"),
    "gpt-5.1-codex": _price("1.25", "0.125", "10.00"),
    "gpt-5.1-codex-max": _price("1.25", "0.125", "10.00"),
    "gpt-5.1-codex-mini": _price("0.25", "0.025", "2.00"),
    "gpt-5.2": _price("1.75", "0.175", "14.00"),
    "gpt-5.2-pro": _price("21.00", None, "168.00"),
    "gpt-5.2-chat-latest": _price("1.75", "0.175", "14.00"),
    "gpt-5.2-codex": _price("1.75", "0.175", "14.00"),
    "gpt-5.3-chat-latest": _price("1.75", "0.175", "14.00"),
    "gpt-5.3-codex": _price("1.75", "0.175", "14.00"),
    "gpt-5.4": _price("2.50", "0.25", "15.00"),
    "gpt-5.4-mini": _price("0.75", "0.075", "4.50"),
    "gpt-5.4-nano": _price("0.20", "0.02", "1.25"),
    "gpt-5.4-pro": _price("30.00", None, "180.00"),
    "gpt-5.5": _price("5.00", "0.50", "30.00"),
    "gpt-5.5-pro": _price("30.00", None, "180.00"),
    "gpt-5.6-sol": _price("5.00", "0.50", "30.00"),
    "gpt-5.6-terra": _price("2.50", "0.25", "15.00"),
    "gpt-5.6-luna": _price("1.00", "0.10", "6.00"),
    "o1": _price("15.00", "7.50", "60.00"),
    "o1-pro": _price("150.00", None, "600.00"),
    "o3": _price("2.00", "0.50", "8.00"),
    "o3-mini": _price("1.10", "0.55", "4.40"),
    "o3-pro": _price("20.00", None, "80.00"),
    "o4-mini": _price("1.10", "0.275", "4.40"),
    "o3-deep-research": _price("5.00", None, "20.00"),
    "o4-mini-deep-research": _price("1.00", None, "4.00"),
}


def get_token_pricing(model: str) -> TokenPricing:
    try:
        return MODEL_PRICING[model]
    except KeyError as error:
        raise ValueError(f"No standard token pricing configured for model: {model}") from error


def calculate_token_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> TokenCost:
    pricing = get_token_pricing(model)
    cached_tokens = max(min(cached_tokens, input_tokens), 0)
    uncached_tokens = max(input_tokens - cached_tokens, 0)
    cached_rate = pricing.cached_input or pricing.input

    input_cost = (
        Decimal(uncached_tokens) * pricing.input
        + Decimal(cached_tokens) * cached_rate
    ) / PER_MILLION_TOKENS
    output_cost = Decimal(max(output_tokens, 0)) * pricing.output / PER_MILLION_TOKENS
    return TokenCost(input_cost=input_cost, output_cost=output_cost)
