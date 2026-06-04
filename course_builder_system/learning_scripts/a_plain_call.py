"""
Learning script (a): one plain model call.  [Phase 0 §7.2 — THROWAWAY]

Purpose: see the bare request/response shape of the Anthropic Messages API.
This is the simplest possible call — no tools, no grounding, no streaming.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python learning_scripts/a_plain_call.py

NOT part of the Course Builder skeleton. Delete before Phase 0 closes.
"""

from __future__ import annotations

import os
import sys

import anthropic

# Swap to "claude-haiku-4-5" or "claude-sonnet-4-6" for cheaper learning runs.
MODEL = "claude-opus-4-8"


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY in your environment first.")

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    # THE REQUEST: a model, a token ceiling, and a list of messages.
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {"role": "user", "content": "In two sentences, what is financial risk?"}
        ],
    )

    # THE RESPONSE: `content` is a LIST of blocks; print the text ones.
    print("=== response.content (list of blocks) ===")
    for block in response.content:
        if block.type == "text":
            print(block.text)

    # The envelope around the content — worth learning to recognize.
    print("\n=== response metadata ===")
    print("model      :", response.model)
    print("stop_reason:", response.stop_reason)   # 'end_turn' = finished naturally
    print("usage      :", response.usage)         # input / output token counts


if __name__ == "__main__":
    main()
