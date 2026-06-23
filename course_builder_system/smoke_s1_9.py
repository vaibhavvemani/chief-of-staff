"""
smoke_s1_9.py — S1.9 throwaway end-to-end plumbing smoke test.

This is NOT the production generation agent (that is S2.x → agents/student_content.py).
Its only job is to prove the plumbing works end to end:

    domain model (S1.7) + grounding sources (S1.6)
        → prompt assembly
        → llm.call() (S1.8, live Anthropic call)
        → output + token log + prompt-hash cache

Disposable: safe to delete once the run is confirmed. Run from course_builder_system/:
    python3 smoke_s1_9.py
"""

from __future__ import annotations

import json
from pathlib import Path

import llm

DM_PATH = Path("domain/m1_s1_domain_model.json")
OUT_PATH = Path("logs/smoke_s1_9_output.md")  # logs/ is gitignored


def load_dm() -> dict:
    return json.loads(DM_PATH.read_text(encoding="utf-8"))


def load_sources(dm: dict) -> list[tuple[str, str, str]]:
    """Read each registered grounding source's text. Returns [(id, name, text), ...]."""
    out = []
    for cat in dm["body"]["grounding_sources"]:
        for item in cat["items"]:
            text = Path(item["file"]).read_text(encoding="utf-8")
            out.append((item["id"], item["name"], text))
    return out


def build_prompt(dm: dict, sources: list[tuple[str, str, str]]) -> tuple[str, str]:
    body = dm["body"]
    # Inject the whole m1_s1 DM slice: deep subtopic + thin-neighbor awareness + source registry.
    dm_json = json.dumps(body, ensure_ascii=False, indent=2)
    src_blocks = "\n\n".join(f"### [{sid}] {name}\n{text}" for sid, name, text in sources)

    system = (
        "You are generating grounded course content for a Financial Risk Management "
        "course. Use ONLY the supplied Domain Model and grounding source texts — never "
        "outside knowledge. Attribute every significant factual claim to a source id."
    )
    user = (
        "DOMAIN MODEL (m1_s1 slice):\n"
        f"{dm_json}\n\n"
        "GROUNDING SOURCES (use ONLY these; cite source ids inline like [g3]):\n"
        f"{src_blocks}\n\n"
        "TASK: Write a concise (~400-600 word) explainer for the subtopic "
        "'Nature of Financial Risk' (m1_s1). Ground every significant factual claim in "
        "one of the sources above and cite it inline as [gN]. Stay within m1_s1's scope "
        "— do not drift into the thin sibling subtopics (m1_s2..m1_s6)."
    )
    return system, user


def main() -> None:
    dm = load_dm()
    sources = load_sources(dm)
    system, user = build_prompt(dm, sources)

    deep = [s for s in dm["body"]["subtopics"] if s.get("depth") == "deep"]
    concept_n = sum(len(s.get("concepts", [])) for s in deep)
    print(f"[smoke] DM loaded: {concept_n} concepts, {len(sources)} grounding sources")
    print(f"[smoke] prompt chars: system={len(system)} user={len(user)}")

    # use_cache=False → force a real round-trip (the cache still gets written, which
    # is itself part of the plumbing we want to confirm).
    result = llm.call(
        [{"role": "user", "content": user}],
        system=system,
        max_tokens=1500,
        use_cache=False,
    )

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(result.text, encoding="utf-8")

    print(f"[smoke] model={result.model} cache_hit={result.cache_hit} usage={result.usage}")
    print(f"[smoke] output chars={len(result.text)} -> {OUT_PATH}")
    print("\n----- OUTPUT (first 1200 chars) -----\n")
    print(result.text[:1200])


if __name__ == "__main__":
    main()
