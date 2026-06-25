# Learning Objectives Generation Prompt

You are writing the Learning Objectives asset for the Course Builder pipeline.

## Objective

Create 4–8 measurable learning objectives for the target subtopic. Each
objective should describe what a learner will be able to **do** after studying
the Course Content, using Bloom's Taxonomy action verbs (e.g. define, explain,
distinguish, apply, analyse, evaluate). The objectives must map directly to what
the Course Content teaches — do not introduce topics that are not covered there.

Do not copy the manual benchmark text. Write original objectives based on the
provided Domain Model, curated source texts, and the already-generated Course
Content.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named institutions, regulatory facts, and concrete assertions.
- Each significant factual claim should cite one source with `source_id`.
- Use `source_id: null` for framing, synthesis, pedagogical transitions, or
  objective-statement language that does not assert a verifiable fact.
- Do not invent source IDs. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the prose.
- Learning objectives are mostly framing, so few or no claims are expected; only
  attribute objective language if it asserts a specific fact (e.g. a date, a
  statistic, a named institution).

## Required Coverage

The objectives must collectively address, at minimum:

- defining financial risk and its four core categories (credit, liquidity,
  market, operational),
- distinguishing risk from Knightian uncertainty,
- explaining why financial risk categories interact and can amplify each other,
- applying the Lehman Brothers collapse as an example of interacting risk
  categories,
- describing the role of measurement and management judgment in financial risk.

Format the `content` as a Markdown list of numbered objectives. Each objective
should start with an action verb.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Learning Objectives asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_lo`
- `type`: `learning_objectives`
- `title`: `Learning Objectives`
- `format`: `docx`
- `file`: `null`
- `status`: `done`

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — do not contradict or merely repeat it)

The following is the Course Content asset that was already generated for this
subtopic. Your Learning Objectives must reflect **exactly** what this content
teaches. Do not reference topics that are absent from it, and do not contradict
any of its factual assertions.

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
