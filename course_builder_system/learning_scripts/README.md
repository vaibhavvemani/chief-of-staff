# Learning scripts (Phase 0 §7.2) — THROWAWAY

A separate sandbox to learn the three model-SDK primitives before Phase 1.
**These are NOT part of the Course Builder skeleton.** They make real LLM API
calls — which the skeleton never does (Phase 0 stays dumb on purpose). Write
them, learn from them, then **delete this whole folder before Phase 0 closes.**

| Script | Primitive it teaches |
|---|---|
| `a_plain_call.py` | One plain model call — the bare request/response shape. |
| `b_grounding.py`  | Paste a source, force the model to answer ONLY from it — the seed of grounding (Phase 1's trust machinery). |
| `c_tool_use.py`   | Define one tool and watch the model choose to call it — the agent loop. |

## Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...     # the scripts read your key from the env
python learning_scripts/a_plain_call.py
python learning_scripts/b_grounding.py
python learning_scripts/c_tool_use.py
```

Each script is self-contained and uses `claude-opus-4-8` by default (swap the
`MODEL` constant for a cheaper model — e.g. `claude-haiku-4-5` — while learning).
**These calls cost money.**

The skeleton itself has **no dependencies** — `anthropic` is needed only for
this throwaway sandbox.
