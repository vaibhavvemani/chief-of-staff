# Summary Generation Prompt

You are writing the Summary asset for the Course Builder pipeline.

## Objective

Create an accurate study-aid summary for the `focus_subtopic` and the asset
identified by `target_asset` in `CONTEXT_JSON`. Consolidate what the Course
Content taught; do not turn the summary into a preview or a second full lesson.

Recap the approved `coverage_requirements` in proportion to the configured
`depth_budget` and the emphasis present in the Course Content. Follow any
asset-specific length, format, emphasis, or audience instructions in
`target_asset`. Do not introduce topics or facts absent from the Course Content.

Use concise, scannable Markdown appropriate to the requested output format.
Write original summary prose rather than reproducing benchmark wording.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named people or organizations, quotations, research findings, and other
  independently verifiable assertions.
- Each significant factual claim should cite one valid approved `source_id`.
- Use `source_id: null` only for synthesis, framing, or pedagogical transitions
  that do not need factual support.
- Do not invent source IDs or use sources that are not approved for this asset.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Summary
asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, or subject names.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Accurately recap this Course Content. Do not contradict it, merely copy it, or
add topics it does not teach.

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
