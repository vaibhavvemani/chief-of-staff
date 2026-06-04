"""
Learning script (b): grounding — answer ONLY from a pasted source.
[Phase 0 §7.2 — THROWAWAY]

Purpose: the seed of grounding. We paste a small source document into the
prompt and instruct the model to answer ONLY from it — and to say it doesn't
know when the answer isn't there. We ask two questions to SEE the difference:
  1. answerable from the source  -> it answers
  2. NOT in the source           -> it refuses instead of guessing

That refusal is the whole point: it proves the answer came from the source,
not the model's memory. This is the kernel of Phase 1's trust machinery.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python learning_scripts/b_grounding.py

NOT part of the Course Builder skeleton. Delete before Phase 0 closes.
"""

from __future__ import annotations

import os
import sys

import anthropic

MODEL = "claude-opus-4-8"  # swap to a cheaper model for learning if you like

SOURCE = """\
ACME Bank — Internal Risk Note (fictional, for this exercise)

ACME Bank sets its firm-wide Value-at-Risk (VaR) limit at $40 million over a
one-day horizon at the 99% confidence level. The limit was last revised in
March 2026. Breaches must be reported to the Chief Risk Officer within 24 hours.
"""

# The grounding contract lives in the system prompt.
SYSTEM = (
    "Answer the user's question using ONLY the SOURCE below. "
    "If the answer is not stated in the SOURCE, reply exactly: "
    '"Not stated in the source." Do not use any outside knowledge.\n\n'
    f"SOURCE:\n{SOURCE}"
)

QUESTIONS = [
    "What is ACME Bank's one-day VaR limit, and at what confidence level?",  # in source
    "What is ACME Bank's total annual revenue?",                             # NOT in source
]


def ask(client: anthropic.Anthropic, question: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY in your environment first.")

    client = anthropic.Anthropic()
    for q in QUESTIONS:
        print(f"Q: {q}")
        print(f"A: {ask(client, q)}\n")


if __name__ == "__main__":
    main()
