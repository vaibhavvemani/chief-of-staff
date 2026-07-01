# Learning Objectives Generation Prompt

You are writing the Learning Objectives asset for the Course Builder pipeline.

## Objective

Create measurable learning objectives for the `focus_subtopic` and the asset
identified by `target_asset` in `CONTEXT_JSON`. Each objective must describe
what a learner will be able to do after studying the Course Content, using
observable action verbs appropriate to the configured audience and depth.

Use the number, taxonomy level, formatting, and other asset-specific instructions
in `target_asset` when supplied. The objectives must collectively map to the
approved `coverage_requirements` and `depth_budget`, but they must test only what
the already-generated Course Content actually teaches. Do not introduce a new
topic simply because it appears in a source.

Format `content` as concise Markdown, normally a numbered list unless
`target_asset` requests another structure. Write original objective statements;
do not reproduce benchmark wording.

## Grounding Rules

- Use only the approved source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include dates, figures, named events, named people
  or organizations, research findings, and other independently verifiable
  assertions.
- Each significant factual claim should cite one valid approved `source_id`.
- Objective language and pedagogical framing normally use `source_id: null` and
  need not be represented as claims unless they assert a specific fact.
- Do not invent source IDs or use sources that are not approved for this asset.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Learning
Objectives asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, or subject names.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Condition on this asset. The objectives must reflect exactly what it teaches,
at the depth it teaches it, without contradiction or unsupported extension.

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
