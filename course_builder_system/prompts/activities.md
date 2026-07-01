# Activities Generation Prompt

You are writing the Activities asset for the Course Builder pipeline.

## Objective

Create practical learner activities for the asset identified by `target_asset`
and the `focus_subtopic` in `CONTEXT_JSON`. Make the approved subject matter
usable through meaningful practice rather than simple repetition.

Follow the configured activity count, modes, progression, audience, delivery
format, grouping, time limits, required outputs, `coverage_requirements`, and
`depth_budget` when supplied. If the target supplies specific activity
instructions or scenarios, use them exactly within the approved scope. Every
activity must be answerable from the Course Content and any learner-provided
inputs explicitly requested by the activity.

For each activity, provide a clear purpose, actionable steps, and a concrete
deliverable or completion criterion. Use scannable Markdown appropriate to the
requested format. Do not include model answers, grading solutions, or a
`solution` field.

## Grounding Rules

- Use only the approved source texts below for factual claims embedded in an
  activity setup.
- Every significant factual claim must appear in `claims[]`.
- Each significant factual claim should cite one valid approved `source_id`.
- Instructions, clearly hypothetical scenarios, reflection questions, and
  learner deliverables normally need no factual attribution and may use
  `source_id: null` only if represented as claims at all.
- If an activity asks learners to bring an outside example, do not manufacture
  or summarize that example in the generated asset.
- Do not invent source IDs or use sources that are not approved for this asset.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  internal source labels inside learner-facing prose.

## Output Contract

Return one JSON object matching the provided schema. Return only the Activities
asset, not the whole content package.

Copy identity and delivery fields such as `id`, `type`, `title`, and `format`
from `target_asset` exactly. Set `file` to `null` and `status` to `done` unless
the target explicitly supplies another schema-valid value. Do not substitute
hardcoded IDs, titles, formats, activity types, or subject names.

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content

Every activity must practice what this Course Content teaches at an appropriate
depth. Do not require absent concepts, methods, facts, or tools.

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
