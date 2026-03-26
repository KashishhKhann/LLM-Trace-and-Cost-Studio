import logging

from shared.cost import estimate_cost_usd


def test_estimate_cost_usd_known_pricing() -> None:
    cost = estimate_cost_usd("openai", "gpt-4o-mini", tokens_in=1000, tokens_out=2000)
    assert cost == 0.00135


def test_estimate_cost_usd_missing_pricing_returns_zero_and_logs_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        cost = estimate_cost_usd("unknown-provider", "unknown-model", tokens_in=500, tokens_out=500)

    assert cost == 0.0
    assert "Missing pricing for provider=unknown-provider model=unknown-model" in caplog.text
