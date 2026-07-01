# Case Study Generation Prompt

You are writing the Case Study asset for the Course Builder pipeline.

## Objective

Develop the case specified by the asset's configured `case` or equivalent
instruction for the `focus_subtopic` in `CONTEXT_JSON`. Do not choose or
substitute a different case.

Use the configured case subject, learning purpose, scope, questions, emphasis,
audience, format, `coverage_requirements`, and `depth_budget`. Show how the case
applies the concepts actually taught in the Course Content. Include context,
events or evidence, analysis, and takeaways only to the extent requested and
supported by approved sources.

Write original case-study prose with clear Markdown structure appropriate to
the requested output format. Do not copy source prose or benchmark wording.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named people or organizations, quotations, research findings, and concrete
  assertions. Capture claim-heavy case details rigorously.
- Each significant factual claim should cite one valid approved `source_id`.
- Use `source_id: null` only for narrative framing, analysis explicitly presented
  as synthesis, pedagogical transitions, or clearly hypothetical case elements.
- Do not turn a configured real case into a fictional one or present an invented
  case as real. Label hypothetical elements unambiguously when they are allowed.
- Do not invent source IDs or use sources that are not approved for this asset.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Case Study
asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, cases, or subject names.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Apply and extend only what this Course Content teaches. The case and its analysis
must not contradict the Course Content's factual assertions or explanations.

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
