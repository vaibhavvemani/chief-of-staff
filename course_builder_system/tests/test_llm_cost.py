from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import llm


class _FakeMessages:
    def __init__(self, response) -> None:
        self.response = response
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _response(*, text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        model="claude-opus-4-8",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=11,
            output_tokens=7,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
        _request_id="req_test",
        model_dump_json=lambda: json.dumps({"id": "msg_test"}),
    )


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


def test_live_call_context_rejects_excess_calls_before_provider_use() -> None:
    with llm.live_call_context(
        stage="course_outcomes",
        course_id="bounded-course",
        max_calls=1,
        max_input_chars=1_000,
    ) as context:
        context.call_count = 1
        with pytest.raises(llm.LiveCallLimitExceeded, match="live call limit"):
            llm.call(
                [{"role": "user", "content": "Do not call the provider."}],
                use_cache=False,
            )


def test_live_call_context_rejects_oversized_input_before_provider_use() -> None:
    with llm.live_call_context(
        stage="course_outcomes",
        course_id="bounded-course",
        max_calls=1,
        max_input_chars=20,
    ):
        with pytest.raises(llm.LiveCallLimitExceeded, match="live input"):
            llm.call(
                [{"role": "user", "content": "This request exceeds the bound."}],
                use_cache=False,
            )


def test_missing_live_provider_key_fails_explicitly_and_emits_safe_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    events: list[tuple[str, dict]] = []

    def emit(event_type: str, **payload) -> None:
        events.append((event_type, payload))

    with llm.live_call_context(
        stage="course_outcomes",
        course_id="unready-course",
        max_calls=1,
        max_input_chars=1_000,
        emit=emit,
    ):
        with pytest.raises(llm.ProviderNotReady, match="ANTHROPIC_API_KEY"):
            llm.call(
                [{"role": "user", "content": "Return a bounded proposal."}],
                use_cache=False,
            )

    assert [event_type for event_type, _ in events] == [
        "model.call.started",
        "model.call.failed",
    ]
    assert events[-1][1]["error_type"] == "ProviderNotReady"


def test_structured_call_transforms_wire_schema_and_enforces_original_contract(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _FakeMessages(_response(text='{"count": 11}'))
    monkeypatch.setattr(llm, "_client", SimpleNamespace(messages=messages))
    monkeypatch.setattr(llm, "_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(llm, "_LOG_FILE", tmp_path / "logs" / "calls.jsonl")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["count"],
        "properties": {
            "count": {"type": "integer", "minimum": 1, "maximum": 10},
        },
    }

    with pytest.raises(llm.LLMError, match="violated the local contract"):
        llm.call(
            [{"role": "user", "content": "Return a count."}],
            schema=schema,
            use_cache=False,
        )

    wire_count = messages.kwargs["output_config"]["format"]["schema"]["properties"][
        "count"
    ]
    assert "minimum" not in wire_count
    assert "maximum" not in wire_count
    assert "minimum" in wire_count["description"]
    log = json.loads(llm._LOG_FILE.read_text(encoding="utf-8"))
    assert log["failure_type"] == "LLMError"
    assert log["input_tokens"] == 11
    assert log["output_tokens"] == 7


def test_paid_unclean_stop_is_logged_and_emits_safe_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _FakeMessages(_response(text="partial", stop_reason="max_tokens"))
    monkeypatch.setattr(llm, "_client", SimpleNamespace(messages=messages))
    monkeypatch.setattr(llm, "_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(llm, "_LOG_FILE", tmp_path / "logs" / "calls.jsonl")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    events: list[tuple[str, dict]] = []

    with llm.live_call_context(
        stage="outcomes",
        course_id="paid-failure",
        max_calls=1,
        max_input_chars=1_000,
        emit=lambda event_type, **payload: events.append((event_type, payload)),
    ):
        with pytest.raises(llm.LLMError, match="output truncated"):
            llm.call(
                [{"role": "user", "content": "Return a complete response."}],
                max_tokens=100,
                use_cache=False,
            )

    assert [event for event, _ in events] == [
        "model.call.started",
        "model.call.failed",
    ]
    assert events[-1][1]["input_tokens"] == 11
    assert events[-1][1]["estimated_cost_usd"] is not None
    log = json.loads(llm._LOG_FILE.read_text(encoding="utf-8"))
    assert log["failure_type"] == "LLMError"


def test_cached_structured_output_is_revalidated_without_cost(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = llm.LLMResult(
        text='{"count": 99}',
        raw={"id": "cached"},
        usage={"input_tokens": 40, "output_tokens": 10},
        model="claude-opus-4-8",
        prompt_hash="cached-hash",
        cache_hit=True,
        parsed={"count": 99},
    )
    monkeypatch.setattr(llm, "_load_cache", lambda _prompt_hash: cached)
    monkeypatch.setattr(llm, "_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(llm, "_LOG_FILE", tmp_path / "logs" / "calls.jsonl")
    events: list[tuple[str, dict]] = []
    schema = {
        "type": "object",
        "required": ["count"],
        "properties": {"count": {"type": "integer", "maximum": 10}},
    }

    with llm.live_call_context(
        stage="outcomes",
        course_id="cached-failure",
        max_calls=1,
        max_input_chars=1_000,
        emit=lambda event_type, **payload: events.append((event_type, payload)),
    ):
        with pytest.raises(llm.LLMError, match="cached structured output"):
            llm.call(
                [{"role": "user", "content": "Return a count."}],
                schema=schema,
            )

    assert [event for event, _ in events] == [
        "model.call.started",
        "model.call.failed",
    ]
    assert events[-1][1]["cache_hit"] is True
    log = json.loads(llm._LOG_FILE.read_text(encoding="utf-8"))
    assert log["cache_hit"] is True
    assert log["input_tokens"] == 0
    assert log["output_tokens"] == 0
    assert log["estimated_cost_usd"] == 0.0
