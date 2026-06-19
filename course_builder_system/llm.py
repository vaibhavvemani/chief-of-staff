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

# Module-level client — SDK reads ANTHROPIC_API_KEY from the environment.
# max_retries=4 activates the SDK's built-in exponential backoff on 429/5xx.
# We do NOT guard against a missing key here; we guard inside `call()` so that
# importing the module is always safe (useful for tests and non-API callers).
_client = anthropic.Anthropic(max_retries=4)

_CACHE_DIR = Path(".llm_cache")
_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "llm_calls.jsonl"

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
) -> str:
    """SHA-256 over a deterministic JSON serialisation of the full call spec."""
    payload = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        "schema": schema,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


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
        use_cache:  When False, always bypass the local cache and call the API.

    Returns:
        LLMResult with text, raw response dict, usage token counts, and
        (optionally) parsed structured output.

    Raises:
        SystemExit: If ANTHROPIC_API_KEY is unset and an API call is required.
    """
    t0 = time.monotonic()
    timestamp = datetime.now(tz=UTC).isoformat()

    prompt_hash = _canonical_key(model, system, messages, max_tokens, schema)

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

    # Build keyword arguments for messages.create
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system is not None:
        kwargs["system"] = system
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}

    response = _client.messages.create(**kwargs)

    latency_s = time.monotonic() - t0

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
        parsed = json.loads(text)

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
