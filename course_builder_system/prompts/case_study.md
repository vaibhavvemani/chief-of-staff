# Case Study Generation Prompt

You are writing the Case Study asset for the Course Builder pipeline.

## Objective

Develop the **Lehman Brothers collapse** as an applied case study for the target
subtopic. The case must show how multiple financial risk categories (credit,
liquidity, market, and operational/governance) interacted and cascaded to produce
the September 2008 failure of Lehman Brothers Holdings Inc.

The case study is primarily grounded in **g5** (the FCIC report) and uses
**g2** and **g3** (the credit-risk and liquidity-risk references) for the
risk-category interactions. It must be consistent with how the Course Content
already references Lehman — do not introduce facts that contradict the Course
Content.

Do not copy the manual benchmark text. Write original case-study prose based on
the provided curated source texts and the already-generated Course Content.

## Grounding Rules

- Use only the curated source texts below for factual claims.
- Every significant factual claim must appear in `claims[]`.
- Significant factual claims include definitions, dates, figures, named events,
  named institutions, regulatory facts, and concrete assertions — this asset is
  claim-heavy and should attribute rigorously.
- Named events, specific dates (e.g. filing date), dollar figures (e.g. asset
  values, leverage ratios), and named institutions must each be captured as a
  claim.
- Each significant factual claim should cite one source with `source_id`.
  Prefer g5 for FCIC-sourced facts; use g2/g3 for credit/liquidity concepts.
- Use `source_id: null` only for narrative framing or pedagogical transitions
  that assert no verifiable fact.
- Do not invent source IDs. Valid source IDs are provided in the context.
- Keep `content` clean. Do not put inline citations, claim IDs, footnotes, or
  source labels inside the prose.

## Required Coverage

The case study must cover, at minimum:

- Lehman's business model and key exposures (mortgage-backed securities,
  commercial real estate, high leverage),
- the market risk dimension: falling asset values and mark-to-market losses,
- the credit risk dimension: counterparty doubts and interbank credit withdrawal,
- the liquidity risk dimension: repo-market funding collapse and inability to
  roll short-term debt,
- the operational/governance dimension: risk management and oversight failures,
- how these risk categories amplified each other (the cascade logic),
- the date and scale of the bankruptcy filing,
- the systemic contagion effects,
- lessons for financial risk management practice.

Use Markdown with clear section headings suitable for later conversion to slides.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Case Study asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_case`
- `type`: `case_study`
- `title`: `The Lehman Brothers Collapse`
- `format`: `pptx`
- `file`: `null`
- `status`: `done`

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — do not contradict or merely repeat it)

The following is the Course Content asset that was already generated for this
subtopic. Your Case Study must be consistent with how it describes Lehman and
risk categories. Do not contradict any factual assertions made in the Course
Content, and do not introduce Lehman-specific facts that conflict with it.

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
