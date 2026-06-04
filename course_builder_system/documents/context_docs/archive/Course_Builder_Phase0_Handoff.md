# Course Builder — Phase 0 Handoff & Build Context

> **Archive note:** Phase 0 has been completed. This file is retained as historical implementation context for the artifact schemas, orchestrator, approval loop, and the decisions behind them. The active project state now lives in `Course_Builder_Master_Context.md`; create a Phase 1 handoff/design doc before replacing the Student Content stub with a real agent.

> **Purpose.** A historical reference for how Phase 0 was designed and completed. It carries the locked artifact schemas, orchestrator architecture, approval-loop design, and rationale that may still be useful when maintaining the skeleton or designing later phases.
>
> **Relationship to other docs.** The project's `Course_Builder_Master_Context.md` is now the active source of truth for current state and next steps. This archived file should be used only for Phase 0 rationale and implementation history.

---

## 0. How to use this archived document

- Read §4–§5 if you need the Phase 0 schema and orchestrator rationale.
- Do not use §7 as active work guidance; Phase 0 has already been completed.
- **Do not re-litigate locked decisions (§6 + §8).** If a request seems to contradict one, flag it rather than drift. Push back when warranted; don't add scope without justification.
- **Team:** two engineers, both new to agentic AI. Calibrate accordingly — concrete, simplest-thing-that-works.

---

## 1. Project context in brief

The long-term goal is a **Chief of Staff**: a system that automates a company's work one process at a time, under human direction — *you direct it; it does the heavy lifting; it returns at the decision points that matter.* We are **not** building all of that now.

**Course-building is the first process being automated, as a proof-of-concept.** It's a real, self-contained workflow the team already does manually, with an inspectable output (a finished course), and it exercises the patterns the general system needs (build domain understanding, generate trustworthy content, insert human approval).

**The Course Builder, in one line:** an agent that builds a complete course largely on its own — researching, structuring, generating learner + teacher material, packaging for an LMS — while one person directs and approves at the checkpoints that matter. Goal: ~10× faster by shifting the person from *producing* to *directing and approving*.

**The four-step flow** (each step's output feeds the next; each ends at a human checkpoint):

```
1. STRUCTURE  →  2. BLUEPRINT  →  3. STUDENT CONTENT  →  4. LESSON PLAN
```

| Step | Produces | In short |
|---|---|---|
| 1 Structure | Domain Model + TOC | Understand the subject; build the domain model; produce modules/subtopics in a teaching order |
| 2 Blueprint | Operational metadata | Hours, slide volume, speaker placement, dependency map. Team-facing, never seen by a learner |
| 3 Student Content | Learner material (+ packaging) | Generate objectives, reading, slides, cases, assessments — grounded, verified; then package for the LMS. The heaviest step |
| 4 Lesson Plan | Teacher material | Map full material vs live time; live-vs-self-study split; per-class plans + talking points |

**The deliverable** is a single organized folder per course: Student Content (LMS-packaged), Teacher Content, Metadata (TOC + Blueprint), and the Domain Model document.

---

## 2. What Phase 0 is — and the one principle that governs it

**Phase 0 = Foundations & Walking Skeleton.** Prove the whole pipeline runs end to end, with **every step faked**, and define the data contracts everything else depends on.

> **THE CRITICAL PRINCIPLE: Phase 0 stays dumb on purpose.** The steps are **stubs** returning hardcoded artifacts — **no real research, no content generation, no LLM calls inside the skeleton steps.** Real intelligence is Phase 1+. Keeping the skeleton stub-only is what lets us debug *plumbing* separately from *agent quality*. Mixing them is the classic way this phase goes sideways.

Phase 0 has three deliverables:
1. **The artifact schemas** — the JSON shape of all five artifacts (the real work).
2. **The orchestrator + approval loop** — the skeleton that runs steps in order, saves artifacts, and pauses for approval.
3. **Three throwaway learning scripts** — to learn the model-SDK primitives, then delete.

---

## 3. Phase 0 status at a glance

| Deliverable | Status | Where |
|---|---|---|
| #1 Artifact schemas (all five, v0.1) | **DONE & validated** | §4, Appendix B |
| #2 Orchestrator + approval loop | **DONE & tested** | §5, Appendix A |
| Wiring: stubs emit the *real* shapes | **TODO (immediate next)** | §7.1 |
| #3 Three throwaway learning scripts | **TODO** | §7.2 |

**Phase 0 is done when:** one command (`python run.py`) produces a complete course folder, pausing for approval between each step, and "needs changes" re-runs **only** that step. (The skeleton already does this with placeholder bodies; §7.1 swaps in the real shapes.)

---

## 4. The locked artifact schemas (v0.1)

We design the **`body`** of each artifact. Every body is wrapped by a fixed metadata **envelope** the orchestrator owns.

### 4.1 The metadata envelope (fixed, owned by the orchestrator)

```json
{
  "course_id": "frm",
  "artifact_type": "toc",
  "produced_by_step": "structure",
  "schema_version": "0.1",
  "status": "draft",            // draft -> approved (set by orchestrator at the checkpoint)
  "revision": 0,                // bumped by orchestrator each re-run of the step
  "revision_note": null,        // the feedback that triggered a re-run
  "inputs": ["brief"],          // which artifact_types this step consumed
  "updated_at": "2026-06-03T00:00:00+00:00",
  "body": { /* artifact-specific; OPAQUE to the engine */ }
}
```

The engine reads only the envelope; `body` is opaque to it. This is why schema changes never touch the orchestrator.

### 4.2 The ID convention (the keystone decision)

The source Excel files have **no IDs** — hierarchy was encoded by `01. Title` + space-indentation, inconsistently. We therefore **impose** IDs:

- **`id`** — a stable handle, assigned once, **never renumbered** (`m1`, `m1_s1`, `c1`, `g1`, …).
- **`order`** — integer sequence within the parent; this is what changes on reorder.
- The human-facing **"1.1"** is **derived** (`module.order` . `subtopic.order`), so there's one source of truth and no drift.

**The principle that falls out of it:** **the TOC is the single source of truth for structure.** Every other artifact **references** TOC IDs and **never re-encodes** the module/subtopic tree. (This is the direct antidote to the spec-vs-practice drift the manual files showed.)

### 4.3 TOC — `body`

```json
{
  "subject": "Financial Risk Management",
  "modules": [
    {
      "id": "m1",
      "order": 1,
      "title": "Foundations of Financial Risk",
      "subtopics": [
        {"id": "m1_s1", "order": 1, "title": "Nature of Financial Risk", "summary": "What financial risk is and how it arises."},
        {"id": "m1_s2", "order": 2, "title": "Risk Classification Framework"},
        {"id": "m1_s3", "order": 3, "title": "Risk Management Process"},
        {"id": "m1_s4", "order": 4, "title": "Risk Appetite & Capacity"},
        {"id": "m1_s5", "order": 5, "title": "Evolution of Modern Risk Management"},
        {"id": "m1_s6", "order": 6, "title": "Institutional Risk Governance"}
      ]
    }
    // modules m2 … m10 follow the same shape
  ]
}
```
- `subtopics[].summary` is **optional** — the one-line "what's taught here" (resolves where the manual "content overview" lives; handy at the Step 1 checkpoint).
- FRM has 10 modules (Module 1 fully shown above is real data).

### 4.4 Domain Model — `body`

The conceptual heart: *comprehension of the subject*, not a pile of links. Reads as a document (prose lives in `overview` and every `summary`).

```json
{
  "subject": "Financial Risk Management",
  "overview": "Financial Risk Management is the discipline of identifying, measuring, and controlling losses from market movements, counterparty default, funding shortfalls, and operational failure...",
  "concepts": [
    {"id": "c1", "name": "Financial Risk", "summary": "The possibility of loss from market, credit, liquidity, or operational exposure.", "depends_on": []},
    {"id": "c2", "name": "Risk vs Uncertainty", "summary": "Knight's distinction: risk is measurable; uncertainty is not.", "depends_on": ["c1"]},
    {"id": "c3", "name": "Value at Risk (VaR)", "summary": "A quantile measure of maximum expected loss over a horizon.", "depends_on": ["c1"]}
  ],
  "grounding_sources": [
    {"category": "GLOBAL FRAMEWORKS", "items": [
      {"id": "g1", "name": "Basel III framework (BIS)", "url": "https://www.bis.org/bcbs/basel3.htm"},
      {"id": "g2", "name": "Basel II framework (BIS)", "url": "https://www.bis.org/publ/bcbs128.htm"}
    ]}
  ]
}
```
- `concepts[].depends_on` references other concept IDs — the dependency graph captures learning order.
- `grounding_sources` mirrors the manual `Tools & Regulations` sheet (CAPS category → items with verified URLs). Each item has a stable `id` so a Content Package asset's `sources` can point back to it (attribution).
- `concepts` are intentionally **independent of the TOC** for the POC (no hard link). A `covers: [concept_ids]` link on TOC subtopics is a **deferred** option (would power gap analysis); not now.
- **`real_world_anchors` was considered and DEFERRED** (cases/people/companies). Consequence: landmark cases and notable people are sourced/generated at Step 3, and speaker candidates come from Step 2 research, rather than being pre-curated here. Revisit as a later feature.

### 4.5 Blueprint — `body`

Operational plan; team-facing metadata, never seen by a learner.

```json
{
  "allocations": [
    {"node_id": "m1",    "hours": 2.5, "slides": 49},
    {"node_id": "m1_s1", "hours": 0.5, "slides": 9},
    {"node_id": "m2",    "hours": 3.0, "slides": 55}
  ],
  "dependencies": [
    {"module_id": "m1", "prerequisites": []},
    {"module_id": "m2", "prerequisites": ["m1"]}
  ],
  "speakers": [
    {"id": "sp1", "placed_at": "m1", "topic": "Institutional Risk Governance",
     "suggested_expert": "<expert from Step 2 research>", "source": "research", "status": "proposed"}
  ]
}
```
- `allocations[].node_id` references **any** TOC node — module vs subtopic is **inferred from the ID** (`m1` vs `m1_s1`), so no extra `level` field. (Module 1's `2.5h / 49 slides` is real data.)
- `dependencies` = the explicit prerequisite map the manual process never had (module-level to start).
- `speakers` = guest-expert placement; candidate names come from Step 2 research (`source: research`).

### 4.6 Content Package — `body`

The heaviest artifact. Keyed by subtopic ID; **no re-nesting** of the tree.

```json
{
  "asset_vocabulary": [
    "learning_objectives", "course_content", "summary", "case_study",
    "important_person", "did_you_know", "assessment", "activities", "resources"
  ],
  "subtopics": [
    {
      "subtopic_id": "m1_s1",
      "assets": [
        {
          "id": "m1_s1_lo", "type": "learning_objectives", "title": "Learning Objectives",
          "format": "docx", "content": "Understand the concept of financial risk...",
          "sources": [], "file": null, "status": "done"
        },
        {
          "id": "m1_s1_case", "type": "case_study", "title": "The Lehman Brothers Collapse",
          "format": "pptx", "content": "Lehman Brothers Collapse (2008) as a multi-risk case...",
          "sources": ["g1"], "file": null, "status": "done"
        },
        {
          "id": "m1_s1_assess", "type": "assessment", "title": "Self-Assessment: Nature of Financial Risk",
          "format": "docx", "content": "Q1. Define financial risk and give two examples...",
          "solution": "Q1. Financial risk is the possibility of loss from market, credit, liquidity, or operational exposure...",
          "sources": [], "file": null, "status": "done"
        }
      ]
    }
  ]
}
```
**Design rules baked in:**
- **Assets are a typed list**, not fixed columns, with allowed types in a configurable **`asset_vocabulary`** (the manual asset set drifts, and a subtopic may carry several case-lets — "20–50% extra").
- **`content` holds the generated material; `file` stays `null` until packaging.** The Content Package holds *content*, not finished files. Rendering to `.pptx`/`.docx` + LMS packaging is the **tail of Step 3, built in Phase 5** (low-risk mechanical transform; depends on finished content).
- **`sources`** references Domain Model grounding-source IDs (e.g. `["g1"]`) — the attribution half of the trust mechanism. Empty until Phase 1 wires it.
- **`solution`** (on assessment assets only) is the teacher-only answer key, generated alongside the question. Packaging routes it to Teacher Content and excludes it from the Student deliverable.

### 4.7 Lesson Plan — `body`

Teacher-facing; organized by **session** (a class), because a teacher plans by class and one class may span several subtopics.

```json
{
  "sessions": [
    {
      "id": "sess1", "order": 1, "title": "Foundations of Financial Risk", "duration_hours": 2.5,
      "covers": [
        {"subtopic_id": "m1_s1", "mode": "live",       "talking_points": ["Open with the Lehman collapse as a hook", "Draw the risk-vs-uncertainty distinction"]},
        {"subtopic_id": "m1_s2", "mode": "live",       "talking_points": ["Walk through the risk classification framework"]},
        {"subtopic_id": "m1_s3", "mode": "self_study", "talking_points": []}
      ]
    }
  ]
}
```
- `covers[].subtopic_id` references TOC subtopics; `mode` is `live` | `self_study` (the core Step 4 decision); `talking_points` are teacher-facing, distinct from learner reading.

### 4.8 The reference graph (verified — no dangling references)

```
Domain Model ── concepts depend_on concepts (internal graph)
     │            grounding_sources have ids  ◄── attribution targets (Content Package .sources)
     ▼
   TOC ◄────────── single source of truth for structure (module/subtopic IDs)
     ▲   ▲   ▲
     │   │   └── Lesson Plan:      sessions.covers[].subtopic_id  -> TOC subtopics
     │   └────── Blueprint:        allocations[].node_id          -> TOC modules/subtopics
     │           Blueprint:        dependencies[].module_id       -> TOC modules
     └────────── Content Package:  subtopics[].subtopic_id        -> TOC subtopics
```

---

## 5. The orchestrator architecture (DONE — code in Appendix A)

Three files, split along the team's "bones vs intelligence" line:

| File | Role | Owner | Changes in Phase 1+? |
|---|---|---|---|
| `orchestrator.py` | the engine: envelope, storage, approval loop | Person A | **No** — depends only on the envelope |
| `steps.py` | the four step stubs | Person B | **Yes** — each stub becomes a real agent |
| `run.py` | wires the pipeline (a list of `Step`s) and runs it | shared | minimal |

**Core contracts already implemented and tested:**

- **A step is a pure function:** `run(inputs, feedback) -> {artifact_type: artifact}`. `inputs` is `{artifact_type: artifact}`. Everything it needs arrives as arguments; everything it makes is returned. This is what makes a step runnable in isolation.
- **A step may produce several artifacts.** Step 1 (`structure`) produces **both** `domain_model` and `toc`. So a step returns a dict, and `Step` declares `consumes` and `produces` as lists.
- **The pipeline is data:** an ordered `list[Step]`, each with `name`, `consumes`, `produces`, `run`. Wiring (from `run.py`):
  - `structure`: consumes `[brief]` → produces `[domain_model, toc]`
  - `blueprint`: consumes `[toc, domain_model]` → produces `[blueprint]`
  - `student_content`: consumes `[blueprint, domain_model]` → produces `[content_package]`
  - `lesson_plan`: consumes `[content_package, blueprint]` → produces `[lesson_plan]`
- **The brief is a seed artifact.** The human's intent (subject, audience, level, goals, scope) is wrapped in the same envelope (`produced_by_step: "human"`), saved pre-approved, and consumed by Step 1.
- **Storage:** plain JSON, one folder per course — `courses/<course_id>/<artifact_type>.json`. No database.
- **The approval loop:** after a step runs, its artifacts are saved as `draft` and shown; the `approver` returns approve or request-changes.
  - **Approve** → artifacts flip to `approved`; advance.
  - **Request-changes** → the loop re-runs **only this step** with the feedback (same inputs, since earlier artifacts are fixed). `revision` bumps; `revision_note` records the feedback. Because the loop lives *inside* one step, a rejection can't disturb earlier steps.
- **The orchestrator owns the lifecycle fields** (`status`, `revision`, `revision_note`), not the steps.
- **Resumability:** on restart, a step whose outputs are already `approved` on disk is **skipped**. (To force a redo, delete that step's `.json` files.)
- **Injectable approver:** `run_pipeline(..., approver=...)` defaults to a console prompt; pass a custom one for non-interactive runs (this is the seam a Phase 1 eval harness and a Phase 6 UI plug into — no engine change).

**Proven in Phase 0 testing:**
1. Full pipeline produces a complete folder (all artifacts present).
2. Request-changes on one step re-runs **only** that step (it goes to `revision 1`; all others stay `revision 0`).
3. An approved step is skipped on restart (resume works).

---

## 6. Stack defaults & hard constraints

| Concern | Default |
|---|---|
| Language | Python |
| Model access | Call the model SDK **directly**. **No agent framework** (LangChain/CrewAI/etc.) yet |
| State & storage | Plain files on disk: one folder per course, artifacts as JSON. **No database** |
| Approval | Console prompt for now (injectable; nicer UI is Phase 6) |
| Grounding | (Phase 1) paste sources into the prompt; **no RAG/vector store** until source volume forces it |

**Do NOT do in Phase 0:** real research, real content generation, any LLM call inside a skeleton step, a framework, a database, a vector store, or any UI beyond the console.

---

## 7. What's left to finish Phase 0

### 7.1 Immediate: wire the stubs to emit the real shapes

`steps.py` currently returns **placeholder** bodies (`<module 1>`, `C1`, …). Replace each stub's `body=` with the **real locked shape** from §4, using the FRM `*.frm.example.json` files as the hardcoded return values. **Keep them hardcoded — still no LLM, no generation.** The orchestrator does not change.

Concretely:
- `structure_step` → return `domain_model` (§4.4) + `toc` (§4.3) bodies.
- `blueprint_step` → return `blueprint` (§4.5), with `allocations`/`dependencies` referencing the TOC IDs it received in `inputs`.
- `student_content_step` → return `content_package` (§4.6), keyed by the TOC subtopic IDs.
- `lesson_plan_step` → return `lesson_plan` (§4.7), `covers` referencing TOC subtopic IDs.

**Done when:** `python run.py` produces a `courses/<id>/` folder of **real-shaped** artifacts, still pausing for approval, and request-changes still re-runs only that step. Recommended: add a tiny referential-integrity check (every Content Package / Blueprint / Lesson Plan reference resolves to a TOC ID) — it's a cheap guard that the contracts hold.

### 7.2 The three throwaway learning scripts (independent)

A separate sandbox to learn the model-SDK primitives — **not part of the skeleton; delete after.**
- (a) one plain model call — see the request/response shape;
- (b) a call where you paste a source document in and force the model to answer **only** from it — the seed of grounding;
- (c) a call where you define one simple tool and watch the model choose to call it — the agent loop.

### 7.3 Then: Phase 0 is complete → Phase 1

Phase 1 makes Student Content **real on ONE subtopic**: build the trust machinery (grounding + separate verification + attribution), measured against the human-made FRM version of that subtopic. That's where the `sources`/`file` slots and the first real LLM calls come in. (See the Master Context / Implementation Roadmap for Phase 1+ detail.)

---

## 8. Decisions locked — do not re-litigate

| Decision | What was settled |
|---|---|
| Phase 0 stays dumb | Stubs only; no LLM/research/generation in skeleton steps |
| Five artifacts | TOC, Domain Model, Blueprint, Content Package, Lesson Plan — bodies locked at v0.1 (§4) |
| Metadata envelope | Fixed; orchestrator-owned; `body` opaque to the engine (§4.1) |
| ID convention | Stable `id` + `order`; "1.1" derived; never renumber IDs (§4.2) |
| TOC owns structure | Other artifacts reference TOC IDs; never re-encode the tree (§4.2) |
| Step is a function | `(inputs, feedback) -> {type: artifact}`; a step may produce several artifacts |
| Approval is on content | Step 3 checkpoint reviews readable content **before** packaging; packaging (Phase 5) renders files after |
| `real_world_anchors` deferred | Not in the Domain Model for now; revisit later (§4.4) |
| Answer keys | Teacher-only `solution` field on the assessment asset, generated with the question (§4.6) |
| No framework / DB / vector store / UI in Phase 0 | Direct SDK calls; files on disk; console approval (§6) |

---

## Appendix A — current code (as built & tested)

### `orchestrator.py`

```python
"""
Course Builder - Phase 0 orchestrator (the walking skeleton).

This is the ENGINE. It knows nothing about what a Domain Model or a TOC
actually contains. It treats every artifact as an opaque JSON *body* wrapped in
a small, fixed metadata *envelope*. Its only jobs are:

  1. run the steps in order,
  2. feed each step the artifacts it consumes,
  3. save what each step produces into a per-course folder,
  4. pause after each step for human approve / request-changes,
  5. on "request-changes", re-run ONLY that step with the feedback.

Because it depends only on the envelope (never the body), the real schema work
you do next will not require changing a single line of this file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

SCHEMA_VERSION = "0.1"
COURSES_DIR = Path("courses")


def make_artifact(
    course_id: str,
    artifact_type: str,
    produced_by_step: str,
    body: dict,
    inputs: list[str],
) -> dict:
    """Wrap a step's output body in the fixed metadata envelope.

    The lifecycle fields (status, revision, revision_note, updated_at) are
    owned by the orchestrator, not the step - they are set/overwritten when
    the artifact is saved. A step just declares identity + body + what it read.
    """
    return {
        "course_id": course_id,
        "artifact_type": artifact_type,
        "produced_by_step": produced_by_step,
        "schema_version": SCHEMA_VERSION,
        "status": "draft",          # draft -> approved (set by orchestrator)
        "revision": 0,              # bumped by orchestrator on re-run
        "revision_note": None,      # the feedback that triggered the re-run
        "inputs": inputs,           # which artifact_types this consumed
        "updated_at": _now(),
        "body": body,               # OPAQUE to the engine
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Step:
    name: str                                  # e.g. "structure"
    consumes: list[str]                         # artifact_types it reads
    produces: list[str]                         # artifact_types it writes
    run: Callable[[dict, Optional[str]], dict]
    # run(inputs, feedback) -> {artifact_type: artifact_envelope}
    # inputs is {artifact_type: artifact_envelope}


@dataclass
class Decision:
    approved: bool
    feedback: Optional[str] = None


def course_dir(course_id: str) -> Path:
    return COURSES_DIR / course_id


def artifact_path(course_id: str, artifact_type: str) -> Path:
    return course_dir(course_id) / f"{artifact_type}.json"


def save_artifact(artifact: dict) -> Path:
    path = artifact_path(artifact["course_id"], artifact["artifact_type"])
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact["updated_at"] = _now()
    path.write_text(json.dumps(artifact, indent=2))
    return path


def load_artifact(course_id: str, artifact_type: str) -> Optional[dict]:
    path = artifact_path(course_id, artifact_type)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def console_approver(step_name: str, produced: dict) -> Decision:
    print(f"\n=== Step '{step_name}' produced: {', '.join(produced)} ===")
    for atype, art in produced.items():
        print(f"\n--- {atype}  (revision {art['revision']}) ---")
        print(json.dumps(art["body"], indent=2))
    while True:
        choice = input(f"\n[{step_name}] (a)pprove / (c)hanges / (q)uit > ").strip().lower()
        if choice in ("a", "approve"):
            return Decision(approved=True)
        if choice in ("c", "changes"):
            fb = input("  what should change? > ").strip()
            return Decision(approved=False, feedback=fb)
        if choice in ("q", "quit"):
            raise KeyboardInterrupt
        print("  please type: a, c, or q")


def run_pipeline(
    course_id: str,
    pipeline: list[Step],
    seed_artifacts: dict,
    approver: Callable[[str, dict], Decision] = console_approver,
) -> None:
    """Run the steps in order, pausing for approval after each.

    seed_artifacts: artifacts the human supplies up front (e.g. the brief).
                    Saved pre-approved so Step 1 can consume them.
    """
    for art in seed_artifacts.values():
        art["status"] = "approved"
        save_artifact(art)

    for step in pipeline:
        # resume: skip a step whose outputs are already approved on disk.
        existing = [load_artifact(course_id, t) for t in step.produces]
        if existing and all(a and a["status"] == "approved" for a in existing):
            print(f"[skip]  '{step.name}' already approved - resuming past it")
            continue

        # gather inputs this step consumes
        inputs = {}
        for t in step.consumes:
            art = load_artifact(course_id, t)
            if art is None:
                raise RuntimeError(
                    f"step '{step.name}' needs '{t}', but it is not on disk"
                )
            inputs[t] = art

        # run / approve loop: re-runs ONLY this step until approved
        feedback: Optional[str] = None
        revision = 0
        while True:
            produced = step.run(inputs, feedback)

            for art in produced.values():
                art["revision"] = revision
                art["revision_note"] = feedback
                art["status"] = "draft"
                save_artifact(art)

            decision = approver(step.name, produced)
            if decision.approved:
                for art in produced.values():
                    art["status"] = "approved"
                    save_artifact(art)
                print(f"[ok]    '{step.name}' approved")
                break

            feedback = decision.feedback
            revision += 1
            print(f"[redo]  re-running ONLY '{step.name}' (revision {revision})")

    print(f"\nDone. Course folder: {course_dir(course_id)}/")
```

### `steps.py` (CURRENT — placeholder bodies; §7.1 swaps these for the real shapes)

```python
"""
Course Builder - Phase 0 step STUBS. (Person B's territory.)

Every step here returns hardcoded placeholder JSON. There are NO LLM calls,
no research, no content generation. Phase 0 stays dumb so we can debug the
plumbing separately from agent quality.

Phase 1+ replaces each function below with a real agent. The orchestrator
never changes - it only ever sees the envelope, never the body shapes here.

Step 1 (Structure) produces TWO artifacts (domain_model AND toc), so a step
returns a {type: artifact} dict, not a single artifact.

NOTE: the bodies below are PLACEHOLDERS. The real locked shapes are in the
Phase 0 handoff §4 and the *.frm.example.json files. §7.1 is to replace these
placeholder bodies with those real shapes (still hardcoded - no LLM yet).
"""

from __future__ import annotations

from typing import Optional

from orchestrator import make_artifact


def structure_step(inputs: dict, feedback: Optional[str]) -> dict:
    """subject brief -> Domain Model + TOC."""
    brief = inputs["brief"]["body"]
    course_id = inputs["brief"]["course_id"]

    domain_model = make_artifact(
        course_id, "domain_model", "structure",
        body={
            "_placeholder": True,
            "subject": brief.get("subject"),
            "concepts": [
                {"id": "C1", "name": "<concept 1>", "depends_on": []},
                {"id": "C2", "name": "<concept 2>", "depends_on": ["C1"]},
            ],
            "note": "STUB. Real shape comes from the reference-course schema work.",
        },
        inputs=["brief"],
    )
    toc = make_artifact(
        course_id, "toc", "structure",
        body={
            "_placeholder": True,
            "modules": [
                {"id": "M1", "title": "<module 1>", "subtopics": [
                    {"id": "M1.1", "title": "<subtopic 1.1>"},
                    {"id": "M1.2", "title": "<subtopic 1.2>"},
                ]},
                {"id": "M2", "title": "<module 2>", "subtopics": [
                    {"id": "M2.1", "title": "<subtopic 2.1>"},
                ]},
            ],
            "note": "STUB.",
        },
        inputs=["brief"],
    )
    return {"domain_model": domain_model, "toc": toc}


def blueprint_step(inputs: dict, feedback: Optional[str]) -> dict:
    """TOC + Domain Model -> Blueprint (operational plan)."""
    toc = inputs["toc"]["body"]
    course_id = inputs["toc"]["course_id"]

    allocations = [
        {"module_id": m["id"], "hours": 2, "slides": 20, "prerequisites": []}
        for m in toc.get("modules", [])
    ]
    blueprint = make_artifact(
        course_id, "blueprint", "blueprint",
        body={
            "_placeholder": True,
            "allocations": allocations,
            "speakers": [],
            "note": "STUB.",
        },
        inputs=["toc", "domain_model"],
    )
    return {"blueprint": blueprint}


def student_content_step(inputs: dict, feedback: Optional[str]) -> dict:
    """Blueprint + Domain Model -> Content Package (learner material)."""
    bp = inputs["blueprint"]["body"]
    course_id = inputs["blueprint"]["course_id"]

    modules = [
        {
            "module_id": alloc["module_id"],
            "objectives": ["<objective>"],
            "reading": "<reading material placeholder>",
            "assessment": ["<question>"],
        }
        for alloc in bp.get("allocations", [])
    ]
    content = make_artifact(
        course_id, "content_package", "student_content",
        body={"_placeholder": True, "modules": modules, "note": "STUB."},
        inputs=["blueprint", "domain_model"],
    )
    return {"content_package": content}


def lesson_plan_step(inputs: dict, feedback: Optional[str]) -> dict:
    """Content Package + Blueprint -> Lesson Plan (teacher material)."""
    content = inputs["content_package"]["body"]
    course_id = inputs["content_package"]["course_id"]

    sessions = [
        {
            "module_id": m["module_id"],
            "live": ["<taught live>"],
            "self_study": ["<left to self-study>"],
            "talking_points": ["<talking point>"],
        }
        for m in content.get("modules", [])
    ]
    plan = make_artifact(
        course_id, "lesson_plan", "lesson_plan",
        body={"_placeholder": True, "sessions": sessions, "note": "STUB."},
        inputs=["content_package", "blueprint"],
    )
    return {"lesson_plan": plan}
```

### `run.py`

```python
"""
Course Builder - Phase 0 entry point.

Run with:   python run.py

Produces a complete placeholder course folder under courses/<course_id>/,
pausing for your approval after each step.
"""

from __future__ import annotations

import steps
from orchestrator import Step, make_artifact, run_pipeline, console_approver


def build_pipeline() -> list[Step]:
    return [
        Step(name="structure",       consumes=["brief"],                    produces=["domain_model", "toc"], run=steps.structure_step),
        Step(name="blueprint",       consumes=["toc", "domain_model"],      produces=["blueprint"],           run=steps.blueprint_step),
        Step(name="student_content", consumes=["blueprint", "domain_model"], produces=["content_package"],    run=steps.student_content_step),
        Step(name="lesson_plan",     consumes=["content_package", "blueprint"], produces=["lesson_plan"],     run=steps.lesson_plan_step),
    ]


def main() -> None:
    course_id = "frm-demo"
    brief = make_artifact(
        course_id, artifact_type="brief", produced_by_step="human",
        body={
            "subject": "Financial Risk Management",
            "audience": "PG",
            "level": "intermediate",
            "goals": "<what the course should achieve>",
            "scope": "<in / out of scope>",
        },
        inputs=[],
    )
    run_pipeline(course_id=course_id, pipeline=build_pipeline(),
                 seed_artifacts={"brief": brief}, approver=console_approver)


if __name__ == "__main__":
    main()
```

---

## Appendix B — worked FRM examples

The full, validated example artifacts live in these files (bring them into the workspace):
`toc.frm.example.json`, `domain_model.frm.example.json`, `blueprint.frm.example.json`, `content_package.frm.example.json`, `lesson_plan.frm.example.json`. They are the concrete shapes §7.1 hardcodes into `steps.py`, and the quality yardstick the real agents (Phase 1+) are measured against. FRM is the most complete manual course (planned → benchmarked → produced), which is why it's the reference.

---

*Living document. Update when a locked decision changes or a phase completes. A stale handoff is worse than none.*
