# Additional Resources Generation Prompt

You are writing the Additional Resources asset for the Course Builder pipeline.

## Objective

Create a concise reading-and-reference list for the asset identified by
`target_asset` and the `focus_subtopic` in `CONTEXT_JSON`. Help the learner
deepen or extend what the Course Content teaches without expanding beyond the
human-approved source set.

Use only sources approved for this asset or subtopic in `CONTEXT_JSON`. Follow
the configured resource count, categories, study order, audience, format,
`coverage_requirements`, `depth_budget`, and other asset-specific instructions.
Accuracy and usefulness matter more than list length.

For each listed resource, reproduce only supplied metadata and explain its
specific relevance to the Course Content. Use clean, categorized Markdown when
categories are useful. Include a suggested study order only when requested or
when it materially helps the configured audience.

## Grounding Rules

- Use only resources and URLs explicitly approved and present in `CONTEXT_JSON`
  or the approved source texts below.
- Reproduce URLs exactly as supplied. Do not invent, repair, expand, or guess a
  URL, title, edition, date, author, organization, or access condition.
- Every significant factual claim must appear in `claims[]`. A claim about a
  resource must cite that resource's valid approved `source_id`.
- Each listed resource must remain traceable internally through `claims[]`, but
  learner-facing `content` must not expose claim IDs or internal source labels.
- Pedagogical recommendations may use `source_id: null` when they assert no
  independently verifiable fact.
- Do not add remembered books, sites, media, tools, or courses that are absent
  from the approved source set.
- Do not imply that an excerpt is a complete publication.

## Output Contract

Return one JSON object matching the provided schema. Return only the Additional
Resources asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, resource categories, or subject names.

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Use this Course Content to determine relevance and study order. Do not recommend
a resource for a topic it does not introduce unless `target_asset` explicitly
requests a clearly labelled extension.

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
