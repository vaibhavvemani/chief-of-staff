# Course Builder — Four-Week Prototype Plan

> **Status:** ✅ APPROVED FOR SPRINT PLANNING — 2026-07-01
> **Prepared:** 2026-07-01
> **Team:** Two developers
> **Delivery window:** Four weeks after approval of this plan
> **Purpose:** Define what the prototype must do, how it must behave, what foundations must be implemented, and what is deliberately deferred.
> **Execution plan:** See `Course_Builder_Four_Week_Sprint_Plan.md` for sprint gates, estimates, dependencies, and assignments.

## 1. Delivery decision

A functioning domain-agnostic Course Builder prototype is achievable within four weeks for two developers if the work is treated as one narrow vertical product rather than an attempt to polish every remaining roadmap phase independently.

The prototype must prove this complete path:

`sparse topic request → guided questions → approved intent and outcomes → bounded research → human source selection → approved course structure → human-approved per-subtopic plan → grounded content → basic lesson plan → organized course folder`

It does not need a graphical interface, production-scale crawling, perfect document styling, or comprehensive hardening. The terminal may be the user interface, but the underlying interaction contracts must be reusable by a later web interface.

The original Phases 2–6 remain useful capability labels. For this deadline, however, they become workstreams inside one four-week prototype rather than separate polished releases.

## 2. Prototype objective

By the deadline, one person must be able to start with a topic such as “coffee making,” answer a manageable series of questions, make explicit choices at important checkpoints, and receive a coherent course folder generated without subject-specific code or prompts.

For the prototype, “works for any topic” means:

- All reusable prompts, schemas, selection logic, and pipeline steps are domain-neutral.
- A topic is supplied as data; adding a new subject does not require changing source code or reusable prompt text.
- The system can research and build an ordinary, publicly researchable topic when sufficient accessible sources exist.
- If evidence is unavailable or inadequate, the system stops and explains what is missing instead of inventing unsupported factual content.

It does not mean that four weeks can establish expert-level quality across every specialist, regulated, confidential, or safety-critical domain. Medical, legal, and similarly high-stakes outputs still require qualified human review.

## 3. Prototype Definition of Done

The prototype is complete only when all of the following are true:

1. A user can begin with only a subject and optional short description.
2. The agent asks stage-appropriate questions until the minimum course intent is resolved.
3. The user approves a Course Brief and measurable course-level outcomes before research starts.
4. The research agent scans a bounded set of competitor course TOCs/outlines, produces an auditable coverage-and-sequence comparison, and proposes candidate factual sources with locators and relevance notes.
5. The user explicitly approves or rejects each candidate source and may add a source manually.
6. Deterministic code prevents rejected or merely proposed sources from entering the Course Model or generation context.
7. The agent proposes a compact Course Model with modules, subtopics, scope, concepts, dependencies, coverage requirements, and approved source mappings.
8. The user reviews and approves the course structure.
9. The agent proposes a Blueprint with global defaults and per-subtopic depth, time, examples, cases, assessments, and asset/document choices.
10. The user can select which assets to generate for every subtopic and override the proposed depth where necessary.
11. The system generates only the selected assets for all selected subtopics, using only the approved source material routed to each subtopic.
12. The existing claim-attribution and separate-verification path runs on generated factual content.
13. The system produces a basic lesson plan from the approved content and teaching constraints.
14. All approved artifacts, selected sources, generated learner material, teacher material, and a run summary are written into one organized course folder.
15. A stopped or failed run can resume without repeating already approved stages or regenerating unaffected content.
16. The full path is demonstrated on one non-FRM acceptance course and smoke-tested on a second unrelated topic.

## 4. End-to-end user experience

```text
START
  └─ Topic request
      └─ Guided Course Brief questions
          └─ Human approves Brief
              └─ Agent proposes course outcomes
                  └─ Human selects/edits/prioritizes outcomes
                      └─ Agent researches competitors and sources
                          └─ Human selects allowed sources
                              └─ Agent proposes Course Model
                                  └─ Human approves structure
                                      └─ Agent proposes Blueprint defaults
                                          └─ Human selects depth and assets per subtopic
                                              └─ Generate and verify selected content
                                                  └─ Human reviews/revises affected assets
                                                      └─ Generate basic Lesson Plan
                                                          └─ Write organized course folder
```

The agent should do most of the drafting. The human should make consequential decisions, correct assumptions, and approve artifacts rather than manually author every field.

## 5. Shared interaction foundation

Two interaction capabilities must be implemented once and reused across the pipeline.

### 5.1 Guided questioning

The prototype uses a **hybrid questioning model**. Required information, answer types, validation, safe defaults, and normal conditional branches are defined deterministically. The agent may ask a small number of bounded follow-up questions only when an answer is vague, contradictory, unusually domain-specific, or likely to materially change the course.

The agent does not independently invent the whole interview. This preserves completeness, makes the experience testable, and avoids spending a model call merely to rediscover standard questions. It also avoids the opposite failure: a rigid questionnaire that accepts an answer such as “for beginners” even when the intended role, age, or baseline knowledge materially changes the course.

The deterministic question specification should define:

- a stable field and question ID;
- required, optional, or conditional status;
- a default wording and concise explanation;
- answer type and allowed options;
- validation rules;
- a safe default where appropriate;
- `show_if` conditions based on earlier answers;
- whether an agent-generated follow-up is allowed for that field.

Normal questions are rendered directly from this specification without an LLM call. After each answer round, code identifies missing required fields and simple validation failures. A bounded gap-analysis call may then propose at most three follow-ups using the same typed question representation. Code validates those proposed questions and rejects questions outside the current stage or questions that repeat resolved information.

Each question should include:

- the field or decision being resolved;
- a concise question in plain language;
- why the answer matters when that is not obvious;
- an answer type: free text, single choice, multiple choice, number, duration, or confirmation;
- sensible proposed options or a default when one is safe;
- whether the user may skip it or accept the default.

Interaction rules:

- Ask no more than three to five related questions in one round.
- Never ask again for a value already supplied unless it conflicts with later information.
- Separate user-stated facts from agent assumptions.
- Make assumptions visible before the artifact is approved.
- Ask course-wide questions once; ask per-subtopic questions only where the subtopic differs from approved defaults.
- Persist the resulting decisions in the relevant approved artifact so later stages do not need to repeat the conversation.
- Use a smaller/cheaper model for optional gap analysis when available; artifact drafting and specialist agents do not need to be invoked merely to choose the next standard question.

The prototype interface can be terminal-based. The question representation must remain independent of the terminal so a later browser UI can render the same questions as fields, radio buttons, checkboxes, or text areas.

### 5.2 Explicit human decisions

Whenever the agent proposes a list of consequential options, the user must be able to select, reject, edit, or add items through a structured choice rather than only through free-text feedback.

The reusable choice representation should support:

- a stable choice ID;
- stage and target artifact;
- single-select or multi-select mode;
- option label, concise description, and recommendation rationale;
- recommended/default selection without automatic approval;
- minimum and maximum selections where relevant;
- an optional user-supplied item;
- the final selected/rejected IDs.

The agent proposes; deterministic application code records the choice. The model must never reinterpret a message such as “use sources 1, 3, and 5” and decide for itself what was approved.

The final decision should live in the relevant artifact:

- source candidates become `approved` or `rejected`;
- Blueprint assets become `selected` or `rejected`;
- selected outcomes remain in the approved outcomes artifact;
- approved depth, timing, and lesson-plan values become the artifact values.

A lightweight interaction log may be retained for debugging, but a new general-purpose workflow database is not required.

## 6. Stage requirements

### Stage 0 — Subject request

**User supplies:** a subject and optional short description, known source links, or existing constraints.

**System behavior:** create a stable course ID and persist the initial request. No domain-specific defaults should be hidden in code.

**Output:** a small `subject_request` input artifact or equivalent persisted seed.

### Stage 1 — Conversational Course Brief

The intake agent resolves the smallest useful set of course-wide decisions.

Required areas:

- intended audience and role;
- expected prior knowledge;
- desired course purpose and practical outcome;
- level or depth;
- total learning duration or acceptable size;
- delivery modality;
- language;
- in-scope and out-of-scope material;
- must-have topics or examples;
- constraints and available materials.

Conditional areas:

- jurisdiction, regulation, or geography when relevant;
- accessibility or organizational requirements;
- assessment and certification expectations;
- live-teaching constraints;
- required tools, software, or equipment;
- freshness/currentness requirements.

These required and conditional areas become the deterministic Course Brief questionnaire. Agent follow-ups are reserved for ambiguous answers, conflicts such as advanced depth with insufficient duration, and domain-specific constraints that the fixed fields cannot safely resolve.

**Human decision:** approve or revise the summarized Course Brief.

**Output:** schema-valid Course Brief v0.2. This schema is currently missing and must be added.

**Failure behavior:** if the user declines a required high-impact question and no safe assumption exists, the stage pauses and identifies the unresolved decision.

### Stage 2 — Course-level outcomes

The outcomes agent proposes a concise set of measurable whole-course outcomes aligned with the approved brief.

Each outcome includes a statement, cognitive level, observable evidence, and priority. The interface lets the user select, reject, edit, add, and reprioritize outcomes.

**Human decision:** approve the outcomes that will guide research and structure.

**Output:** approved Course Outcomes v0.2.

**Failure behavior:** research cannot start until at least one meaningful outcome is approved.

### Stage 3 — Research and candidate sources

The research agent performs bounded research rather than open-ended browsing.

Prototype research behavior:

- derive research questions from the approved brief and outcomes;
- identify a bounded set of relevant competitor offerings, targeting five to eight and requiring at least three usable public outlines for the acceptance run;
- extract every publicly visible competitor TOC/outline: modules, units, topic titles, order, advertised level, duration, delivery format, and assessment approach where available;
- retain the original outline wording and locator while also normalizing equivalent topic names for comparison;
- build a competitor coverage matrix showing which normalized topics appear in which course;
- identify common-core topics, common sequencing patterns, unusual inclusions, omissions, depth signals, and differentiation opportunities;
- record when a competitor outline is partial, inaccessible, stale, or behind a login rather than guessing its contents;
- find a manageable list of candidate authoritative sources;
- capture title, publisher, source type, locator, trust notes, relevance, and likely topic coverage;
- support publicly accessible HTML and text-extractable PDF sources where practical;
- allow the user to supply known URLs or local source references;
- record inaccessible, duplicate, or failed sources instead of silently omitting failures.

The research adapter should separate search, source inspection, and content storage so the provider can be changed later without rewriting the agent.

#### Competitor TOC analysis and our TOC

The prototype does not create a separate permanent TOC artifact. The approved module/subtopic hierarchy inside the compact Course Model is the course TOC.

That hierarchy must be proposed from four inputs, in this priority order:

1. the approved audience, scope, duration, and constraints in the Course Brief;
2. the approved course outcomes;
3. the competitor TOC coverage-and-sequence analysis;
4. the available approved factual sources.

Competitor frequency is evidence, not a voting rule. A topic appearing in every competitor may still be excluded when it conflicts with the approved scope; a topic absent from competitors may be included when required by the outcomes or when it creates a deliberate differentiator.

The Research Dossier must make the reasoning inspectable through:

- the competitor courses and outline locators;
- extracted outline sections in original order;
- a normalized topic coverage matrix;
- common-core and sequencing observations;
- gaps and differentiation opportunities;
- explicit implications or options for our proposed course structure.

The user reviews these findings before approving the Research Dossier and later sees how they influenced the Course Model proposal. The structure agent must be able to explain whether a proposed module or subtopic came from an approved outcome, recurring competitor coverage, a differentiation decision, source availability, or a combination of these.

Competitor course pages are research evidence for curriculum design. They are not automatically approved grounding sources for learner-facing factual claims. If a competitor page is also useful as a content source, it must appear separately in the candidate-source list and receive explicit human approval like every other source.

**Human decision:** review the candidate list and explicitly approve or reject each source. The user can also request another research pass or add a known source.

**Output:** approved Research Dossier containing competitor outline evidence and the normalized comparison, plus a source store containing approved factual source content or bounded excerpts.

**Failure behavior:** if no adequate source is approved for a factual area, the system offers three choices: research further, reduce that area’s scope, or pause. It does not quietly rely on model memory.

### Stage 4 — Compact Course Model

The structure agent consumes only the approved Brief, Outcomes, Research Dossier, and approved source content. It proposes:

- course metadata;
- ordered modules and subtopics;
- purpose, in-scope, and out-of-scope statements;
- prerequisites and dependencies;
- key concepts;
- coverage requirements;
- approved source assignments.

The proposed hierarchy must include concise structural rationale traceable to the approved outcomes and competitor TOC analysis. The Course Model itself stays compact; detailed competitor outlines and the full comparison matrix remain in the Research Dossier.

The Course Model remains compact. Competitor narratives and source text stay outside it.

**Human decision:** approve or revise modules, subtopics, order, scope, dependencies, and important coverage. Structural changes should not require repeating approved research unless they create an evidence gap.

**Output:** approved Course Model v0.2.

**Failure behavior:** integrity checks reject unknown outcomes, invalid dependencies, duplicate IDs, and any proposed/rejected source reference.

### Stage 5 — Blueprint and per-subtopic choices

The Blueprint agent proposes a practical generation plan using course-wide defaults first. For every subtopic it proposes:

- target learning minutes;
- depth level;
- target word range;
- required concepts;
- example count;
- case depth;
- assessment complexity;
- learner and teacher assets/documents;
- source routing.

The user should not complete a large blank form for every subtopic. The interface first asks for global defaults and then shows exceptions or important subtopics needing a specific decision.

For each subtopic, the user can select among supported assets such as:

- learning objectives;
- course content;
- summary;
- case study;
- important person/profile;
- did-you-know material;
- assessment and answer key;
- activities;
- resources.

Recommended prototype defaults may select learning objectives, course content, summary, and assessment, while leaving specialized assets optional. The recommendation is never a hidden fixed requirement.

**Human decision:** approve global defaults, override depth where necessary, and explicitly select or reject assets per subtopic.

**Output:** approved Blueprint v0.2.

**Failure behavior:** a subtopic with no content asset is flagged for confirmation. Invalid timing/word ranges or source assignments block approval.

### Stage 6 — Whole-course Student Content

The existing Phase 1 generation and verification path is reused, then generalized from one fixed FRM subtopic to every selected subtopic in the approved Blueprint.

Required behavior:

- iterate through all selected subtopic plans;
- generate only assets whose status is `selected`;
- build a deterministic context slice for the current subtopic and asset;
- include only human-approved sources assigned to that subtopic/asset;
- generate Course Content before dependent assets for coherence;
- apply coverage/depth checks and bounded targeted expansion;
- attribute significant factual claims;
- run the separate adversarial verifier;
- allow targeted revision of one asset without regenerating unaffected work;
- cache unchanged calls and resume partial runs.

The phrase “only approved sources” is an enforced rule, not prompt guidance. Rejected and proposed source IDs must be filtered and rejected by integrity checks. The writer must not introduce unsupported significant factual claims from model memory. If approved evidence is insufficient, the asset is marked as needing evidence and the user is returned to research/scope decisions.

**Human decision:** approve the generated package or request changes by asset/subtopic. Verification findings are visible during review.

**Output:** verified Content Package v0.2 covering the selected course scope.

### Stage 7 — Basic Lesson Plan

The lesson-plan agent replaces the current FRM-specific fixture. It asks only for unresolved delivery constraints, including:

- available session count and duration;
- live, self-study, or blended delivery;
- breaks or sequencing constraints;
- teacher emphasis and practical activities.

It maps approved content into sessions with duration, covered subtopics, delivery mode, and concise teacher talking points.

**Human decision:** approve the schedule and live/self-study split.

**Output:** schema-valid Lesson Plan plus a readable Markdown version.

### Stage 8 — Organized prototype output

The prototype writes one understandable folder without requiring the user to inspect internal caches or logs.

```text
courses/<course_id>/
  brief.json
  course_outcomes.json
  research_dossier.json
  course_model.json
  blueprint.json
  content_package.json
  lesson_plan.json
  sources/
    <approved-source-id>.md
  deliverables/
    course_overview.md
    module_<id>/
      subtopic_<id>/
        <selected-asset>.md
    lesson_plan.md
  run_summary.json
```

Markdown is the required rendered format for the four-week acceptance gate because it is deterministic, inspectable, and already allowed by the Content Package schema. Native styled DOCX/PPTX output and SCORM packaging remain extensions unless the core prototype stabilizes early.

## 7. Source-control and evidence rules

These rules are non-negotiable:

1. The research agent may propose sources but may not mark its own proposal as human-approved.
2. Every approved source has a stable ID, locator, content reference, trust note, relevance note, and explicit human decision.
3. Only approved sources appear in the Course Model source registry.
4. Only approved, assigned source content enters generation prompts.
5. Rejected and proposed sources are retained in the Research Dossier for audit but excluded from downstream context.
6. Significant factual claims trace to an approved source and are checked by the verifier.
7. An unavailable source cannot remain silently approved; it is marked unavailable and requires replacement, scope reduction, or an explicit decision.
8. The user can reopen source selection when later stages reveal an evidence gap. Previously approved unrelated artifacts should remain intact where possible.
9. Competitor pages used only for TOC analysis cannot enter learner-content grounding context unless the human separately approves them as factual sources.

## 8. Human-control rules

- The system always distinguishes an agent recommendation from a human decision.
- No consequential stage advances without approval.
- Form-like choices are used for bounded decisions; free text is used for nuance and revision feedback.
- The user can accept recommended defaults quickly.
- The user can inspect why an option was recommended.
- The user is not forced to answer low-impact questions when a safe, visible default exists.
- Per-subtopic controls inherit global choices and store only meaningful overrides.
- Rejection reruns the smallest affected unit: current artifact, subtopic, or asset.

## 9. Technical foundations

### Preserve

- The artifact envelope and orchestrator-owned lifecycle fields.
- Ordered `Step` contracts, approval loops, and disk-based resume behavior.
- Compact Course Model, Blueprint, Content Package v0.2, and stable IDs.
- Deterministic context slicing.
- Phase 1 generation, attribution, verification, coverage, and revision mechanisms.
- Direct model SDK use, local response cache, and token logging.
- Plain files as the prototype system of record.

### Add or replace

- Course Brief v0.2 schema and sparse `subject_request` boundary.
- Provider-independent question and structured-choice representations.
- Terminal interaction renderer and injectable non-interactive test responder.
- Real intake and course-outcomes agents.
- Bounded research adapter and source-content store.
- An expanded Research Dossier contract for extracted competitor outlines, normalized topic coverage, sequence observations, and structural implications (with a schema-version bump if the body contract changes).
- Deterministic source-decision application and approved-source filtering.
- Real Course Model agent.
- Real Blueprint agent with global defaults and per-subtopic overrides.
- Whole-course iteration instead of the fixed `m1_s1` content path.
- Real domain-neutral Lesson Plan agent.
- Deterministic Markdown course-folder renderer.
- End-to-end acceptance harness and run summary.

### Do not add during the prototype

- An agent framework.
- A database.
- A vector store or RAG system.
- Multi-user permissions or collaboration.
- Background queues or distributed workers.
- A browser application.
- General workflow-builder abstractions beyond the two interaction primitives actually needed.

## 10. Reliability requirements

The prototype does not need production operations, but it must be safe to demonstrate and iterate:

- Model and research calls have bounded retries and actionable errors.
- Completed approved artifacts are resumable.
- Individual content assets can fail and retry without discarding completed assets.
- External research is mocked in automated tests.
- One live research run is retained as acceptance evidence.
- Invalid model JSON is retried or rejected with a clear stage error.
- All artifact and cross-reference integrity checks run before approval.
- Secrets remain outside the repository.
- Token/cost logs continue to be recorded.
- The run summary identifies completed, skipped, failed, and pending-review stages.

Parallel generation is not required. Sequential generation with visible progress, caching, and resume is safer for the deadline.

## 11. Course-size and acceptance boundaries

The contracts should not contain a permanent course-size limit. To keep the four-week acceptance run bounded, the primary demonstration course should contain approximately:

- one to two modules;
- four to eight subtopics total;
- a recommended core asset set for each subtopic;
- optional richer assets selected for only the subtopics that benefit from them.

This demonstrates whole-course behavior without turning the final integration test into dozens of expensive, slow model calls. Larger-scale optimization remains later work.

## 12. Acceptance scenarios

### Scenario A — Primary non-FRM course

Start from only “coffee making” or another approved ordinary topic.

The run must demonstrate:

- at least two rounds of relevant clarification;
- outcome selection/editing;
- live scanning of at least three usable competitor TOCs/outlines and a normalized coverage/sequence comparison;
- live candidate factual-source research;
- approving some sources and rejecting at least one;
- proof that the rejected source never enters the Course Model or content context;
- proof that the proposed Course Model explains how outcomes and competitor analysis influenced its hierarchy;
- Course Model approval;
- different asset selections or depth settings across at least two subtopics;
- generation and verification of the selected course content;
- one targeted content revision;
- basic lesson-plan generation;
- organized Markdown output;
- successful resume after stopping the run.

### Scenario B — Domain-neutral smoke test

Use a substantially different small topic. Run at least through approved Course Model and Blueprint, with model/research calls mocked where appropriate. No reusable prompt or source-code edit is allowed for the second subject.

### Automated acceptance

- All existing Phase 1 tests remain green.
- Course Brief, Outcomes, Research Dossier, Course Model, Blueprint, Content Package, and Lesson Plan validate.
- Extracted competitor outlines retain their locators and original ordering, and normalized coverage-matrix references resolve.
- Course Model structural rationale traces to approved outcomes and/or documented competitor findings without embedding the full competitor evidence.
- Rejected source leakage fails deterministically.
- Unselected asset generation fails deterministically.
- Context slices contain only the current node and approved assigned source excerpts.
- Resume skips approved stages and preserves completed assets.
- A research or generation failure produces a recoverable state.
- Final output contains every selected asset and no rejected asset.

## 13. Deliberately deferred

The following are valuable but are not required for the four-week prototype:

- Web/mobile UI and visual form design.
- Production authentication or multiple course directors.
- RAG, embeddings, or semantic retrieval.
- Parallel generation and queue infrastructure.
- Large-course performance optimization.
- Continuous autonomous web monitoring or source freshness refresh.
- Polished DOCX/PPTX templates and pixel-perfect layouts.
- Wiring every generated asset into the existing SCORM converter.
- Comprehensive LMS upload automation.
- Rich tracing dashboards, analytics, and cost-control UI.
- Automated pedagogical-quality judgment across domains.
- Extensive prompt tuning across many subjects.
- Production deployment, security hardening, and operational support.

If time remains after the acceptance path is stable, the priority order for stretch work is:

1. basic native document rendering;
2. SCORM wiring for rendered files;
3. a minimal browser interface using the same question/choice contracts;
4. limited parallel generation.

Stretch work must not displace completion, resume, source enforcement, or the end-to-end acceptance run.

## 14. Principal risks and controls

| Risk | Control in this plan |
|---|---|
| The agent asks too many questions | Ask only unresolved, high-impact questions in small rounds; use visible defaults and global settings. |
| Human choice becomes free-text prompt engineering | Use typed questions and deterministic multi-select application. |
| Rejected sources leak downstream | Filter by approved IDs in code and add negative integrity tests. |
| Research quality varies by topic | Use bounded auditable research, manual source addition, and a stop-on-insufficient-evidence path. |
| Competitor outlines are partial or inaccessible | Target five to eight offerings, require at least three usable public outlines for acceptance, record gaps, and never infer hidden TOC content. |
| Source fetching consumes the schedule | Support accessible HTML/text PDFs first; retain failed locators; do not build a universal crawler. |
| Course Model becomes an evidence dump | Keep full research and source content outside the compact schema. |
| Per-subtopic forms become exhausting | Propose course-wide defaults, ask only for exceptions, and provide recommended asset sets. |
| Whole-course generation becomes slow or costly | Bound the acceptance course, generate selected assets only, cache, resume, and stay sequential. |
| Existing FRM assumptions survive | Static prompt checks and a second unrelated subject smoke test. |
| Packaging absorbs the final week | Require Markdown output; treat native documents and SCORM wiring as stretch work. |
| Two developers block each other | Lock shared contracts before implementation and separate platform/interaction work from agent/content work in the later sprint plan. |

## 15. Decisions requested during review

The project owner should approve or change the following before sprint planning:

1. **Prototype output:** Markdown course folder is the required gate; native DOCX/PPTX and SCORM are stretch goals.
2. **Acceptance size:** primary demonstration course is limited to roughly one to two modules and four to eight subtopics.
3. **Default asset recommendation:** learning objectives, course content, summary, and assessment are proposed by default; all other assets remain optional per subtopic.
4. **Primary acceptance topic:** “coffee making” remains the default unless another topic is selected.
5. **Research boundary:** accessible public HTML and text-extractable PDFs plus manually supplied sources are sufficient for the prototype.
6. **Interaction surface:** structured terminal questions and multi-select choices satisfy the prototype; browser UI is deferred.
7. **Evidence behavior:** when approved sources do not support the requested scope, the system must pause for more research or scope reduction rather than generate unsupported factual claims.
8. **Lesson-plan scope:** a basic session plan and Markdown teacher guide are required; richer teacher assets are later work.
9. **Competitor scan boundary:** target five to eight relevant offerings and require at least three usable public TOCs/outlines for the acceptance run; use the comparison as evidence, not as an automatic majority vote for our TOC.
10. **Questioning model:** use deterministic required/conditional questionnaires plus a maximum of three validated agent-generated follow-ups per round; do not let the agent invent the entire interview.

## 16. What happens after approval

Once this document is approved:

1. Convert the capability sequence into four one-week sprints with an integration gate at the end of every sprint.
2. Break each capability into bounded implementation, contract, test, and acceptance tasks.
3. Assign every task to one of the two developers while minimizing shared-file contention.
4. Identify the critical path, explicit stretch tasks, and the first tasks to drop if schedule risk appears.
5. Add estimates and dependencies only after the scope above is locked.

The scope is approved. Execution is governed by `Course_Builder_Four_Week_Sprint_Plan.md`; material scope changes return here for explicit approval rather than entering a sprint silently.
