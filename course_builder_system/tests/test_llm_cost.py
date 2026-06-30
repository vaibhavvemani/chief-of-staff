from __future__ import annotations

import llm


def test_estimate_cost_uses_model_specific_and_cache_rates() -> None:
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
    }

    assert llm._estimate_cost_usd("claude-opus-4-8", usage) == 36.75


def test_estimate_cost_refuses_to_guess_unknown_model_price() -> None:
    assert llm._estimate_cost_usd("future-model", {"input_tokens": 100}) is None
