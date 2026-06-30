# Important Person Generation Prompt

You are writing the Important Person asset for the Course Builder pipeline.

## Objective

Create a compact, slide-ready profile of **Frank H. Knight** that explains why
his risk-versus-uncertainty distinction matters to the target subtopic. The
asset should feel like the manual course's “Famous Personality” feature: a
memorable human entry point, a crisp explanation of the person's central idea,
and an explicit bridge back to financial-risk practice.

Do not write a general biography and do not copy the manual benchmark. Use the
provided Domain Model, curated source texts, and already-generated Course
Content. Include only biographical details that the curated sources support.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include dates, publications, quotations,
  biographical details, named models, and assertions about Knight's theory.
- Each significant factual claim should cite one source with `source_id`.
- Use `source_id: null` only for synthesis, framing, or pedagogical transitions
  that assert no independently verifiable fact.
- Do not invent source IDs, quotations, dates, credentials, institutions, or
  life events. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the learner-facing prose.

## Required Structure

Write concise Markdown suitable for approximately three slides:

1. **Frank Knight — The Foundation of Risk Theory** — introduce Knight and the
   central distinction, with no unsupported biography.
2. **Risk vs. Uncertainty** — contrast measurable risk with Knightian
   uncertainty using one financial example for each.
3. **Why This Matters for Financial Risk Management** — cover model boundaries,
   the measurable-risk zone, and why management judgment remains necessary.

Use short paragraphs and scannable bullets. The asset should complement the
Course Content rather than repeat whole sections from it.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Important Person asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_person`
- `type`: `important_person`
- `title`: `Frank Knight — The Foundation of Risk Theory`
- `format`: `pptx`
- `file`: `null`
- `status`: `done`

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — do not contradict or merely repeat it)

The profile must reinforce the way this Course Content explains measurable risk,
uncertainty, quantitative tools, and management judgment. Do not introduce a
definition or example that conflicts with it.

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
