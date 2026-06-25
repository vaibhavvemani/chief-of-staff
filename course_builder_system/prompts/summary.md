# Summary Generation Prompt

You are writing the Summary asset for the Course Builder pipeline.

## Objective

Create a concise, accurate summary of the key takeaways from the Course Content
for the target subtopic. The summary should consolidate what was taught — it is
a study-aid recap, not a preview. A postgraduate/intermediate Financial Risk
Management learner should be able to use it to review the core ideas after
reading the full Course Content.

Do not copy the manual benchmark text. Write original summary prose based on the
provided Domain Model, curated source texts, and the already-generated Course
Content.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named institutions, regulatory facts, and concrete assertions about Lehman or
  risk categories.
- Each significant factual claim should cite one source with `source_id`.
- Use `source_id: null` for synthesis, framing, or pedagogical transitions that
  do not need factual support.
- Do not invent source IDs. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the prose.

## Required Coverage

The summary must recap, at minimum:

- what financial risk is and why it matters,
- the distinction between risk and Knightian uncertainty,
- the four core risk categories (credit, liquidity, market, operational) and
  their defining characteristics,
- how risk categories can interact and cascade,
- the Lehman Brothers collapse as the applied example showing how multiple risk
  categories combined into a crisis,
- the role of measurement and management judgment.

Use concise Markdown prose with headings or bullet points. Aim for clarity and
brevity — this is a review aid, not a second Course Content.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Summary asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_summary`
- `type`: `summary`
- `title`: `Summary`
- `format`: `docx`
- `file`: `null`
- `status`: `done`

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — do not contradict or merely repeat it)

The following is the Course Content asset that was already generated for this
subtopic. Your Summary must accurately recap what **this** content taught.
Do not introduce new topics not covered in the Course Content, and do not
contradict any of its factual assertions.

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
