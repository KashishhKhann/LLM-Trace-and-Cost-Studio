from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Placeholder per-token pricing in USD per 1K tokens.
PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o-mini": {"in_per_1k": 0.00015, "out_per_1k": 0.0006},
        "gpt-4.1-mini": {"in_per_1k": 0.0003, "out_per_1k": 0.0012},
    },
    "anthropic": {
        "claude-3-5-haiku": {"in_per_1k": 0.0008, "out_per_1k": 0.004},
    },
}


def estimate_cost_usd(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    provider_key = provider.lower()
    model_key = model.lower()
    provider_pricing = PRICING.get(provider_key, {})
    # Try exact match first, then fallback to prefix matching to handle model variants
    model_pricing = provider_pricing.get(model_key)
    if model_pricing is None:
        # attempt prefix match (e.g., real model ids with date suffixes)
        for known_model_key, pricing in provider_pricing.items():
            if model_key.startswith(known_model_key):
                model_pricing = pricing
                break

    if model_pricing is None:
        logger.warning("Missing pricing for provider=%s model=%s", provider, model)
        return 0.0

    in_per_1k = model_pricing["in_per_1k"]
    out_per_1k = model_pricing["out_per_1k"]
    total = (tokens_in / 1000.0) * in_per_1k + (tokens_out / 1000.0) * out_per_1k
    return round(total, 8)
