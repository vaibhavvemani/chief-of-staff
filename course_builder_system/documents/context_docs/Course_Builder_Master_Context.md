# Course Builder — Master Context Document

> **Purpose:** This is the single source of truth for the Course Builder project. It exists so that any AI assistant (or new human collaborator) can read this one document and understand exactly what we are building, why, how it is designed, and how we intend to build it. The project is being built largely with AI assistance, so this document is written to orient an AI quickly and completely.

---

## Current status - 2026-07-17

The four-week Course Builder prototype is complete as a working vertical product prototype. It has passed deterministic local acceptance, a second-topic domain-neutral smoke test, and one full live end-to-end run using live research, live LLM-backed content generation, live verification, lesson-plan generation, and Markdown rendering.

Read `Course_Builder_Four_Week_Prototype_Completion_Handoff.md` before starting new work. It is the current prototype closeout record and supersedes the pre-build sprint assumptions for status, known gaps, and recommended next work.

Course Builder Studio, the artifact-oriented browser interface, is also implemented as a local product prototype. It adds a React/Vite frontend and FastAPI adapter for course creation, eight-stage review, live or deterministic stage execution, explicit source decisions, claim-level content review, Lesson Plan inspection, and Markdown Package review. Read `Course_Builder_Frontend_Implementation_Handoff.md` before changing the frontend, API adapter, workspace projection, or browser workflow.

The next development cycle is now planned as a milestone-gated program whose release target is one internal, nontechnical course director completing a sample course without terminal or JSON intervention. Read `Course_Builder_Next_Development_Cycle_Plan.md` for the product roadmap, then use its technical-contract, implementation-backlog, and acceptance/pilot companion documents before starting cycle work.

The NC-10 lifecycle and command foundation and NC-20 Guided Brief Intake package are implemented and independently checkpointed. NC-002, NC-004, NC-005, NC-101 through NC-109, and NC-201 through NC-207 have deterministic evidence covering lifecycle vocabulary, catalog-driven invalidation, impact checksums and mutation locking, approval guards, explicit reopen, backend-projected capabilities, scoped Content revision, failure preservation/retry, read-only examples, truthful controls, durable multi-round Brief intake, typed questions, explicit default acceptance, conditional clarification, normalized historical reads, transitive backend intake gates, and reopen-protected direct editing. NC-30 Outcomes decisions is the next safe package to begin; NC-30 and later packages remain unstarted.

The most important current conclusion:

- the pipeline works end to end;
- source enforcement, asset selection, resume, rendering, and integrity checks work;
- live generation can complete at acceptable cost after source-excerpt bounding;
- the browser now provides the primary structured operator workspace over the same artifact contracts;
- first-pass live content is not automatically learner-ready;
- verifier blockers must drive source repair and targeted revision before a live course is considered final.
- the next cycle must first make lifecycle, reopening, impact, revision, and intake behavior truthful before layering on complete live-agent parity.

---

## 0. How to use this document (for AI assistants)

- Read this whole document first. It is self-contained — you should not need any other file to understand the project.
- Then read `Course_Builder_Four_Week_Prototype_Completion_Handoff.md` for the current implementation state, validation evidence, and next work package.
- For frontend or API-adapter work, then read `Course_Builder_Frontend_Implementation_Handoff.md`. The older frontend product plan records intent; the handoff records the implementation that actually exists.
- For next-cycle work, read `Course_Builder_Next_Development_Cycle_Plan.md`, then its `Technical_Contract`, `Implementation_Backlog`, and `Acceptance_and_Pilot` companion documents. The roadmap defines target intent; the handoffs define current implementation reality.
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

**In one line:** A domain-agnostic agent that can build a complete course on any subject — researching it, structuring it, generating learner and teacher material, and packaging it for an LMS — while a single person directs it and approves its work at the decision points that matter.

The goal is **not** to remove the human. It is to make course-building **roughly 10× faster** by shifting the person from producing everything by hand to **directing and approving**. The agent does the heavy lifting; the human steers.

---

## 4. What "done" looks like (the deliverable)

When a course is complete, the human receives **a single organized folder** containing all material for that course:

| Folder Section | What it contains |
|---|---|
| **Student Content** | Learner-facing deliverables — learning objectives, reading material, slides, workbooks, case studies, quizzes/assessments — organized by module and subtopic, packaged in an LMS-ready format. |
| **Teacher Content** | What the teacher delivers live — per-class lesson plan, the live-vs-self-study split, talking points, and solution guides. A layer distinct from the student reading material. |
| **Course Design Documents** | The approved Course Brief and course-level outcomes, Research Dossier and source decisions, compact Course Model, and Blueprint. |
| **Reference Sources** | The approved source corpus and source metadata used to ground the course. Full source text stays here rather than inside the Course Model. |

The folder is the deliverable.

---

## 5. The course-building workflow

A course is built through **eight approval-oriented stages**. The stages are sequential at the contract level, but a stage may contain an agent loop with the human until its artifact is approved.

```
1. BRIEF → 2. OUTCOMES → 3. RESEARCH & SOURCES → 4. COURSE MODEL
         → 5. BLUEPRINT → 6. STUDENT CONTENT → 7. LESSON PLAN → 8. PACKAGE
```

### Stage 1 — Conversational Course Brief
The user may begin with only a subject. The agent asks the smallest useful set of clarifying questions about audience, prior knowledge, desired depth, duration, scope, modality, jurisdiction, goals, constraints, and must-have or excluded material. The user approves the resulting Course Brief.

### Stage 2 — Course-level Outcomes
The agent proposes measurable course-level learning outcomes from the approved brief. The human revises and approves these **before research** so the competitor scan and structure are aimed at the intended learning result. These are design outcomes for the whole course; learner-facing objectives for individual subtopics are separate content assets.

### Stage 3 — Research Dossier and Source Approval
The agent researches competing courses, current practice, real-world problems, and candidate authoritative sources. It produces a separate **Research Dossier** with competitor findings, gaps, candidate sources, and source-to-topic relevance. The human explicitly approves or rejects sources. Full source texts are stored separately and are never embedded in the Course Model.

### Stage 4 — Course Model
The agent turns the approved brief, outcomes, research, and source decisions into one compact **Course Model**. It combines the former Table of Contents and Domain Model use cases: modules, subtopics, order, scope, concepts, dependencies, coverage requirements, and approved source IDs. The human revises and approves it as a single artifact.

### Stage 5 — Blueprint
The Blueprint turns the Course Model into a runnable operational plan. Per subtopic it records delivery time, depth, target learning minutes, a target word **range**, required concepts/examples/case depth, assessment complexity, and the exact learner and teacher assets to generate. It may also plan slide volume and speaker placement. Asset selection is not globally fixed: the human can choose what a particular subtopic needs.

### Stage 6 — Student Content
For each selected asset, a deterministic context builder supplies the current subtopic slice, course/audience context, relevant neighbouring titles/scopes, and only the approved source material routed to that asset. Long-form content follows `approved coverage plan → draft → coverage/depth check → bounded targeted regeneration`. Length is a guardrail, not a universal pass/fail threshold. A separate verification pass checks factual claims and attribution. Section-by-section drafting can be added during whole-course scaling if measured quality or context size warrants the extra calls.

### Stage 7 — Lesson Plan
The agent maps approved course content against live teaching time, decides live versus self-study delivery, and produces per-class plans and teacher talking points.

### Stage 8 — Package
The approved learner and teacher assets are assembled into the organized course folder and packaged for the target LMS.

---

## 6. The compact Course Model

The Course Model is the **single approved contract for course structure and scoped subject understanding**.

- **One artifact, two logical views:** its hierarchy provides the TOC view; its concepts, scope, dependencies, coverage requirements, and source mappings provide the former Domain Model view. Separate TOC and Domain Model documents are retired for new work.
- **Compact by design:** it contains only information needed to design and generate the approved course. It does not contain competitor-course narratives, full source text, generated teaching prose, or encyclopedic background.
- **Stable identifiers:** modules, subtopics, concepts, outcomes, and sources use IDs so later artifacts reference rather than duplicate them.
- **Sources remain separate:** the Research Dossier records why sources were considered and the source store holds their text. The Course Model stores only approved source IDs and topic relevance.
- **Context is sliced deterministically:** later calls do not receive the whole Course Model and source corpus. Code selects the current subtopic, its parent and small neighbour summary, relevant course/audience constraints, Blueprint requirements, and assigned approved source excerpts by ID.
- **No RAG yet:** this is explicit artifact selection, not semantic retrieval. Add embeddings/vector search only when deterministic source-to-subtopic mappings demonstrably stop scaling.

---

## 7. The human's role (the checkpoint model)

The agent does the heavy lifting and works through a step on its own. At a **checkpoint** it stops, shows what it produced, and asks whether it is good enough or needs changes. The person approves or redirects; only then does the agent move on.

**Motto:** the agent proposes, the human disposes, and nothing significant moves forward without a yes.

| Stage | What the human provides | What they approve at the checkpoint |
|---|---|---|
| Brief | Initial subject and answers to the agent's clarifying questions | Audience, depth, scope, duration, modality, constraints, inclusions and exclusions |
| Outcomes | Corrections and priorities | Course-level learning outcomes |
| Research & Sources | Trust preferences and known sources | Research findings and the exact candidate sources allowed for use |
| Course Model | Structural and subject-matter corrections | Modules, subtopics, order, scope, concepts, dependencies, coverage and source mappings |
| Blueprint | Delivery constraints and content preferences | Per-subtopic depth budget, timing, examples/cases, assessment complexity and selected assets |
| Student Content | Feedback on individual assets | Grounded, verified learner material before packaging |
| Lesson Plan | Live teaching time available per module/class | Live-vs-self-study split and per-class plan |

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

**Known gaps the POC closes:** heavy reliance on one person; slow, repetitive manual prompting; uneven/manual verification; **LMS packaging (now built — SCORM 1.2 converter, see §16)**; underdeveloped trainer enablement; drift between the defined asset list and what's actually produced.

---

## 10. Decisions already locked (do not re-litigate)

The 2026-06-30 migration rules are recorded in `Course_Builder_Architecture_Decision_2026-06-30.md`.

| Decision | What was settled |
|---|---|
| **It is a Chief of Staff with a pipeline inside it** | The end product automates a company process by process. The course-building workflow is the first process it learns to run — not the whole product. |
| **Course-building is the first POC** | Chosen because it is real, self-contained, understood, and exercises the right general patterns. |
| **Domain-agnostic course creation** | The product must be capable of building a course on any subject. FRM is a Phase 1 benchmark fixture, not product logic or the permanent domain. |
| **Checkpoint model for human control** | Agent runs a step, stops, shows its work, asks for approval. Not continuous-supervision, not fully autonomous. |
| **Brief and course outcomes are approved first** | The agent clarifies intent conversationally; the human approves the Course Brief and course-level outcomes before research begins. |
| **The Course Model combines TOC + Domain Model** | One compact, human-correctable artifact preserves both logical views. Full research and source text remain separate. |
| **Human approves sources and per-subtopic assets** | Candidate sources and each subtopic's document/asset plan are explicit user decisions, not hidden or globally fixed choices. |
| **Deterministic context slicing before RAG** | Generation receives a small subtopic-specific Course Model slice and assigned approved source excerpts. No vector database until this simpler mapping fails at real scale. |
| **Depth is planned, not padded** | Blueprint depth budgets and coverage checks govern expansion. There is no universal word minimum across all subtopics. |
| **One director per course** | Single-owner-per-project. Not designing for multi-user collaboration in the POC. |
| **The deliverable is an organized folder** | Student content, teacher content, approved design/research artifacts, and reference sources — sorted and LMS-ready where applicable. |
| **General lessons live in phase docs** | High-level docs stay course-focused; Chief-of-Staff generalization happens in per-phase design work. |
| **Build order ≠ course order** | We build by contracts and risk, not in the sequence a course is made (see Section 12). |
| **No agent framework at the start** | Direct model SDK calls first. Add a framework later only if a concrete need appears. |

---

## 11. Open questions (to resolve during phasing)

- **Target LMS and packaging format. RESOLVED — SCORM 1.2.** A standalone converter (`.docx`/`.pptx` → self-contained SCORM 1.2 `.zip`, via a LibreOffice→PDF→JPEG pipeline) is built and tested against an LMS; see `scorm_converter.md`. It does not affect the brief, research, Course Model, or Blueprint contracts. The remaining Phase 5 work is wiring the builder's generated course folder into it (see §16).
- **Phase 1 benchmark gate. RESOLVED — PASSED.** The final FRM outputs were fully reviewed and accepted on 2026-07-01. Phase 1 is closed; the FRM package remains benchmark evidence and fixture data.
- **Source context scale threshold.** Measure prompt size and source coverage as courses grow; define the evidence that would justify moving beyond deterministic source-to-subtopic mapping to retrieval.
- **Cost-vs-depth policy.** Use the Blueprint's dynamic depth budget and logged runs to decide how thorough — and therefore how slow/expensive — generation and verification should be.
- **How each agent is actually built.** All technical implementation is decided per-phase with the Chief-of-Staff vision in view.

---

## 12. Implementation philosophy: build order is not course order

The natural instinct is to build the workflow from Brief through Package in order. **That is the wrong implementation sequence, and following it is a common way projects like this stall.** Two ideas replace it:

**Each stage is a function.** It takes input artifacts and produces an output artifact:
`subject → approved brief → approved course outcomes → research dossier + approved sources → Course Model → Blueprint → Student Content → Lesson Plan + package`.
So the **contracts between stages matter more than any single stage's cleverness**. If each artifact's shape is well-defined and stable, you can build, test, and swap each stage on its own — and hand-author an artifact to test a later stage before the earlier one exists. **The real foundation is the data model, not the first stage.**

**Deepen stages in risk order.** Student Content is the long pole: heaviest, highest-value, and home to the one genuinely uncertain question — *can an agent produce content trustworthy enough that review is light?* Answer that early. Finished manual courses let us test it on hand-authored input and measure it against a known-good result before building conversational intake and live research.

---

## 13. Principles to build by

- **Smallest thing that works, first.** Reach for the simplest version that proves the point, then grow it.
- **No agent frameworks at the start.** Call the model SDK directly. Frameworks (LangChain, CrewAI, etc.) hide the mechanics you most need to learn and make debugging painful. Add one later only if a concrete need appears.
- **Contracts before cleverness.** Lock the artifact shapes before building the agents that fill them.
- **Composition over monolith.** Keep each stage a small, bounded agent with a clear contract — not one giant do-everything prompt.
- **Verification is the product, not a feature.** It is the entire reason review can be light.
- **Hand-author inputs to test later stages.** You do not need intake and research agents finished to test content generation—only valid approved fixtures.

---

## 14. Glossary (shared vocabulary)

| Term | Meaning |
|---|---|
| **Agent** | An LLM given a goal, some tools, and a loop — so it takes steps toward the goal instead of answering once. |
| **Tool / tool use** | A function you expose to the model (search, read a file, run code) that it can choose to call. How an agent acts, not just talks. |
| **Artifact / contract** | The defined data shape each stage outputs and the next consumes (for example the Course Model as JSON). Stable contracts let you build and test each stage on its own. |
| **Course Model** | The compact combined artifact for course hierarchy and scoped subject understanding; it replaces separate TOC and Domain Model artifacts for new work. |
| **Research Dossier** | Competitor findings, gaps, candidate sources, relevance notes, and human source decisions. It is deliberately separate from the compact Course Model. |
| **Context slice** | A deterministic, ID-based subset of the approved artifacts and sources assembled for one subtopic or asset generation call. |
| **Grounding** | Generating from supplied, verified sources rather than the model's memory — so facts are real and traceable. |
| **RAG** | Retrieval-augmented generation: semantic retrieval for grounding at scale. Do not reach for it until deterministic source-to-subtopic mappings stop scaling. |
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
| **Approval** | Course Builder Studio is the current structured browser checkpoint interface. The terminal prompt remains useful for CLI acceptance and debugging. |
| **Grounding** | Store approved source texts separately; map them to subtopics and inject only relevant excerpts. Move to retrieval / RAG only when this deterministic mapping demonstrably stops scaling. |

---

## 16. The build plan — seven phases

**Build by contracts and risk, not course order.** Each phase replaces one stub with one real agent.

| Phase | Focus | What you prove or get |
|---|---|---|
| **0** | Foundations & walking skeleton | **Complete:** pipeline runs end to end with real-shaped stubs, approvals, resumability, and contract checks |
| **1** | Student content (one subtopic) | **Complete:** core generation, attribution, verification, and targeted revision risk retired on FRM benchmark |
| **2** | Intent, research & Course Model | **Complete in prototype:** clarified brief → outcomes → research/source approval → compact Course Model |
| **3** | Blueprint | **Complete in prototype:** runnable per-subtopic plan with depth, time, assets, examples/cases, assessments, and source routing |
| **4** | Integrate & scale content | **Complete in prototype:** whole-course selected content generation from approved artifacts |
| **5** | Lesson plan + output folder | **Complete in prototype for Markdown:** teacher lesson plan and organized Markdown course folder; native DOCX/PPTX/SCORM wiring remains later |
| **6** | Hardening | **Partially complete:** resume, negative gates, source-context cost control, run-summary attention gate, and local browser workspace; production deployment, deeper editing, and richer observability remain later |

### Phase details

**Phase 0 — Foundations & Walking Skeleton. COMPLETE.** The artifact schemas, orchestrator, approval loop, resumability, hardcoded real-shaped stubs, and referential-integrity check are in place. The archived Phase 0 handoff remains as historical implementation context only.

**Phase 1 — Make Student Content real, on ONE subtopic. COMPLETE.** The FRM benchmark exercised the domain-agnostic generation path, scoped grounding, separate verification, claim-level attribution, coverage/depth checks, targeted revision, and the human review rubric. The final outputs were reviewed and accepted on 2026-07-01. See `Course_Builder_Phase1_Handoff.md`.

**Phase 2 — Make intent, research, and structure real. COMPLETE IN PROTOTYPE.** Starting from a subject as broad as “coffee making,” the prototype can run clarification, approve a Course Brief and course-level outcomes, research competitors and candidate sources, apply explicit source decisions, and produce one compact Course Model. Research evidence and source content remain outside the Course Model. The remaining work is source-quality hardening, not Phase 2 contract completion.

**Phase 3 — Make Blueprint real. COMPLETE IN PROTOTYPE.** The Blueprint turns the Course Model into a runnable plan with timing, depth budgets, word ranges, concepts/examples/cases/assessment complexity, selected assets, and per-asset source routing.

**Phase 4 — Integrate, then scale content. COMPLETE IN PROTOTYPE.** Content generation consumes deterministic per-subtopic slices from the Course Model, Blueprint, and approved source store. It generates only selected assets and supports verification, retry states, resume, and targeted revision. The next scale work is source repair, verifier-driven revision, cost controls, and eventually parallelization.

**Phase 5 — Lesson Plan + output packaging. COMPLETE IN PROTOTYPE FOR MARKDOWN.** The lesson-plan agent maps approved content into a basic schedule, and the renderer exports an organized Markdown course folder. Native DOCX/PPTX and wiring generated output into the existing SCORM converter remain later work.

**Phase 6 — Hardening. PARTIAL.** The prototype now has resume behavior, local acceptance, negative tests, source-context cost control, a run-summary attention gate, and Course Builder Studio as a local operator workspace. The browser supports the full eight-stage review flow, but the system still needs a closed source-repair/reverification loop, deeper structured editing, richer diagnostics, production deployment, and production packaging before a non-builder can run it confidently.

---

## 17. Two-person division of labor

A clean split is **bones versus intelligence**. It keeps the two builders out of each other's way once contracts are set.

| Role | Owns |
|---|---|
| **Person A — Platform** | The bones: orchestrator, artifact schemas & storage, the approval loop, packaging, tracing. |
| **Person B — Agents** | The intelligence: the stage agents — prompts, grounding, verification, attribution, and the evals. |
| **Where to pair** | Tightly in Phase 0 (the shared contracts) and Phase 1 (the make-or-break step). Diverge after that. |

---

## 18. What will bite you (anti-patterns to avoid)

- **The monolith temptation** — one giant prompt that does everything. Keep steps bounded with clear contracts.
- **Frameworks too early** — debugging through a black box you don't understand. Direct model calls first.
- **Treating verification as optional** — it is the whole reason review can be light. Build it as a real component with its own quality target.
- **Building in course order** — it feels natural and it stalls projects. Build by contracts and risk.
- **Optimising too early** — don't parallelise or add a vector database before one subtopic works end to end.
- **No eval** — without comparing against the manual courses you can't tell whether a change helped. Build the comparison early.
- **Domain facts in reusable prompts** — prompts express the task; approved artifacts provide the subject-specific coverage requirements.
- **Context dumping** — do not inject the full Course Model and every source into every call. Build the deterministic context slice first.
- **Word-count inflation** — a universal minimum rewards padding. Use subtopic-specific depth, coverage, examples, and word-range checks.

---

## 19. Prototype completion snapshot

**Status:** The four-week prototype is complete as an engineering prototype. Existing FRM artifacts remain a narrow quality benchmark; the non-FRM coffee acceptance path and indoor herb smoke path prove the domain-neutral contracts.

What Phase 0 left behind as durable project context:

- **Artifact schemas v0.1 are historical walking-skeleton contracts.** They originally separated Domain Model and TOC. New work migrates them to the combined Course Model and adds Course Brief, course outcomes, Research Dossier/source decisions, and per-subtopic Blueprint depth/asset fields.
- **Every artifact is wrapped in the same metadata envelope.** The orchestrator owns lifecycle fields such as `status`, `revision`, `revision_note`, and `updated_at`; artifact-specific content lives under `body`.
- **Stable hierarchy IDs remain the single source of truth for structure.** In the target contract these live in the Course Model; later artifacts reference them instead of re-encoding the module/subtopic tree. Human-facing numbering is derived from `order`.
- **The walking skeleton works.** `orchestrator.py`, `steps.py`, and `run.py` run the four-step pipeline end to end with hardcoded real-shaped stubs, save artifacts under `courses/<course_id>/`, pause for approval, and skip already-approved steps on resume.
- **Step functions are isolated contracts.** Each step follows `(inputs, feedback) -> {artifact_type: artifact}`. Rejection at a checkpoint re-runs only that step, preserving earlier approved artifacts.
- **A cheap contract guard exists.** `integrity.py` checks cross-artifact references in the current contracts; migration must preserve equivalent checks for Course Model, approved sources, Blueprint, Content Package, and Lesson Plan IDs.
- **The learning scripts exist only as a throwaway sandbox.** `learning_scripts/` demonstrates a plain model call, grounded answer, and simple tool-use loop. They are not part of the skeleton and should not shape production architecture unless a Phase 1 decision explicitly promotes an idea from them.

The Phase 0 handoff has been archived at `documents/context_docs/archive/Course_Builder_Phase0_Handoff.md`. Treat it as historical rationale, not the current source of active instructions.

---

## 20. Team & current state

- **Team:** two engineers, both new to agentic AI.
- **Current state:** The four-week pipeline prototype and the local Course Builder Studio frontend are implemented and independently reviewed through NC-20 Guided Brief Intake. The reusable contracts, prompts, context builder, verification, integrity path, FastAPI adapter, React workspace, durable guided intake, local acceptance course, live-run evidence, and FRM benchmark are in place. FRM-specific fixtures remain benchmark data, not reusable prompt or contract assumptions.
- **Building method:** the project is being built largely with AI assistance — this document exists to give any AI collaborator full context.
- **Key asset:** existing, manually-built courses (risk & governance subjects). These are the reference for designing the artifacts AND the quality bar the agent's output is measured against.
- **Immediate next action:** begin NC-30 Outcomes decisions from `Course_Builder_Next_Cycle_Implementation_Backlog.md`, preserving the verified NC-10 lifecycle guarantees and NC-20 intake, persistence, validation, provenance, normalization, and approval-gate contracts.

---

*This is a living document. When a locked decision changes, a phase completes, or the vision sharpens, update the relevant section. A stale context document is worse than none.*
