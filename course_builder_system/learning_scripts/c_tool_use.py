"""
Learning script (c): one tool, and the agent loop.  [Phase 0 §7.2 — THROWAWAY]

Purpose: define ONE simple tool and watch the model CHOOSE to call it, then
feed the result back so it can finish. This is the agent loop in miniature:

    ask -> model returns stop_reason 'tool_use' -> we run the tool ->
    we send the result back -> model returns the final answer.

We use the MANUAL loop (not the SDK's tool_runner) on purpose: the whole point
is to SEE the mechanics, not hide them.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python learning_scripts/c_tool_use.py

NOT part of the Course Builder skeleton. Delete before Phase 0 closes.
"""

from __future__ import annotations

import os
import sys

import anthropic

MODEL = "claude-opus-4-8"  # swap to a cheaper model for learning if you like

# 1) The tool definition the model sees: name, description, input schema.
TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city. Call this whenever "
                       "the user asks about the weather somewhere.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. Paris"}
            },
            "required": ["city"],
        },
    }
]


def get_weather(city: str) -> str:
    """The tool's actual implementation. Canned data — this is a learning stub,
    not real research (the real skeleton never fakes data)."""
    return f"18C and lightly raining in {city}."


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY in your environment first.")

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": "What's the weather in Paris right now?"}]

    # 2) The agent loop: keep going until the model stops asking for tools.
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            # Model is done — print its final text and stop.
            final = "".join(b.text for b in response.content if b.type == "text")
            print("FINAL:", final)
            break

        # 3) The model chose to call a tool. Record its turn, run the tool(s),
        #    then send the results back as a new user turn.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[model called {block.name}({block.input})]")
                result = get_weather(**block.input)  # only one tool here
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,   # must match the tool_use block's id
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    main()
