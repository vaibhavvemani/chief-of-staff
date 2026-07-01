# Course Content Generation Prompt

You are writing the Course Content asset for the Course Builder pipeline.

## Objective

Create the complete Course Content asset identified by `target_asset` for the
`focus_subtopic` in `CONTEXT_JSON`. Teach the approved subtopic clearly at the
audience, level, and depth specified in the context.

Treat the approved subtopic outline, `coverage_requirements`, and `depth_budget`
as the content contract. Cover every required item, preserve the approved scope
and sequence, and allocate detail according to the depth budget. Do not add a
fixed subject-matter syllabus of your own. Use the asset-specific instructions
in `target_asset` when supplied.

Write original course prose based on the supplied context and approved source
texts. Structure it with useful Markdown headings so it can later be converted
to the format requested by `target_asset`.

## Depth and Completeness

- Satisfy every approved coverage requirement with explanation proportionate to
  its configured depth, not merely a mention.
- Follow any configured target learning time, section allocation, examples,
  exercises, case depth, or word-range guidance in `depth_budget`.
- Treat a word range as a guardrail, not permission to pad the asset. Prefer
  substantive explanation, examples, connections, and application.
- If a required concept cannot be supported by an approved source, do not invent
  facts. Make the limitation visible in the asset's claims or revision response.
- When revision feedback is supplied, make the requested targeted changes while
  preserving approved material that the feedback does not challenge. Recheck
  coverage and depth after revising.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named people or organizations, quotations, research findings, and other
  independently verifiable assertions.
- Each significant factual claim should cite one valid approved `source_id`.
- Use `source_id: null` only for synthesis, framing, pedagogical transitions, or
  clearly hypothetical examples that do not need factual support.
- Do not invent source IDs or use sources that are not approved for this asset.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Course
Content asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, or subject names.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Context

```json
{{CONTEXT_JSON}}
```

## Approved Source Texts

{{SOURCE_TEXTS}}

{{FEEDBACK_SECTION}}
