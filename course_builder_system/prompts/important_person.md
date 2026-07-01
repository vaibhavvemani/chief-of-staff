# Important Person Generation Prompt

You are writing the Important Person asset for the Course Builder pipeline.

## Objective

Create a compact, learner-facing profile for the asset identified by
`target_asset` and the `focus_subtopic` in `CONTEXT_JSON`. Profile only the
person specified by the asset's configured `person` or equivalent instruction;
do not select or substitute a different person.

Use the configured angle, central contribution, bridge to the subtopic,
audience, format, and length when supplied. The profile should provide a
memorable human entry point while remaining directly useful to the approved
`coverage_requirements` and `depth_budget`. It should complement the Course
Content rather than reproduce whole sections from it.

Do not write an unfocused biography. Include only biographical details and
attributed ideas supported by approved sources. Use concise, scannable Markdown
appropriate to the requested output format.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include dates, publications, quotations,
  biographical details, affiliations, named works or ideas, and attributed
  contributions.
- Each significant factual claim should cite one valid approved `source_id`.
- Use `source_id: null` only for synthesis, framing, pedagogical transitions, or
  clearly hypothetical examples that assert no independently verifiable fact.
- Do not invent source IDs, quotations, dates, credentials, affiliations, works,
  life events, or attributed ideas.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Important
Person asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, people, or subject names.

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Connect the configured person to what this Course Content teaches. Do not
contradict its explanations or introduce an unsupported contribution.

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
