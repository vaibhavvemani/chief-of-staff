# Course Content Generation Prompt

You are writing the Course Content asset for the Course Builder pipeline.

## Objective

Create the full Course Content asset for the target subtopic. This is the
anchor asset for the rest of the content package, so it must teach the complete
body of knowledge clearly and deeply enough for a postgraduate/intermediate
Financial Risk Management learner.

Do not copy the manual benchmark text. Write original course prose based on the
provided Domain Model and curated source texts.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named institutions, regulatory facts, and concrete assertions about Lehman or
  risk categories.
- Each significant factual claim should cite one source with `source_id`.
- Use `source_id: null` only for synthesis, framing, or pedagogical transitions
  that do not need factual support.
- Do not invent source IDs. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the prose.

## Required Teaching Coverage

Cover, at minimum:

- the purpose of Financial Risk Management,
- what financial risk means,
- why financial risk matters to firms and institutions,
- the distinction between risk and Knightian uncertainty,
- why Financial Risk Management works mainly in the measurable-risk zone,
- why measurement enables but does not replace management judgment,
- credit risk,
- liquidity risk,
- market risk,
- operational risk,
- how risk categories interact in layers,
- the Lehman Brothers collapse as an applied example of interacting market,
  liquidity, leverage/funding, and governance/risk-management failures.

Use headings and Markdown structure suitable for later conversion to slides or
trainer-facing content. The output should be comprehensive: comparable to or
deeper than the manual Course Content benchmark.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Course Content asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_cc`
- `type`: `course_content`
- `title`: `Nature of Financial Risk`
- `format`: `pptx`
- `file`: `null`
- `status`: `done`

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Context

```json
{{CONTEXT_JSON}}
```

## Curated Source Texts

{{SOURCE_TEXTS}}

{{FEEDBACK_SECTION}}
