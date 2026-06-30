# Did You Know Generation Prompt

You are writing the Did You Know asset for the Course Builder pipeline.

## Objective

Create a compact, slide-ready feature around the manual course's editorial hook:
**“The CRO Role Barely Existed Before the 1990s.”** Use g6 to show how
financial-risk oversight became more central as institutions, products, and
crises exposed the limits of fragmented risk management. Tie the feature back
to the target subtopic's themes of layered risk, model limits, and management
judgment.

Do not copy the manual benchmark. Use the provided Domain Model, curated source
texts, and already-generated Course Content. Prefer a small number of well-made,
well-supported points over a broad history of the CRO profession.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include dates, historical trends, named roles,
  named institutions or crises, and claims about governance practice.
- Each supported factual claim should cite one source with `source_id`.
- Use g6 for the role's early-1990s emergence, mid-1990s financial-services
  adoption, and integrated-risk rationale. Do not extend those facts beyond
  what g6 establishes.
- Use `source_id: null` only for synthesis or framing that asserts no
  independently verifiable fact.
- Do not invent source IDs, statistics, quotations, executive-reporting lines,
  regulatory mandates, or crisis details.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the learner-facing prose.

## Required Structure

Write concise Markdown suitable for approximately two slides:

1. **Did You Know?** — the hook plus a short explanation of why institution-wide
   risk oversight became important. Use only supported examples from the source
   pack; do not add unsupported milestones such as LTCM unless supplied.
2. **Why the Role Matters Today** — explain the need to see interactions among
   market, credit, liquidity, and operational/governance risks, and why models
   do not replace senior judgment.

Use a headline, a brief setup paragraph, and two to four labelled callouts or
bullets per section. Complement the Course Content rather than retelling it.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Did You Know asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_dyk`
- `type`: `did_you_know`
- `title`: `The CRO Role Barely Existed Before the 1990s`
- `format`: `pptx`
- `file`: `null`
- `status`: `done`

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — do not contradict or merely repeat it)

The feature must stay consistent with this Course Content's treatment of risk
categories, layered risk, Lehman, measurement, and judgment.

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
