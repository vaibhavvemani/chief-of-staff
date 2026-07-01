# Assessment Generation Prompt

You are writing the Assessment asset for the Course Builder pipeline.

## Objective

Create a self-assessment for the asset identified by `target_asset` and the
`focus_subtopic` in `CONTEXT_JSON`. Test learner understanding of the
already-generated Course Content at the configured level of difficulty.

Follow the configured question count, question types, scoring or weighting,
audience, format, `coverage_requirements`, `depth_budget`, and other
asset-specific assessment instructions. Balance recall, explanation, and
application only as the configured depth requires. Every question must assess
material actually taught in the Course Content.

Produce two things in one JSON object:

1. `content` — the learner-facing assessment with questions only.
2. `solution` — a teacher-only, Markdown-formatted answer key containing a
   complete model answer for every question.

Use matching question labels in `content` and `solution`. Keep answers out of
learner-facing content.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named people or organizations, quotations, research findings, and other
  independently verifiable assertions.
- Each significant factual claim should cite one valid approved `source_id`.
- Use `source_id: null` for question framing, pedagogical scaffolding, clearly
  hypothetical scenarios, or transitions that assert no verifiable fact.
- Do not invent source IDs or use sources that are not approved for this asset.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing questions.
- The teacher-only `solution` may mention claim or source IDs when useful, but it
  must remain readable prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Assessment
asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, question counts, or subject names.

The `solution` field is required and must be a non-empty string containing the
teacher-facing answer key.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Assess exactly what this Course Content teaches, at the depth it teaches it.
Do not ask about absent topics or contradict its factual assertions. Ensure each
model answer is consistent with it.

```text
{{COURSE_CONTENT}}
```

## Context

```json
{{CONTEXT_JSON}}
```

## Approved Source Texts

{{SOURCE_TEXTS}}

{{FEEDBACK_SECTION}}
