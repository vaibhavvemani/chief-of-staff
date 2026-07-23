# Course Builder NC-110 Release Validation Evidence

> **Evidence date:** 2026-07-23
> **Checkpoint state:** NC-1101 through NC-1105 are independently verified and all
> package exit gates are green. This does not complete NC-120 or the development cycle.

## Result

The deterministic, recovery, negative, accessibility, credentialed live, and
domain-neutral regression paths pass. The bounded live course reached an approved
Package with:

- `operator_status: complete`;
- 10 selected, generated, summarized, reviewed, and rendered learner assets;
- zero unsupported, ungrounded, or unattributed hard blockers;
- 93 supported and 6 partial nonblocking findings retained for human visibility;
- 10 current human review approvals;
- three approved content-bearing sources and zero rejected-source leakage;
- successful referential integrity;
- the deterministic Markdown Package implementation reported explicitly.

Canonical ignored evidence:

- `output/playwright/live/nc110-live-acceptance-evidence.json`
- `output/playwright/live/nc110-live-package-approved.png`
- `output/playwright/live/report/`

## Package exit gate

| Gate | Result |
|---|---:|
| Full Python regression | 468 passed; one existing Starlette deprecation warning |
| Ruff | passed |
| Frontend unit/component suite | 92 passed |
| Frontend production build | passed; existing chunk-size advisory only |
| Deterministic Chromium acceptance | 13 passed in 1.2 minutes |
| Credentialed live Chromium acceptance | 1 passed |
| NC-1105 focused domain-neutral regression | 70 passed |
| `git diff --check` | passed |
| Generated `tsconfig.app.tsbuildinfo` | restored |

The deterministic browser suite covers the complete operator journey; reopen and
downstream rerun; an actual post-start safe failure/retry; actual Uvicorn child-process
restart recovery; refresh/navigation
rediscovery; concurrent mutation rejection; source leakage, blocker approval,
read-only mutation, and traversal rejections; real Markdown rendering; Course Model,
Blueprint, and Lesson Plan decisions; source repair; hard-blocker truth; target-only
repair; and Content review closure.

## Credentialed live course

| Field | Evidence |
|---|---|
| Course ID | `studio-live-pilot` |
| Subject | Indoor herb gardening for apartment beginners |
| Provider/model | Anthropic / `claude-opus-4-8` |
| Boundary | five subtopics, exactly ten selected learner assets |
| Live stages | Outcomes, Research, Course Model, Blueprint, Student Content, independent Verification, Lesson Plan |
| Brief | required typed conditional question completed; no agent follow-up or synthesis was requested, so no Brief model call was required |
| Package | deterministic Markdown renderer |
| Final state | 8/8 approved; all release checks passed |

The final browser pass reused the completed scoped live revision instead of paying for
the same evidence again. It still revalidated the current artifacts, source boundary,
asset reconciliation, Content review, raw Markdown preview, integrity, diagnostics,
and Package approval in Chromium.

### Source decision

Approved and content-bearing:

- Penn State Extension, `https://extension.psu.edu/growing-herbs-indoors`
- Royal Horticultural Society, `https://www.rhs.org.uk/herbs/containers`
- University of Maryland Extension,
  `https://extension.umd.edu/resource/growing-herbs-containers-and-indoors`

The originally considered University of Minnesota page returned HTTP 403 through the
production fetcher. The whole source-decision transaction was rejected without a
partial registry write. University of Maryland was then verified through the same
fetcher and approved. Competitor-only course-outline seeds remained structural research
inputs and never entered grounding routes.

The final registry contains three approved source IDs and seven rejected candidate IDs.
Every Course Model, Blueprint, Content claim, and rendered source reference resolves
only to the approved set.

## Model-call and cost ledger

The safe model-call log contains 76 records for this course:

- 63 paid successful calls;
- 11 cache hits;
- two logged zero-token provider failures;
- 705,509 known input tokens;
- 96,134 known output tokens;
- **$5.930895 known estimated cost** using the repository pricing table.

| Stage | Records | Paid | Cache | Logged failures | Input tokens | Output tokens | Known cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Outcomes | 4 | 2 | 0 | 2 | 2,805 | 1,471 | $0.050800 |
| Research | 4 | 4 | 0 | 0 | 8,725 | 368 | $0.052825 |
| Course Model | 1 | 1 | 0 | 0 | 2,663 | 995 | $0.038190 |
| Blueprint | 1 | 1 | 0 | 0 | 7,940 | 502 | $0.052250 |
| Content + Verification | 64 | 54 | 10 | 0 | 680,995 | 92,668 | $5.721675 |
| Lesson Plan | 2 | 1 | 1 | 0 | 2,381 | 130 | $0.015155 |

Runtime events contain 79 call starts, 74 completions, and two explicit provider
failures. Three starts lack a completion:

1. an Outcomes job interrupted during an early browser-harness race; provider billing
   is unknown;
2. the first verifier attempt, which failed locally during Anthropic schema
   transformation before a request was sent and therefore has no provider cost;
3. a scoped Content revision interrupted during a later harness race; provider billing
   is unknown.

The two interrupted calls are not included in the known token/cost totals. The ledger
therefore reports the precise locally recorded estimate, not a claim about the final
provider invoice.

## Live corrections and recovery evidence

The resumed live journey exposed and corrected real defects without silent fallback:

1. Two pre-credit Outcomes attempts failed atomically with zero tokens and zero cost.
2. An early in-flight Outcomes job was recovered as `InterruptedJob`.
3. Three bounded Research planner attempts failed the three-outline gate. Generic
   learning-outcome parsing, fallback query ranking, and operator seed separation were
   corrected and regression-tested.
4. The unavailable Minnesota source proved atomic source-decision failure before the
   Maryland substitute was approved.
5. The first Content verification attempt failed locally because the Anthropic wire
   schema lacked the root string type on the `support` enum. The transformer contract
   was corrected and tested against the real SDK transformer.
6. A repair command with an explicit asset plus verifier context incorrectly expanded
   to another flagged asset. The scope guard rejected the transaction atomically.
   Revision parsing now keeps explicit selectors exact.
7. Five bounded Resources repair runs, within 13 successful Content repair jobs,
   exposed unstable URL/meta-claim behavior. Resources prompts now distinguish
   substantive claims from source metadata, and deterministic verification permits
   metadata only for claims strictly about the registered title, publisher, type, or
   URL.
8. A final target-only Resources repair cleared all hard blockers while preserving the
   other nine learner assets.
9. Approved-state scoped revision recovery now waits on the exact accepted job ID.
   Failed scoped revisions preserve normal target-only retry capabilities rather than
   forcing a whole-stage rerun.
10. Package summary generation now reconciles operation-scoped progress against the
    complete current Content Package, ignores completed operation sentinels, retains
    real failed/pending units, and reports a newly rendered manifest as completed while
    its envelope remains the human approval gate.

The final run summary contains exactly the ten canonical asset IDs and reports
`operator_status: complete`.

## Bounds and safety

- All live starts required explicit `live` mode and provider readiness.
- No provider failure selected deterministic output.
- Maximum recorded input sizes remained below the configured stage limits; the largest
  Content call was 48,096 characters.
- Generation and verification used only routed, approved excerpts plus bounded source
  metadata.
- Source selection remained atomic and content-bearing.
- The final Content activity shows both `content_generation` and `verification` call
  roles.
- Package output remained raw-HTML-disabled Markdown.
- Runtime courses, rendered output, reports, call logs, and cache entries remain
  git-ignored.

## NC-1105 domain-neutral regression

The injected live-stage contract suite passes across:

- indoor herb gardening for apartment beginners; and
- everyday bicycle maintenance for new commuters.

It covers live Brief synthesis, Outcomes, Research, Course Model, Blueprint, Content,
Verification, Lesson Plan, grounding, selected-asset control, revision scope, and
no-fallback behavior on both topics. The deterministic second-topic course smoke and
generic research/verification/prompt tests also pass. A production-code scan found no
`studio-live-pilot`, apartment-herb, or named-source literal in `agents/`, `api/`,
`prompts/`, `research_adapter.py`, `steps.py`, `llm.py`, or the implementation
registry. Subject-specific values remain confined to the opt-in acceptance fixture.

## Remaining limitations

- The first live Content draft was not learner-ready and required repeated bounded
  repair. The trust loop worked, but live output quality remains variable.
- Six partial findings remain intentionally visible for human judgment; they are not
  release blockers.
- Two interrupted, transmitted-or-possibly-transmitted calls have unknown provider
  billing outside the local estimate.
- Estimated cost uses the repository pricing table and should be reconciled with the
  provider invoice if exact accounting is required.
- Package output is Markdown; native document formats, SCORM, hosting, authentication,
  and collaboration remain deferred.
- NC-1202 must be performed unaided by the real nontechnical course director. This
  evidence does not simulate or claim that pilot.

Nothing in this package was pushed.
