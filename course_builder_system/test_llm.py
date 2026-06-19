"""
Offline tests for llm.py — no network calls, no real API key required.

Strategy:
  - Monkeypatch the module-level `_client` in llm so the SDK is never touched.
  - Use a temporary directory for both the cache dir and the log file so tests
    are hermetic (nothing written to the real .llm_cache/ or logs/).

Tests:
  (a) Cache hit: a second call with identical inputs returns the cached result
      WITHOUT invoking the mock client at all.
  (b) Token log: after a live (cache-miss) call, exactly one line is appended
      to the JSONL log and it contains the expected fields.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import llm  # noqa: E402 — local module in project root

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_response(text: str = "hello") -> MagicMock:
    """Build a minimal mock that looks like an anthropic.types.Message."""
    block = SimpleNamespace(type="text", text=text)
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    response = MagicMock()
    response.content = [block]
    response.usage = usage
    response.model = "claude-opus-4-8"
    # model_dump_json must return a valid JSON string (raw envelope)
    response.model_dump_json.return_value = json.dumps(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "model": "claude-opus-4-8",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
    )
    return response


MESSAGES = [{"role": "user", "content": "What is 2 + 2?"}]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect cache and log paths into a temp directory for the duration of the test."""
    cache_dir = tmp_path / ".llm_cache"
    log_dir = tmp_path / "logs"

    monkeypatch.setattr(llm, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(llm, "_LOG_DIR", log_dir)
    monkeypatch.setattr(llm, "_LOG_FILE", log_dir / "llm_calls.jsonl")
    # Provide a fake API key so the key-guard doesn't sys.exit in cache-miss tests.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake-key")

    return tmp_path


# ---------------------------------------------------------------------------
# (a) Cache hit: second call must NOT touch the client
# ---------------------------------------------------------------------------


def test_cache_hit_skips_api(isolated_dirs: Path):
    mock_response = _make_fake_response("four")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch.object(llm, "_client", mock_client):
        # First call — cache miss, goes to API
        r1 = llm.call(MESSAGES, use_cache=True)
        assert r1.cache_hit is False
        assert mock_client.messages.create.call_count == 1

        # Second call — identical inputs, should be a cache hit
        r2 = llm.call(MESSAGES, use_cache=True)
        assert r2.cache_hit is True
        assert r2.text == "four"
        # The client must NOT have been called a second time
        assert mock_client.messages.create.call_count == 1, (
            "API client was called on a cache hit — caching is broken"
        )


# ---------------------------------------------------------------------------
# (b) Token log: a cache-miss call appends a JSONL line with expected fields
# ---------------------------------------------------------------------------


def test_token_log_written_on_cache_miss(isolated_dirs: Path):
    mock_response = _make_fake_response("four")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    log_file = llm._LOG_FILE  # already redirected by the fixture

    with patch.object(llm, "_client", mock_client):
        llm.call(MESSAGES, use_cache=False)  # force a cache miss every time

    assert log_file.exists(), "Log file was not created"
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, f"Expected 1 log line, got {len(lines)}"

    entry = json.loads(lines[0])
    assert entry["cache_hit"] is False
    assert entry["input_tokens"] == 10
    assert entry["output_tokens"] == 5
    assert "timestamp" in entry
    assert "prompt_hash" in entry
    assert "latency_s" in entry
    assert "model" in entry
    # Confirm no dollar-cost fields are present (deferred to S3.2)
    assert "cost" not in entry
    assert "cost_usd" not in entry


# ---------------------------------------------------------------------------
# (b-extra) Cache-hit log line has zeroed token counts
# ---------------------------------------------------------------------------


def test_token_log_cache_hit_zeroes_tokens(isolated_dirs: Path):
    mock_response = _make_fake_response("four")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    log_file = llm._LOG_FILE

    with patch.object(llm, "_client", mock_client):
        llm.call(MESSAGES, use_cache=True)  # miss — populates cache
        llm.call(MESSAGES, use_cache=True)  # hit

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    hit_entry = json.loads(lines[1])
    assert hit_entry["cache_hit"] is True
    assert hit_entry["input_tokens"] == 0
    assert hit_entry["output_tokens"] == 0


# ---------------------------------------------------------------------------
# Standalone runner (fallback if pytest isn't on PATH)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.execlp("python3", "python3", "-m", "pytest", __file__, "-v")
