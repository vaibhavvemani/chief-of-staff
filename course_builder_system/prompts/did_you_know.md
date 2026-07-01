# Did You Know Generation Prompt

You are writing the Did You Know asset for the Course Builder pipeline.

## Objective

Create a compact, learner-facing feature for the asset identified by
`target_asset` and the `focus_subtopic` in `CONTEXT_JSON`. Build the feature
around only the editorial `hook` or equivalent asset-specific instruction
supplied in the context; do not invent a replacement hook.

Explain why the configured hook is surprising, useful, or memorable and connect
it directly to the Course Content. Follow the supplied angle, emphasis, length,
format, audience, `coverage_requirements`, and `depth_budget`. Prefer a small
number of well-supported points to a broad unsupported detour.

Use a strong headline and concise, scannable Markdown appropriate to the
requested output format. Complement the Course Content rather than retelling it.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include dates, figures, historical trends, named
  people or organizations, quotations, research findings, and other
  independently verifiable assertions.
- Each significant factual claim should cite one valid approved `source_id`.
- Use `source_id: null` only for synthesis, framing, or pedagogical transitions
  that assert no independently verifiable fact.
- Do not invent source IDs, statistics, quotations, milestones, reporting lines,
  mandates, or examples.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Did You
Know asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, hooks, or subject names.

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Connect the configured hook to what this Course Content teaches. Do not
contradict it or introduce an unrelated theme.

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
