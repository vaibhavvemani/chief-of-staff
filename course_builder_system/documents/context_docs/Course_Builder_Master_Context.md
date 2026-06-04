# Course Builder — Master Context Document

> **Purpose:** This is the single source of truth for the Course Builder project. It exists so that any AI assistant (or new human collaborator) can read this one document and understand exactly what we are building, why, how it is designed, and how we intend to build it. The project is being built largely with AI assistance, so this document is written to orient an AI quickly and completely.

---

## 0. How to use this document (for AI assistants)

- Read this whole document first. It is self-contained — you should not need any other file to understand the project.
- **Intent wins on vision; detail wins on implementation.** Sections 1–11 define *what* we are building and the decisions already locked. Sections 12–19 define *how* we are building it.
- **Do not re-litigate locked decisions** (Section 10) unless we explicitly reopen one. If a request seems to contradict a locked decision or a core principle, flag it rather than quietly drifting.
- **Push back when warranted.** We prefer direct, rigorous collaboration over agreeable drift. Do not add scope, components, or "nice to haves" without genuine justification. If we are over-engineering, say so.
- We are **two engineers, both new to agentic AI**, building this from zero. Calibrate explanations accordingly: be concrete, define terms, and prefer the simplest thing that works.
- When we say we are working on a specific phase (Section 16), that is where the detailed technical decisions get made. Keep high-level discussion aligned with the phase we are in.

---

## 1. The long-term vision: a Chief of Staff

The end goal is a system we call the **Chief of Staff**: software that automates a company's work **one process at a time**, under human direction. Not a single tool bolted onto one task, and not a giant system built all at once — a general capability that can take over a defined process, run it largely on its own, and then be pointed at the next process.

The guiding image is an actual chief of staff: something you **direct rather than operate**. You give it the goal and the constraints; it does the heavy lifting; it returns to you at the decision points that matter; you approve or redirect. Over time it absorbs more of the company's processes, team by team.

Two principles sit underneath this and must never be lost:

1. **Automate incrementally, not all at once.** One process at a time. Each one we automate teaches us about the next.
2. **The human steers; the system does the work.** The aim is leverage, not the removal of human judgment.

---

## 2. Why course-building first (the POC)

We are **not** building the whole Chief of Staff yet. We chose one real process to automate first, as a proof-of-concept, because building something concrete teaches us how the general system should work far better than theorizing.

Course-building was chosen because it is:

- A **real, self-contained workflow** the team already understands and does manually today.
- An output with a **clear, inspectable result** — a finished course — so success is easy to judge.
- A process that **exercises the patterns the general system will need**: building understanding of a domain, generating trustworthy content, and inserting human approval at the right points.

**The double payoff.** The POC must succeed at two things at once:
1. Be a genuinely useful course builder.
2. Teach us general, reusable lessons (how an agent builds domain understanding, where humans should approve, how to keep generated work trustworthy) that carry over to whatever process we automate next.

If we only get a course builder and learn nothing reusable, the POC underdelivered. The general lessons are captured **in the per-phase design work**, not in the high-level docs.

---

## 3. What the Course Builder is

**In one line:** An agent that builds a complete course largely on its own — researching the subject, structuring it, generating the learner and teacher material, and packaging it for an LMS — while a single person directs it and approves its work at the decision points that matter.

The goal is **not** to remove the human. It is to make course-building **roughly 10× faster** by shifting the person from producing everything by hand to **directing and approving**. The agent does the heavy lifting; the human steers.

---

## 4. What "done" looks like (the deliverable)

When a course is complete, the human receives **a single organized folder** containing all material for that course:

| Folder Section | What it contains |
|---|---|
| **Student Content** | Learner-facing deliverables — learning objectives, reading material, slides, workbooks, case studies, quizzes/assessments — organized by module and subtopic, packaged in an LMS-ready format. |
| **Teacher Content** | What the teacher delivers live — per-class lesson plan, the live-vs-self-study split, talking points, and solution guides. A layer distinct from the student reading material. |
| **Metadata Documents** | The operational reference — the Table of Contents and the Blueprint (hours, slide counts, speaker placement, dependency map). |
| **Domain Model** | The structured knowledge document about the subject that the agent built and used throughout. Ships as a deliverable in its own right — a reusable asset, not just a working file. |

The folder is the deliverable.

---

## 5. The four-step flow

A course is built end to end through **four sequential steps**. Each step's output becomes the next step's input. The Domain Model (Section 6) sits beneath all four and is drawn on throughout. Each step ends at a **human checkpoint** before the next begins.

```
1. STRUCTURE  →  2. BLUEPRINT  →  3. STUDENT CONTENT  →  4. LESSON PLAN
```

### Step 1 — Structure
*Understand the subject and produce the finalized Table of Contents.*
- Takes in the person's intent: subject, target audience, level, goals, scope.
- Builds the **Domain Model** — a structured understanding of the subject's concepts, how they relate, and what depends on what.
- Researches the field, including the **real, current problems** practitioners face — not just textbook theory.
- Analyzes the competitive landscape (what existing courses cover and where they fall short).
- Runs a gap analysis to surface what should be in the course that nobody has flagged.
- Drafts the **Table of Contents** — modules and subtopics in a defensible teaching order.
- **Outputs:** Domain Model (persists onward) + finalized TOC (module list with subtopics and ordering).

### Step 2 — Blueprint
*Turn the structure into a runnable operational plan. Metadata only — a learner never sees this.*
- Allocates time (hours per module and subtopic).
- Plans delivery volume (slides and material per topic).
- Places speakers (where a guest expert fits and on what topic; can use the Domain Model to suggest candidates).
- Makes the **prerequisite/dependency structure explicit** (which modules depend on which).
- **Outputs:** The Course Blueprint — per-module/subtopic hours and slide counts, speaker placement plan, explicit dependency map.

### Step 3 — Student Content
*Generate the learner-facing material, ready for the LMS. The heaviest step, and where trustworthiness matters most.*
- Generates learner deliverables — objectives, reading material, slides, workbooks, case studies, quizzes/assessments.
- **Grounds** content in researched sources and runs a **separate verification pass** over factual claims.
- Ensures reading material is genuinely comprehensive — the full body of knowledge, not a thin summary.
- Packages output in an **LMS-compatible format** so progress tracking works once uploaded.
- **Outputs:** All learner-facing documents + LMS-packaged output.

### Step 4 — Lesson Plan
*Turn the full material into what the teacher delivers live.*
- Maps the full module material against the available live teaching time.
- Decides what is taught live vs left to self-study.
- Produces a **per-class lesson plan** for each session.
- Provides teacher-facing **talking points** (distinct from the learner's reading material, so the teacher isn't reading the textbook aloud).
- **Outputs:** Per-class lesson plan, live-vs-self-study split, teacher talking points per session.

---

## 6. The Domain Model

The Domain Model is the **conceptual heart** of the system.

- **What it is:** a knowledge *document* about the subject — a structured, written understanding of the field. It captures the concepts, how they relate, the order they should be learned in, and the grounding material (regulations, cases, real-world problems). It is **comprehension, not a pile of links**.
- **How it's used:** built primarily in Step 1, but it persists and is reused by every later step (Step 2 uses it to suggest speakers; Step 3 uses it to ground content; Step 4 uses it to judge what matters most for live teaching). It ships in the final folder as a deliverable.
- **Why a document:** a person can read, check, and correct it; it's portable and needs no special infrastructure; it can be handed to any step as context.
- **POC simplification:** for the POC, a step is handed the **whole** Domain Model as context, not a retrieved slice. This avoids building retrieval machinery early. The trade-off is the document must stay within a sane size. Slicing it into retrievable pieces (RAG) is a **later optimization, not a Day-1 requirement**.
- **Generalization to remember (but not over-build):** a structured knowledge document about a domain is useful far beyond course-building — any process the Chief of Staff later automates likely benefits from one. Note it; do not let it bloat the POC.

---

## 7. The human's role (the checkpoint model)

The agent does the heavy lifting and works through a step on its own. At a **checkpoint** it stops, shows what it produced, and asks whether it is good enough or needs changes. The person approves or redirects; only then does the agent move on.

**Motto:** the agent proposes, the human disposes, and nothing significant moves forward without a yes.

| Step | What the human provides | What they approve at the checkpoint |
|---|---|---|
| 1 Structure | Subject, audience, level, goals, scope; any must-have topics/constraints | The TOC and module/subtopic division |
| 2 Blueprint | Delivery constraints: total hours, format, fixed speaker/scheduling needs | Time allocation, slide volume, speaker placement, dependency map |
| 3 Student Content | Target LMS format; any house style or depth preferences | The generated material (light, fast review because it's grounded + verified) before packaging |
| 4 Lesson Plan | Live teaching time available per module/class | The live-vs-self-study split and per-class lesson plan |

**One director per course.** A single person owns and steers one course end to end. The team is larger, but we design for the single-director reality — **not** multi-user collaboration in the POC.

---

## 8. Trustworthiness of generated content

Because the agent produces real teaching material, it must be trustworthy enough that **human review becomes light and fast**. Three mechanisms support this:

1. **Grounding** — generate from researched, verified sources, not model memory alone.
2. **Separate verification** — a distinct checking pass reviews generated content for unsupported claims. *The writer does not check its own work.*
3. **Source attribution** — significant factual claims carry a traceable source, so an unsupported claim is visible rather than hidden.

**Honest limitation:** these mechanisms sharply reduce error but do not eliminate it, and they cannot judge pedagogical quality. The realistic target is **light-and-fast human review, not the removal of human review**. No one should frame this POC as "no human needed."

> **Verification is the product, not a feature.** It is the entire reason review can be light. Under-invest here and the "10× faster" promise quietly dies.

---

## 9. The manual process we're replacing

Today, courses are built through a largely manual **five-stage** process, with most effort carried by one person prompting an LLM by hand, asset by asset:

1. **Subject Selection** — executives decide the subject, considering audience and program level.
2. **Research & TOC** — researchers benchmark 10+ competing programs, then build a complete in-house TOC; tools, regulations, and cases collected from verified sources.
3. **Structure** — the TOC is broken into modules and subtopics, with teaching elements and target counts defined per chapter.
4. **Content Generation** — for each subtopic, learner material is generated with an LLM and tracked to completion. **The heaviest, most repetitive stage.**
5. **Trainer Enablement** — lesson plans, solution guides, and SME review prepared. **The least-developed stage in practice.**

**Subjects built or in progress:** a connected family of risk & governance topics — FRM (Financial Risk Management), ERM (Enterprise Risk Management), CG (Corporate Governance), SRM (Strategic Risk Management).

**Strengths worth preserving:** genuinely comparative research (10+ real programs benchmarked); facts grounded with verified source links; explicit, consistent pedagogical structure with a deliberate 20–50% extra-material buffer; self-contained chapters.

**Known gaps the POC closes:** heavy reliance on one person; slow, repetitive manual prompting; uneven/manual verification; **no LMS packaging**; underdeveloped trainer enablement; drift between the defined asset list and what's actually produced.

---

## 10. Decisions already locked (do not re-litigate)

| Decision | What was settled |
|---|---|
| **It is a Chief of Staff with a pipeline inside it** | The end product automates a company process by process. The course-builder four-step flow is the first process it learns to run — not the whole product. |
| **Course-building is the first POC** | Chosen because it is real, self-contained, understood, and exercises the right general patterns. |
| **Checkpoint model for human control** | Agent runs a step, stops, shows its work, asks for approval. Not continuous-supervision, not fully autonomous. |
| **Domain model is a document, handed whole** | Readable, correctable, portable; given whole to each step for the POC. Retrieval/slicing deferred. Ships in the final folder. |
| **One director per course** | Single-owner-per-project. Not designing for multi-user collaboration in the POC. |
| **The deliverable is an organized folder** | Student content, teacher content, metadata, and the Domain Model — sorted, LMS-ready where applicable. |
| **General lessons live in phase docs** | High-level docs stay course-focused; Chief-of-Staff generalization happens in per-phase design work. |
| **Build order ≠ course order** | We build by contracts and risk, not in the sequence a course is made (see Section 12). |
| **No agent framework at the start** | Direct model SDK calls first. Add a framework later only if a concrete need appears. |

---

## 11. Open questions (to resolve during phasing)

- **Target LMS and packaging format.** Must be known before Step 3 generation; does not affect Steps 1–2. Likely SCORM or xAPI.
- **Phase 1 reference subtopic.** FRM is the most complete reference course and was used for the Phase 0 schemas. Before building the real Student Content agent, choose the exact FRM subtopic and manual assets that will serve as the Phase 1 quality benchmark.
- **Phase 1 review rubric.** "At least as good as the manual version" must become a small rubric before implementation: factual accuracy, coverage, source attribution, pedagogical clarity, asset completeness, house style, and human review time.
- **Citation granularity.** Phase 0 has source IDs at the Domain Model grounding-source level. Phase 1 must decide how precise attribution needs to be for verification — for example source URL, document section, excerpt, or claim-level support — without jumping to RAG prematurely.
- **Cost-vs-depth trade-off.** How thorough — and therefore how slow/expensive — each generation and verification run should be.
- **How each agent is actually built.** All technical implementation is decided per-phase with the Chief-of-Staff vision in view.

---

## 12. Implementation philosophy: build order is not course order

The natural instinct is to build Step 1 first because it's first, then 2, 3, 4. **That is the wrong sequence, and following it is the most common way projects like this stall.** Two ideas replace it:

**Each step is a function.** It takes an input artifact and produces an output artifact:
`subject → Domain Model + TOC → Blueprint → Student Content → Lesson Plan`.
So the **contracts between steps matter more than any single step's cleverness**. If each artifact's shape is well-defined and stable, you can build, test, and swap each step on its own — and hand-author an artifact to test a later step before the earlier one exists. **The real foundation is the data model, not Step 1.**

**Deepen steps in risk order.** Step 3 (Student Content) is the long pole: heaviest, highest-value, and home to the one genuinely uncertain question — *can an agent produce content trustworthy enough that review is light?* Answer that early. The lucky break: finished manual courses let you test Step 3 on real input and measure it against a known-good result, **without having built Steps 1 or 2 first**.

---

## 13. Principles to build by

- **Smallest thing that works, first.** Reach for the simplest version that proves the point, then grow it.
- **No agent frameworks at the start.** Call the model SDK directly. Frameworks (LangChain, CrewAI, etc.) hide the mechanics you most need to learn and make debugging painful. Add one later only if a concrete need appears.
- **Contracts before cleverness.** Lock the artifact shapes before building the agents that fill them.
- **Composition over monolith.** Keep each step a small, bounded agent with a clear contract — not one giant do-everything prompt.
- **Verification is the product, not a feature.** It is the entire reason review can be light.
- **Hand-author inputs to test later steps.** You don't need Step 1 finished to test Step 3 — just a valid input artifact.

---

## 14. Glossary (shared vocabulary)

| Term | Meaning |
|---|---|
| **Agent** | An LLM given a goal, some tools, and a loop — so it takes steps toward the goal instead of answering once. |
| **Tool / tool use** | A function you expose to the model (search, read a file, run code) that it can choose to call. How an agent acts, not just talks. |
| **Artifact / contract** | The defined data shape each step outputs and the next consumes (e.g. the TOC as JSON). Stable contracts let you build and test each step on its own. |
| **Grounding** | Generating from supplied, verified sources rather than the model's memory — so facts are real and traceable. |
| **RAG** | Retrieval-augmented generation: grounding at scale — store sources, fetch the relevant ones at generation time. Don't reach for it until pasting sources into the prompt stops scaling. |
| **Orchestration** | The code that runs the steps in order, passes artifacts between them, saves state, and pauses for approval. |
| **Human-in-the-loop / checkpoint** | A deliberate stop where the person approves or redirects before the agent continues. |
| **Eval** | A repeatable way to measure output quality — here, comparing against the manual courses — so "better" is a fact, not a feeling. |

---

## 15. A sane starting stack

Defaults chosen to minimise moving parts while learning. Change any of them later when you hit a real reason — not before.

| Concern | Default |
|---|---|
| **Language** | Python — most agentic examples and SDKs assume it. (JavaScript works too; pick one and commit.) |
| **Model access** | Call the model SDK directly. No agent framework yet. |
| **State & storage** | Plain files on disk: one folder per course, artifacts as JSON. No database until you feel real pain. |
| **Approval** | A console prompt at first — print the artifact, wait for approve / request-changes. A nicer interface is Phase 6. |
| **Grounding** | Start by pasting sources into the prompt. Move to retrieval / RAG only when source volume forces it. |

---

## 16. The build plan — seven phases

**Build by contracts and risk, not course order.** Each phase replaces one stub with one real agent.

| Phase | Focus | What you prove or get |
|---|---|---|
| **0** | Foundations & walking skeleton | **Complete:** pipeline runs end to end with real-shaped stubs, approvals, resumability, and contract checks |
| **1** | Student content (one subtopic) | The core risk is retired: trustworthy content with light review |
| **2** | Structure (Step 1) | Subject → Domain Model + TOC, reusing grounding |
| **3** | Blueprint (Step 2) | A runnable plan: hours, slides, speakers, dependencies |
| **4** | Integrate & scale content | A whole course's content generated from a subject |
| **5** | Lesson plan + LMS packaging | Teacher materials and platform-ready output |
| **6** | Hardening | Reliable, observable, pleasant to run |

### Phase details

**Phase 0 — Foundations & Walking Skeleton. COMPLETE.** The artifact schemas, orchestrator, approval loop, resumability, hardcoded real-shaped stubs, and referential-integrity check are in place. The archived Phase 0 handoff remains as historical implementation context only.

**Phase 1 — Make Student Content real, on ONE subtopic. CURRENT FOCUS.** Retire the biggest risk. Feed the real structure and manual reference assets for one FRM subtopic into a Student Content agent. Build the trust machinery: grounding, separate verification, attribution, and a small human review rubric. Iterate against the human-made version of that same subtopic until quality is acceptable. *Done when:* for one subtopic, the agent's output is at least as good as the manual version and review takes minutes, not a rewrite.

**Phase 2 — Make Structure real (Step 1).** Turn a subject into a competitor scan, a Domain Model, and a TOC — reusing the grounding infrastructure from Phase 1. Feed the new Domain Model back into Step 3 as a grounding upgrade. *Done when:* from a subject line you get a Domain Model and TOC comparable to a human researcher's, with human checks at quality-sensitive points (especially the competitor scan).

**Phase 3 — Make Blueprint real (Step 2).** Turn the TOC + Domain Model into a runnable plan: hours, slide counts, speaker placement, dependencies. More rules and structured generation than open-ended writing. A simple dependency model. *Done when:* the Blueprint produces a plan a human signs off on with only minor tweaks.

**Phase 4 — Integrate, then scale content.** Let Step 3 consume real Step 1 and 2 output, and generate content for ALL subtopics with tracking, retries, and partial-failure handling. Do not parallelize before this point. *Done when:* a whole course's student content generates from a subject, with approvals at the gates.

**Phase 5 — Lesson Plan (Step 4) + LMS packaging.** A lesson-plan agent (per-class plans, live-vs-self-study, talking points) and packaging that exports the course folder into the target LMS format. Both depend on finished content, so both come last. *Done when:* the folder is complete and uploads cleanly into the target LMS.

**Phase 6 — Hardening.** A better approval interface, tracing/observability, retries, cost control, polished single-folder output. Polish after it works, never before. *Done when:* someone who didn't build it could run a course and trust the result.

---

## 17. Two-person division of labor

A clean split is **bones versus intelligence**. It keeps the two builders out of each other's way once contracts are set.

| Role | Owns |
|---|---|
| **Person A — Platform** | The bones: orchestrator, artifact schemas & storage, the approval loop, packaging, tracing. |
| **Person B — Agents** | The intelligence: the step agents — prompts, grounding, verification, attribution, and the evals. |
| **Where to pair** | Tightly in Phase 0 (the shared contracts) and Phase 1 (the make-or-break step). Diverge after that. |

---

## 18. What will bite you (anti-patterns to avoid)

- **The monolith temptation** — one giant prompt that does everything. Keep steps bounded with clear contracts.
- **Frameworks too early** — debugging through a black box you don't understand. Direct model calls first.
- **Treating verification as optional** — it is the whole reason review can be light. Build it as a real component with its own quality target.
- **Building in course order** — it feels natural and it stalls projects. Build by contracts and risk.
- **Optimising too early** — don't parallelise or add a vector database before one subtopic works end to end.
- **No eval** — without comparing against the manual courses you can't tell whether a change helped. Build the comparison early.

---

## 19. Phase 0 completion snapshot

**Status:** Phase 0 is complete. The active build focus is now Phase 1.

What Phase 0 left behind as durable project context:

- **Artifact schemas v0.1 are locked for the POC.** The five artifact bodies are Domain Model, TOC, Blueprint, Content Package, and Lesson Plan. Worked FRM examples live in `documents/artifact_samples/`.
- **Every artifact is wrapped in the same metadata envelope.** The orchestrator owns lifecycle fields such as `status`, `revision`, `revision_note`, and `updated_at`; artifact-specific content lives under `body`.
- **The TOC is the single source of truth for structure.** Later artifacts reference stable TOC IDs instead of re-encoding the module/subtopic tree. Human-facing numbering is derived from `order`.
- **The walking skeleton works.** `orchestrator.py`, `steps.py`, and `run.py` run the four-step pipeline end to end with hardcoded real-shaped stubs, save artifacts under `courses/<course_id>/`, pause for approval, and skip already-approved steps on resume.
- **Step functions are isolated contracts.** Each step follows `(inputs, feedback) -> {artifact_type: artifact}`. Rejection at a checkpoint re-runs only that step, preserving earlier approved artifacts.
- **A cheap contract guard exists.** `integrity.py` checks that Blueprint, Content Package, Lesson Plan, Domain Model, and TOC references resolve.
- **The learning scripts exist only as a throwaway sandbox.** `learning_scripts/` demonstrates a plain model call, grounded answer, and simple tool-use loop. They are not part of the skeleton and should not shape production architecture unless a Phase 1 decision explicitly promotes an idea from them.

The Phase 0 handoff has been archived at `documents/context_docs/archive/Course_Builder_Phase0_Handoff.md`. Treat it as historical rationale, not the current source of active instructions.

---

## 20. Team & current state

- **Team:** two engineers, both new to agentic AI.
- **Current state:** Phase 0 is complete. The project has a working file-based skeleton with approved demo artifacts in `courses/frm-demo/`, real-shaped hardcoded stubs, and referential-integrity validation. No real content-generation agent has been built yet.
- **Building method:** the project is being built largely with AI assistance — this document exists to give any AI collaborator full context.
- **Key asset:** existing, manually-built courses (risk & governance subjects). These are the reference for designing the artifacts AND the quality bar the agent's output is measured against.
- **Immediate next action:** create a Phase 1 implementation handoff/design doc, then build Student Content for one chosen FRM subtopic with grounding, separate verification, source attribution, and a review rubric.

---

*This is a living document. When a locked decision changes, a phase completes, or the vision sharpens, update the relevant section. A stale context document is worse than none.*
