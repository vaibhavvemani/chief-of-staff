# Course Builder — Four-Week Sprint Plan

> **Status:** READY TO EXECUTE
> **Created:** 2026-07-01
> **Scope authority:** `Course_Builder_Four_Week_Prototype_Plan.md`
> **Team:** Developer A — **Vaibhav**; Developer B — **Siddarth**
> **Cadence:** Four one-week sprints; five focused working days per sprint
> **Capacity assumption:** Approximately 25–30 focused hours per developer per week
> **Delivery goal:** A domain-neutral, human-directed prototype that builds a modest complete course from a sparse topic request.

## 1. Ownership model

Both developers own agent intelligence and engineering. The split follows two balanced capability groups.

### Vaibhav — user guidance and delivery

- Typed question and structured-choice interaction framework.
- Course Brief and Course Outcomes agents.
- Blueprint agent and per-subtopic depth/asset decisions.
- Whole-course pipeline coordination, progress, and resume UX.
- Lesson Plan agent.
- Markdown renderer and organized final course folder.

### Siddarth — research and knowledge production

- Research adapter and source acquisition.
- Competitor TOC extraction and normalized comparison.
- Source-decision application and approved-source storage.
- Course Model agent.
- Whole-course Student Content adaptation.
- Verification, source integrity, and deterministic context enforcement.

### Shared ownership

- Artifact contracts and fixtures at sprint boundaries.
- End-of-sprint integration gates.
- Primary and secondary acceptance runs.
- Cross-boundary debugging and scope decisions.

The intended balance is approximately 75% independent implementation and 25% contract, integration, and acceptance work.

## 2. Working agreement

1. **No end-of-project merge.** Each developer integrates completed tasks at least every one to two working days.
2. **Contract first.** A producer and consumer agree on fixture JSON and validation before implementing independently.
3. **One primary owner per shared file.** During these four weeks, Vaibhav owns `run.py`, the pipeline assembly, and interaction-facing integration. Siddarth owns `integrity.py` and the source/context enforcement path. Each developer owns their agent modules and prompts.
4. **Keep `steps.py` thin.** New intelligence belongs in agent or service modules. Vaibhav performs final pipeline wiring after Siddarth exposes tested call boundaries, reducing merge contention.
5. **Tests travel with tasks.** A task is not complete if only the happy-path implementation exists.
6. **Fixtures unblock parallel work.** Vaibhav can build interaction and rendering against mocked research/Course Model outputs; Siddarth can build agents against mocked interaction decisions.
7. **Daily boundary check.** Spend 10–15 minutes confirming contract changes, blockers, and the next integration point.
8. **Gate before stretch work.** Native DOCX/PPTX, SCORM wiring, browser UI, and parallel generation do not enter a sprint until its required gate passes.

## 3. Integration ladder

Each sprint leaves a runnable vertical increment:

| Sprint | Runnable result at the gate |
|---|---|
| **1 — Intent and interaction foundation** | Sparse request → guided Brief → selected Outcomes → mocked research/source-choice checkpoint |
| **2 — Research, structure, and Blueprint** | Sparse request → live competitor/source research → human source decisions → approved Course Model → approved Blueprint |
| **3 — Whole-course production** | Approved Blueprint → selected content for all planned subtopics → verification → Lesson Plan → Markdown folder |
| **4 — Acceptance and stabilization** | Complete non-FRM live course, second-topic smoke test, resume/failure proof, operator-ready demo |

## 4. Sprint 1 — Intent and interaction foundation

### Sprint goal

Lock the new contracts and build the reusable human-interaction foundation. By the gate, a sparse subject must become an approved Course Brief and selected Course Outcomes, then reach a mocked structured source-selection checkpoint.

### Vaibhav tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S1.A1** | Subject Request + Course Brief v0.2 contracts | Add schemas/fixtures for sparse request and approved Brief; cover required, optional, conditional, and provenance/assumption fields; validation tests pass. | 4h | S1.P1 |
| **S1.A2** | Typed question and choice models | Implement provider-independent question/choice structures with stable IDs, answer types, defaults, `show_if`, validation, single/multi-select, recommendations, and optional custom items. | 5h | S1.P1 |
| **S1.A3** | Terminal interaction renderer + test responder | Render typed questions/choices in the console; add an injectable scripted responder for deterministic tests; no LLM required for standard questions. | 4h | S1.A2 |
| **S1.A4** | Hybrid intake agent | Implement deterministic Brief questions plus bounded agent follow-ups; do not repeat resolved fields; show assumptions; emit schema-valid Brief. | 5h | S1.A1, S1.A3 |
| **S1.A5** | Course Outcomes agent and outcome choices | Generate measurable outcomes; support select/reject/edit/add/reprioritize; prevent research when no meaningful outcome is approved. | 4h | S1.A1, S1.A3 |

**Vaibhav planned load:** 22h individual + shared work.

### Siddarth tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S1.B1** | Expanded Research Dossier contract | Add extracted competitor outlines, original ordering/locators, normalized topics, coverage matrix, sequence observations, structural implications, and candidate factual sources; version contract if required. | 4h | S1.P1 |
| **S1.B2** | Research adapter interfaces | Define testable search, fetch, extract, and source-store boundaries; provide a mocked provider and failure results without coupling agents to one vendor. | 5h | S1.P1 |
| **S1.B3** | Competitor outline extraction/normalization prototype | Convert fixture competitor pages/outlines into ordered sections and normalized topics; preserve raw labels; build a coverage-matrix fixture. | 5h | S1.B1, S1.B2 |
| **S1.B4** | Source store foundation | Persist approved source content/excerpts by stable course/source ID; validate locators/content references; represent failed or unavailable sources explicitly. | 4h | S1.B2 |
| **S1.B5** | Deterministic source-selection reducer | Apply selected IDs to proposed candidates as approved/rejected without LLM interpretation; prove rejected/proposed sources are excluded from the mocked downstream registry. | 4h | S1.A2, S1.B1 |

**Siddarth planned load:** 22h individual + shared work.

### Shared tasks and gate

| ID | Owners | Task | Acceptance | Estimate each |
|---|---|---|---|---:|
| **S1.P1** | Vaibhav + Siddarth | Contract lock and fixture walkthrough | Agree on Subject Request, Brief, Outcomes, Research Dossier, question/choice boundary, stable IDs, and producer/consumer fixtures before implementation. | 3h |
| **S1.P2** | Vaibhav + Siddarth | Mid-sprint contract integration | Run scripted interaction into mocked research proposals; resolve schema/interface drift while changes are still small. | 1.5h |
| **S1.M** | Vaibhav + Siddarth | Sprint 1 integration gate | A sparse non-FRM request completes guided Brief and Outcomes approval, displays a structured mocked candidate-source form, applies source choices deterministically, and passes all old/new tests. | 2.5h |

**Planned total:** approximately 29h per developer.

### Sprint 1 gate artifacts

- Subject Request and Course Brief contracts.
- Question/choice interaction module and console renderer.
- Scripted test responder.
- Real intake and outcomes agents.
- Expanded Research Dossier contract.
- Mock research adapter, competitor comparison fixture, source store, and source-choice reducer.
- Green regression suite and a runnable intent-to-source-choice demonstration.

## 5. Sprint 2 — Research, structure, and Blueprint

### Sprint goal

Replace the mocked upstream intelligence with a live bounded research path, then generate and approve a compact Course Model and per-subtopic Blueprint. By the gate, a new topic must reach an approved runnable content plan.

### Vaibhav tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S2.A1** | Intake gap-analysis hardening | Add ambiguity/conflict checks and a maximum of three validated follow-ups; reject repeated or out-of-stage agent questions; use a cheaper model configuration where available. | 3h | S1.A4 |
| **S2.A2** | Blueprint agent | Generate course-wide defaults and per-subtopic plans for depth, minutes, word ranges, concepts, examples, cases, assessments, assets, and source routing. Build against the agreed Course Model fixture, then integrate the real agent output. | 6h | S1.B1 fixture; integrate S2.B4 |
| **S2.A3** | Per-subtopic Blueprint decision flow | Let the user accept defaults, select/reject assets, and override meaningful exceptions without completing a blank form for every subtopic. | 5h | S1.A2, S2.A2 |
| **S2.A4** | Blueprint validation and integrity-facing checks | Validate ranges, selected assets, concept/source references, and confirmation for subtopics lacking a core content asset; add negative tests. | 4h | S2.A2, S2.B5 |
| **S2.A5** | Upstream pipeline wiring and resume | Add intake to the runnable path, replace fixture outcomes when enabled, wire approved research/Course Model/Blueprint outputs, and prove rejected upstream stages rerun locally. | 4h | S2.B4, S2.A3 |

**Vaibhav planned load:** 22h individual + shared work.

### Siddarth tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S2.B1** | Live bounded search/fetch provider | Implement one live provider behind the Sprint 1 adapter; support accessible HTML and text-extractable PDFs where practical; bounded retries and actionable failures. | 5h | S1.B2 |
| **S2.B2** | Competitor TOC scanner and comparison | Target 5–8 relevant offerings, require 3 usable outlines for acceptance, extract ordered outlines, normalize topics, and produce coverage/sequence/gap analysis without inferring hidden content. | 5h | S1.B3, S2.B1 |
| **S2.B3** | Candidate factual-source research and capture | Propose auditable candidate sources with trust/relevance notes; ingest only human-approved content; support manual URL/source addition and evidence-gap results. | 4h | S1.B4, S2.B1 |
| **S2.B4** | Course Model agent | Generate modules/subtopics, scope, dependencies, concepts, coverage, and approved source mappings from Brief, Outcomes, competitor analysis, and approved sources; include compact structural rationale. | 6h | S2.B2, S2.B3 |
| **S2.B5** | Source and structure integrity enforcement | Reject proposed/rejected/unavailable source leakage, invalid dependencies/IDs, unresolved outcomes, and embedded full source/competitor evidence; add negative tests. | 4h | S2.B4 |

**Siddarth planned load:** 24h individual + shared work.

### Shared tasks and gate

| ID | Owners | Task | Acceptance | Estimate each |
|---|---|---|---|---:|
| **S2.P1** | Vaibhav + Siddarth | Live-provider and Course Model contract review | Inspect one real research result before building downstream assumptions; approve any necessary bounded schema amendment together. | 1.5h |
| **S2.P2** | Vaibhav + Siddarth | Research-to-Blueprint integration | Run approved source choices through Course Model and Blueprint; verify structural rationale and per-subtopic choices remain traceable. | 2h |
| **S2.M** | Vaibhav + Siddarth | Sprint 2 integration gate | From a sparse non-FRM request, complete live competitor/source research, reject at least one source, approve Course Model, choose different plans for two subtopics, and produce an approved Blueprint with no rejected-source leakage. | 2.5h |

**Planned total:** approximately 28–30h per developer.

### Sprint 2 gate artifacts

- Live bounded research provider.
- Competitor TOC evidence and normalized comparison.
- Human-approved source store.
- Real Course Model agent and integrity rules.
- Real Blueprint agent and structured per-subtopic decisions.
- Runnable subject-to-approved-Blueprint path with resume.

## 6. Sprint 3 — Whole-course production

### Sprint goal

Generalize the Phase 1 one-subtopic content path to a modest entire course, then produce verified selected content, a basic Lesson Plan, and an organized Markdown course folder.

### Vaibhav tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S3.A1** | Whole-course coordination and progress | Iterate approved subtopic plans sequentially; expose current stage/subtopic/asset; preserve already completed work; coordinate tested agent boundaries without embedding domain logic. | 6h | S2.M |
| **S3.A2** | Resume and partial-run UX | Resume approved stages and completed assets, display pending/failed units, and support safe retry without deleting unrelated artifacts. | 4h | S3.A1, S3.B5 |
| **S3.A3** | Domain-neutral Lesson Plan contract and agent | Replace FRM fixture; collect unresolved session constraints; produce sessions, durations, live/self-study modes, covered subtopics, and talking points; validation tests pass. Build against the existing Content Package fixture, then integrate whole-course output. | 5h | Existing fixture; integrate S3.B1 |
| **S3.A4** | Markdown course-folder renderer | Render every selected asset, course overview, source index, and Lesson Plan into deterministic organized paths; avoid claiming DOCX/PPTX files exist. Build against approved fixtures so rendering proceeds in parallel with generation. | 5h | Existing fixtures, S3.A3; integrate S3.B1 |
| **S3.A5** | Run summary and mocked end-to-end test | Record completed/skipped/failed/pending-review stages, token/cost references, and output paths; run a fully mocked modest course through the folder gate. | 4h | S3.A1–S3.A4 |

**Vaibhav planned load:** 24h individual + shared work.

### Siddarth tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S3.B1** | Generalize Student Content to all planned subtopics | Remove fixed `m1_s1` assumptions; derive stable asset IDs/titles/formats from Course Model and Blueprint; generate only selected assets across 4–8 acceptance subtopics. | 6h | S2.M |
| **S3.B2** | Generic whole-course context slicing | Build slices for arbitrary module/subtopic IDs with course/audience context, neighbour summaries, Blueprint requirements, and only approved assigned evidence. | 5h | S3.B1 |
| **S3.B3** | Selection and evidence enforcement | Deterministically block unselected assets and proposed/rejected/unassigned sources; return an evidence-gap state instead of unsupported factual drafting. | 4h | S3.B2 |
| **S3.B4** | Whole-course verification and targeted revision | Verify every generated factual asset, surface summaries by subtopic, and revise one target without regenerating unaffected assets. | 5h | S3.B1–S3.B3 |
| **S3.B5** | Partial failure, cache, and retry behavior | Preserve successful assets when one call fails; retry boundedly; reuse unchanged cache entries; expose recoverable pending state to the coordinator. | 4h | S3.B1, S3.B4 |

**Siddarth planned load:** 24h individual + shared work.

### Shared tasks and gate

| ID | Owners | Task | Acceptance | Estimate each |
|---|---|---|---|---:|
| **S3.P1** | Vaibhav + Siddarth | First multi-subtopic integration | Run two subtopics early in the sprint; fix ID, selection, context, and resume boundary defects before expanding the run. | 2h |
| **S3.P2** | Vaibhav + Siddarth | Failure/revision drill | Force one generation failure and one targeted human revision; prove completed work remains intact. | 1.5h |
| **S3.M** | Vaibhav + Siddarth | Sprint 3 integration gate | An approved 4–8-subtopic Blueprint produces exactly the selected assets, verification results, a basic Lesson Plan, Markdown deliverables, and a resumable run summary. | 2.5h |

**Planned total:** approximately 30h per developer.

### Sprint 3 gate artifacts

- Generic whole-course Student Content path.
- Enforced selection/evidence boundaries.
- Multi-subtopic verification and targeted revision.
- Partial-failure and resume behavior.
- Real Lesson Plan agent.
- Deterministic Markdown renderer and run summary.

## 7. Sprint 4 — Acceptance and stabilization

### Sprint goal

Stop adding required capabilities. Run the live acceptance course, fix integration defects, prove domain neutrality and recovery, and prepare a reliable demonstration. One full day of capacity remains reserved for unknown integration failures.

### Vaibhav tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S4.A1** | Interaction and CLI stabilization | Improve prompts, defaults, validation messages, cancellations, and summaries based on a fresh-user run; no new UI framework. | 4h | S4.P1 |
| **S4.A2** | Output-folder and run-summary stabilization | Ensure filenames, indexes, course overview, source index, status reporting, and rerun behavior remain deterministic and understandable. | 3h | S3.A4, S3.A5 |
| **S4.A3** | Lesson Plan and delivery fixes | Correct generic scheduling/timing issues found in acceptance; verify every planned subtopic is covered exactly where intended. | 3h | S3.A3 |
| **S4.A4** | Resume/operator acceptance | Document and test stop, quit, resume, rejection, retry, and targeted-revision paths from an operator’s perspective. | 3h | S3.A2 |
| **S4.A5** | Demo and operator guide | Write the minimal setup/run/review guide and a concise demonstration script using the actual acceptance output. | 2h | S4.P2 |

**Vaibhav planned load:** 15h individual + shared acceptance/buffer.

### Siddarth tasks

| ID | Task | Required output / acceptance | Estimate | Depends on |
|---|---|---|---:|---|
| **S4.B1** | Live research/TOC acceptance fixes | Run the approved topic live; fix bounded search, extraction, normalization, source capture, and insufficiency handling defects only. | 5h | S4.P1 |
| **S4.B2** | Live whole-course content/verification fixes | Complete the acceptance generation; repair evidence routing, generic IDs, verification, cache, or targeted-revision defects without subject-specific prompt rules. | 5h | S4.B1 |
| **S4.B3** | Second-topic domain-neutral smoke | Use a substantially different topic through Course Model/Blueprint and a small selected-content slice; no reusable code/prompt edits. | 3h | S4.B1 |
| **S4.B4** | Final integrity and negative tests | Prove rejected-source, unselected-asset, invalid-ID, insufficient-evidence, and hidden competitor-content failures are blocked. | 2h | S4.B2, S4.B3 |

**Siddarth planned load:** 15h individual + shared acceptance/buffer.

### Shared tasks, buffer, and final gate

| ID | Owners | Task | Acceptance | Estimate each |
|---|---|---|---|---:|
| **S4.P1** | Vaibhav + Siddarth | Primary live acceptance run | Run the agreed non-FRM course from sparse request through folder output; exercise clarification, outcome/source/asset choices, competitor scan, targeted revision, and resume. | 4h |
| **S4.P2** | Vaibhav + Siddarth | Acceptance review and defect triage | Review all artifacts and outputs together; classify only prototype-blocking defects as required; preserve scope boundary. | 2h |
| **S4.P3** | Vaibhav + Siddarth | Reserved integration buffer | One full focused day for unpredictable live research, model-output, cross-artifact, or rendering failures. Unused time may fund stretch work only after the final gate passes. | 5h |
| **S4.M** | Vaibhav + Siddarth | Prototype final gate | Primary course and second-topic smoke pass; regression suite is green; rejected sources/assets cannot leak; course folder is complete; resume works; operator guide matches the product. | 4h |

**Planned total:** approximately 30h per developer, including the protected buffer.

### Sprint 4 gate artifacts

- Complete primary non-FRM course folder.
- Second-topic domain-neutral smoke evidence.
- Final regression and negative-test results.
- Demonstrated resume, failure recovery, and targeted revision.
- Operator guide, demo script, and final run summary.
- Four-week prototype completion note.

## 8. Dependency and critical path

```text
Interaction contracts
  → Brief + Outcomes
  → Research + source decisions
  → Course Model
  → Blueprint choices
  → Whole-course selected content
  → Verification + targeted revision
  → Lesson Plan + Markdown folder
  → Live acceptance and stabilization
```

The critical path is blocked if any of these boundaries remain unstable:

- question/choice representation;
- approved-source filtering;
- Course Model hierarchy/source IDs;
- Blueprint subtopic and asset IDs;
- content generation across arbitrary subtopics;
- partial-run preservation and final rendering.

Contract changes on the critical path require same-day communication and a fixture/test update by both the producer and consumer.

## 9. Scope-control and drop order

No required item from the approved prototype plan may be silently removed. If schedule pressure appears, drop or reduce work in this order:

1. Optional interaction wording polish.
2. Additional competitor offerings beyond the target once three usable outlines exist.
3. Optional rich asset types on the acceptance course.
4. Secondary-topic content generation beyond the minimum smoke slice.
5. Nonessential renderer styling.

Do **not** drop:

- human source selection;
- approved-source enforcement;
- competitor TOC comparison;
- guided questioning;
- per-subtopic asset/depth choices;
- whole-course generation;
- verification;
- resume/recovery;
- the primary end-to-end acceptance run.

Native DOCX/PPTX, SCORM wiring, browser UI, and parallel generation remain outside the committed sprint scope.

## 10. Completion tracking

A task moves to complete only when:

- its required output exists;
- focused positive and negative tests pass;
- its consumer can use the agreed fixture or real output;
- relevant existing tests remain green;
- documentation/comments no longer describe the replaced path as active.

At every sprint gate, record:

- tasks complete, incomplete, or deliberately descoped;
- test results;
- live-call evidence where required;
- known defects and owner;
- token/cost observations;
- decision on whether the next sprint may begin.

This plan is ready to execute once the actual Sprint 1 start date and normal branch/merge workflow are confirmed by the two developers.
