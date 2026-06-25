"""
llm.py — Anthropic Messages API wrapper for the Course Builder pipeline.

Every Phase 1 pipeline step that needs a model call imports this module.
Design goals:
  - Single, consistent call surface: `call(messages, ...)`.
  - Local prompt-hash disk cache to avoid redundant API calls during dev.
  - Raw token-count logging (no dollar costing — deferred to S3.2).
  - SDK-native retry (max_retries=4) so we never hand-roll backoff.
  - Forward-looking structured output via `schema` (JSON Schema dict).

Cache files:  .llm_cache/<sha256>.json  (gitignored)
Token log:    logs/llm_calls.jsonl      (gitignored, one JSON line per call)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()  # reads ANTHROPIC_API_KEY (and anything else) from .env

DEFAULT_MODEL = "claude-opus-4-8"

# Above this max_tokens, route through the streaming API. The SDK refuses
# non-streaming requests it estimates will exceed its ~10-minute socket timeout
# (i.e. large max_tokens), raising ValueError; streaming sidesteps that. It is
# transport only - `.get_final_message()` returns the same Message a create()
# would - so the cached result and the cache key are identical either way.
_STREAM_THRESHOLD = 8000

# Module-level client — SDK reads ANTHROPIC_API_KEY from the environment.
# max_retries=4 activates the SDK's built-in exponential backoff on 429/5xx.
# We do NOT guard against a missing key here; we guard inside `call()` so that
# importing the module is always safe (useful for tests and non-API callers).
_client = anthropic.Anthropic(max_retries=4)

_CACHE_DIR = Path(".llm_cache")
_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "llm_calls.jsonl"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMError(RuntimeError):
    """Raised when a live call returns output we cannot use.

    Covers a non-clean stop (truncation at max_tokens, a safety refusal, or a
    context-window overflow) and structured output that is not valid JSON. The
    point is to fail loudly with a request id instead of letting a downstream
    json.loads() blow up on truncated/empty text with an opaque error.
    """


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class LLMResult:
    """Returned by every `call()` invocation, cached or live."""

    text: str
    raw: dict[str, Any]  # serialised SDK response (or the cached dict)
    usage: dict[str, Any]  # raw token counts from response.usage
    model: str
    prompt_hash: str
    cache_hit: bool
    parsed: Any = field(default=None)  # populated when `schema` is provided


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _canonical_key(
    model: str,
    system: str | None,
    messages: list[dict[str, Any]],
    max_tokens: int,
    schema: dict[str, Any] | None,
    thinking: dict[str, Any] | None = None,
) -> str:
    """SHA-256 over a deterministic JSON serialisation of the full call spec.

    `thinking` is folded in ONLY when set, so cache entries written before
    thinking was a parameter still resolve for the common thinking-off path.
    `stream` is deliberately not part of the key: it is transport only and the
    final message is identical whether streamed or not.
    """
    payload = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        "schema": schema,
    }
    if thinking is not None:
        payload["thinking"] = thinking
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


_USABLE_STOP_REASONS = {"end_turn", "stop_sequence"}


def _raise_on_bad_stop(response: Any, max_tokens: int) -> None:
    """Raise LLMError if the model did not finish cleanly.

    A max_tokens / refusal / context-overflow stop means the text is truncated
    or empty; treating it as a complete answer (or parsing it as JSON) fails
    with an opaque error far from the cause. Fail here, with a request id.
    """
    stop = response.stop_reason
    if stop in _USABLE_STOP_REASONS:
        return
    rid = getattr(response, "_request_id", None)
    if stop == "max_tokens":
        detail = (
            f"output truncated at max_tokens={max_tokens} - raise max_tokens "
            "(streaming auto-engages above the threshold)"
        )
    elif stop == "refusal":
        detail = "model declined the request (stop_reason='refusal')"
    elif stop == "model_context_window_exceeded":
        detail = "input exceeded the model context window"
    else:
        detail = f"unexpected stop_reason={stop!r}"
    raise LLMError(f"{detail}; model={response.model} request_id={rid}")


def _cache_path(prompt_hash: str) -> Path:
    return _CACHE_DIR / f"{prompt_hash}.json"


def _load_cache(prompt_hash: str) -> LLMResult | None:
    path = _cache_path(prompt_hash)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return LLMResult(
        text=data["text"],
        raw=data["raw"],
        usage=data["usage"],
        model=data["model"],
        prompt_hash=data["prompt_hash"],
        cache_hit=True,
        parsed=data.get("parsed"),
    )


def _save_cache(result: LLMResult) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    path = _cache_path(result.prompt_hash)
    payload = {
        "text": result.text,
        "raw": result.raw,
        "usage": result.usage,
        "model": result.model,
        "prompt_hash": result.prompt_hash,
        "parsed": result.parsed,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_log(
    *,
    timestamp: str,
    model: str,
    prompt_hash: str,
    cache_hit: bool,
    usage: dict[str, Any],
    latency_s: float,
) -> None:
    """Append one JSON line to logs/llm_calls.jsonl.  No dollar cost — S3.2."""
    _LOG_DIR.mkdir(exist_ok=True)
    if cache_hit:
        # Cache hit: no new tokens were consumed from the API.
        log_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
    else:
        log_usage = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        }
    entry = {
        "timestamp": timestamp,
        "model": model,
        "prompt_hash": prompt_hash,
        "cache_hit": cache_hit,
        **log_usage,
        "latency_s": latency_s,
    }
    with _LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def call(
    messages: list[dict[str, Any]],
    *,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    schema: dict[str, Any] | None = None,
    thinking: dict[str, Any] | None = None,
    stream: bool | None = None,
    use_cache: bool = True,
) -> LLMResult:
    """Call the Anthropic Messages API, with local disk caching and token logging.

    Args:
        messages:   SDK-shaped list of {"role": ..., "content": ...} dicts.
        system:     Optional system prompt string.
        model:      Model identifier.  Defaults to DEFAULT_MODEL (claude-opus-4-8).
                    Accepted tiers: claude-opus-4-8 / claude-sonnet-4-6 / claude-haiku-4-5.
        max_tokens: Maximum output tokens.
        schema:     JSON Schema dict for structured output.  When provided, the API
                    is asked to return JSON that conforms to the schema, and
                    LLMResult.parsed is populated via json.loads().
        thinking:   Optional thinking config, e.g. {"type": "adaptive"} on
                    Opus 4.8 (budget_tokens is rejected on this tier). Off by
                    default; folded into the cache key only when set. Thinking
                    blocks are ignored when extracting text, so structured
                    output is unaffected.
        stream:     Tri-state. None (default) auto-streams when max_tokens
                    exceeds the streaming threshold; True/False force it. The
                    final message is identical either way.
        use_cache:  When False, always bypass the local cache and call the API.

    Returns:
        LLMResult with text, raw response dict, usage token counts, and
        (optionally) parsed structured output.

    Raises:
        SystemExit: If ANTHROPIC_API_KEY is unset and an API call is required.
        LLMError:   If the model stops uncleanly (truncation/refusal/context
                    overflow) or structured output is not valid JSON.
    """
    t0 = time.monotonic()
    timestamp = datetime.now(tz=UTC).isoformat()

    prompt_hash = _canonical_key(model, system, messages, max_tokens, schema, thinking)

    # ------------------------------------------------------------------
    # Cache hit path
    # ------------------------------------------------------------------
    if use_cache:
        cached = _load_cache(prompt_hash)
        if cached is not None:
            latency_s = time.monotonic() - t0
            _append_log(
                timestamp=timestamp,
                model=model,
                prompt_hash=prompt_hash,
                cache_hit=True,
                usage=cached.usage,
                latency_s=latency_s,
            )
            return cached

    # ------------------------------------------------------------------
    # API call path — guard the key here, not at import time.
    # ------------------------------------------------------------------
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ANTHROPIC_API_KEY is not set.  "
            "Add it to your .env file or export it in your shell before running."
        )

    # Build keyword arguments shared by the streaming and non-streaming paths.
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system is not None:
        kwargs["system"] = system
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    if thinking is not None:
        kwargs["thinking"] = thinking

    # Stream large outputs so we never trip the SDK's non-streaming timeout
    # guard; get_final_message() returns the same Message a create() would.
    should_stream = stream if stream is not None else max_tokens > _STREAM_THRESHOLD
    if should_stream:
        with _client.messages.stream(**kwargs) as streamed:
            response = streamed.get_final_message()
    else:
        response = _client.messages.create(**kwargs)

    latency_s = time.monotonic() - t0

    # Fail loud on output we cannot use, rather than caching/parsing truncated
    # or empty text and surfacing an opaque error far from the cause.
    _raise_on_bad_stop(response, max_tokens)

    # Extract text from all text-type content blocks
    text = "".join(block.text for block in response.content if block.type == "text")

    # Serialise usage (only the fields we care about)
    usage: dict[str, Any] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
    }

    # Serialise the raw response to a plain dict for caching/logging
    raw: dict[str, Any] = json.loads(response.model_dump_json())

    # Structured output
    parsed: Any = None
    if schema is not None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            rid = getattr(response, "_request_id", None)
            raise LLMError(
                f"structured-output response was not valid JSON ({exc}); "
                f"model={response.model} request_id={rid}"
            ) from exc

    result = LLMResult(
        text=text,
        raw=raw,
        usage=usage,
        model=response.model,
        prompt_hash=prompt_hash,
        cache_hit=False,
        parsed=parsed,
    )

    _save_cache(result)
    _append_log(
        timestamp=timestamp,
        model=model,
        prompt_hash=prompt_hash,
        cache_hit=False,
        usage=usage,
        latency_s=latency_s,
    )

    return result
