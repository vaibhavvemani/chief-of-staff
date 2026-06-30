# Activities Generation Prompt

You are writing the Activities asset for the Course Builder pipeline.

## Objective

Create five practical learner activities that make the target subtopic usable,
not merely memorable. The activities should move from classification and
reflection to applied analysis, mirroring the manual course's concise activity
sheet while improving instructions, expected outputs, and alignment to the
already-generated Course Content.

Do not copy the manual benchmark. Base every activity on concepts actually
taught in the Course Content. The activities are learner-facing tasks only;
do not include model answers, grading solutions, or a `solution` field.

## Grounding Rules

- Use only the curated source texts below for factual claims embedded in the
  activity setup.
- Every significant factual claim must appear in `claims[]`.
- Each significant factual claim should cite one source with `source_id`.
- Instructions, hypothetical scenarios, reflection questions, and learner
  deliverables normally need no factual attribution and may use
  `source_id: null` only if represented as claims at all.
- Do not invent current-news facts. You may ask the learner to select a recent
  article, but do not manufacture or summarize one.
- Do not invent source IDs. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the learner-facing text.

## Required Structure

Write Markdown with exactly five clearly numbered activities:

1. **Risk Mapping** — classify market, credit, liquidity, and operational risks
   for a learner-selected organization.
2. **Scenario Diagnosis** — trace how at least two risk categories can interact
   and amplify one another.
3. **Risk vs. Uncertainty Reflection** — separate measurable exposures from
   judgment-heavy uncertainty.
4. **Evidence-Based News Analysis** — apply the framework to a learner-selected
   recent article without the generated asset asserting current facts.
5. **Lehman Case Reflection** — use what the Course Content taught to argue
   which risk interaction was most consequential and whether the failure was
   mainly quantitative, managerial, or both.

For each activity include: a short purpose, 2–5 action steps, and a concrete
deliverable or word-count/format expectation. Keep the full sheet practical and
scannable; avoid turning it into another assessment quiz.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Activities asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_activities`
- `type`: `activities`
- `title`: `Activities`
- `format`: `docx`
- `file`: `null`
- `status`: `done`

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — test only what it teaches)

Every activity must be answerable using this Course Content plus learner-chosen
examples. Do not require concepts, calculations, or frameworks absent from it.

```text
{{COURSE_CONTENT}}
```

## Context

```json
{{CONTEXT_JSON}}
```

## Curated Source Texts

{{SOURCE_TEXTS}}

{{FEEDBACK_SECTION}}
