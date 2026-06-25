# Assessment Generation Prompt

You are writing the Assessment asset for the Course Builder pipeline.

## Objective

Create a self-assessment that tests learner understanding of the Course Content
for the target subtopic. The assessment should contain a mix of conceptual and
applied questions — both testing recall of definitions/distinctions and requiring
application (e.g. diagnosing risk categories in the Lehman Brothers case).

You must produce **two things** in one JSON object:

1. `content` — the learner-facing assessment (questions only, no answers).
2. `solution` — a teacher-only answer key (string, Markdown formatted) that
   provides full model answers with grounding for every question. This field is
   teacher-only and must NOT appear in the learner-facing `content`.

Do not copy the manual benchmark text. Write original questions and solutions
based on the provided Domain Model, curated source texts, and the
already-generated Course Content.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named institutions, regulatory facts, and concrete assertions.
- Each significant factual claim should cite one source with `source_id`.
- Use `source_id: null` for question framing, pedagogical scaffolding, or
  transitions that assert no verifiable fact.
- Do not invent source IDs. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the question prose.
- The `solution` field may reference claim IDs or source IDs for internal
  clarity, but should also be readable prose.

## Required Coverage

The assessment must include questions that cover, at minimum:

- defining financial risk (conceptual),
- distinguishing the four core risk categories (credit, liquidity, market,
  operational),
- the distinction between risk and Knightian uncertainty,
- the Lehman Brothers collapse as an applied case: identifying which risk
  categories were at play and how they interacted,
- the role of measurement and management judgment.

Include at least 5 and at most 10 questions. Mix question types (short answer,
multiple choice, scenario-based). Format `content` as Markdown.

The `solution` must provide a complete model answer for every question in
`content`. Format it as Markdown with question labels matching those in
`content`.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Assessment asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_assess`
- `type`: `assessment`
- `title`: `Assessment Quiz: Nature of Financial Risk`
- `format`: `pptx`
- `file`: `null`
- `status`: `done`

The `solution` field is **required** and must be a non-empty string containing
the teacher-facing answer key.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — do not contradict or merely repeat it)

The following is the Course Content asset that was already generated for this
subtopic. Your Assessment must test **exactly** what this content taught. Do not
ask about topics absent from the Course Content, and do not contradict any
factual assertions it makes. The `solution` must be consistent with the Course
Content's explanations.

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
