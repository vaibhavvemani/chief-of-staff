# Phase 1 Evaluation Rubric

## Purpose

This rubric defines how we judge whether the AI-generated student content for
`m1_s1` ("Nature of Financial Risk") is good enough to pass Phase 1.

The bar is not "sounds good." The bar is:

> The AI output is at least as good as the manual version, and a human reviewer
> can approve it with light touch-ups rather than rewriting it.

Use this rubric for the core 5 assets first:

- Course Content
- Learning Objectives
- Summary
- Case Study
- Assessment

Then use the same rubric for the light 4 assets:

- Important Person
- Did You Know
- Activities
- Resources

## Scoring Scale

Each dimension is scored from 1 to 10.

| Score | Meaning |
|---|---|
| 1-2 | Very poor. Far below manual quality; likely unusable. |
| 3-4 | Weak. Some useful pieces, but major gaps or rewrites needed. |
| 5 | Almost manual quality, but still meaningfully weaker than the manual version. |
| 6 | Matches the manual version. This is the minimum passing score. |
| 7-8 | Better than the manual version. Stronger, clearer, deeper, or easier to use. |
| 9-10 | Substantially better than manual. Excellent and needs only tiny edits. |

For comparative dimensions, `6` means "manual-equivalent." A score below `6`
means the AI output does not yet meet the Phase 1 bar.

## Pass Rule

For the Phase 1 done gate:

- Each core 5 asset must score at least `6` on every comparative dimension.
- Light 4 assets must be present and decent; they should generally score at
  least `6`, but the core 5 are the hard quality gate.
- Review time must stay within the threshold below.
- A human must ratify the final score. The model can help score, but it cannot
  be the final arbiter.

## Review-Time Threshold

The target is:

> A human should be able to review the full core 5 package for `m1_s1` in
> 60 minutes or less, with light edits only.

Light edits means:

- fixing wording,
- tightening examples,
- correcting small formatting issues,
- adding or removing a small number of lines.

It is not a pass if the reviewer needs to:

- rewrite large sections,
- rebuild the structure,
- fact-check from scratch because sources are unreliable,
- add missing major concepts,
- recreate an asset because it is too thin or off-style.

Suggested per-asset guide:

| Asset | Target review time |
|---|---:|
| Course Content | 25 minutes or less |
| Learning Objectives | 8 minutes or less |
| Summary | 8 minutes or less |
| Case Study | 12 minutes or less |
| Assessment | 12 minutes or less |
| Core 5 total | 60 minutes or less |

## Who Scores What

Scoring is hybrid, but the human is final.

| Dimension | Primary scorer | Notes |
|---|---|---|
| Factual accuracy | Verifier + human ratification | Use claim verdicts as evidence; human spot-checks important claims. |
| Coverage | LLM judge proposes; human ratifies | Compare against the manual version and expected topic scope. |
| Source attribution | Verifier + mechanical checks | Count unsupported, partial, ungrounded, and missing-source claims. |
| Pedagogical clarity | Human | A model can comment, but teaching quality needs human judgment. |
| Asset completeness | Mechanical check + human | Confirm all required assets and required fields exist. |
| House style | LLM judge proposes; human ratifies | Compare tone, formatting, seriousness, and structure to manual assets. |
| Review time | Human | Measure actual wall-clock review time. |

## Dimension 1: Factual Accuracy

Question:

> Are the factual claims correct and supported by the cited sources?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Many wrong or misleading claims; unsafe to use. |
| 3-4 | Several factual issues; reviewer must heavily fact-check. |
| 5 | Mostly correct, but weaker than manual due to notable factual concerns. |
| 6 | As factually reliable as the manual version. |
| 7-8 | More reliable than manual; few or no issues after verification. |
| 9-10 | Excellent factual reliability; claims are precise, well-supported, and easy to audit. |

Evidence to use:

- verifier counts for supported, partial, unsupported, and ungrounded claims,
- human spot-checks of important claims,
- severity of factual issues, not just number of issues.

## Dimension 2: Coverage

Question:

> Does the asset cover the topic deeply enough for the intended course level?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Major concepts missing; not usable as course material. |
| 3-4 | Covers only the obvious basics; too thin for the course. |
| 5 | Almost enough, but still misses meaningful pieces covered manually. |
| 6 | Covers the same essential ground as the manual version. |
| 7-8 | Covers the manual ground plus useful extra depth or better examples. |
| 9-10 | Comprehensive, well-prioritized, and stronger than manual without bloating. |

Evidence to use:

- manual benchmark content,
- Course Model concepts and coverage requirements,
- expected subtopic scope,
- missing concepts, examples, cases, definitions, and transitions.

## Dimension 3: Source Attribution

Question:

> Are significant factual claims traceable to sources?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Most important claims have no usable source trail. |
| 3-4 | Some sourcing exists, but many important claims are missing or wrongly cited. |
| 5 | Sourcing is close, but still weaker than the required manual-equivalent bar. |
| 6 | Important claims are sourced well enough for light review. |
| 7-8 | Strong attribution; most claims are easy to verify quickly. |
| 9-10 | Excellent attribution; claim support is precise, complete, and reviewer-friendly. |

Evidence to use:

- every significant factual claim should have a `source_id`, unless deliberately
  marked ungrounded,
- cited source must actually support the claim,
- verifier should flag unsupported or unattributed claims.

## Dimension 4: Pedagogical Clarity

Question:

> Is the content clear, teachable, and useful for students?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Confusing, poorly ordered, or not teachable. |
| 3-4 | Understandable in places, but students would struggle. |
| 5 | Almost usable, but less clear than manual. |
| 6 | As clear and teachable as the manual version. |
| 7-8 | Clearer than manual; stronger flow, examples, or explanations. |
| 9-10 | Excellent teaching material; polished, intuitive, and easy to deliver. |

Evidence to use:

- logical flow,
- explanation quality,
- examples and applications,
- level fit for the audience,
- whether the teacher can use it without reconstructing the lesson.

## Dimension 5: Asset Completeness

Question:

> Is the required asset present, correctly structured, and complete?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Missing asset or mostly empty. |
| 3-4 | Present but missing major required parts. |
| 5 | Nearly complete, but still has visible gaps. |
| 6 | Complete enough to match the manual asset. |
| 7-8 | More complete or better organized than manual. |
| 9-10 | Fully complete, polished, and ready for packaging. |

Evidence to use:

- asset exists,
- correct asset type,
- title, content, status, format, sources, claims, and solution fields where needed,
- no obvious placeholders,
- assessment includes answer key / solution where required.

## Dimension 6: House Style

Question:

> Does the content feel like it belongs with the existing manual course?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Wrong tone or format; clearly off-brand. |
| 3-4 | Some alignment, but style mismatch is obvious. |
| 5 | Close, but still weaker than manual style. |
| 6 | Matches the manual course style. |
| 7-8 | Keeps the house style while improving polish or consistency. |
| 9-10 | Excellent fit; cleaner and more consistent than manual. |

Evidence to use:

- tone,
- seriousness,
- heading style,
- bullet density,
- structure of slides/docs,
- similarity to manual assets without copying their wording.

## Dimension 7: Review Time

Question:

> Can a human review this quickly with light edits?

Score guidance:

| Score | Anchor |
|---|---|
| 1-2 | Needs a rewrite. |
| 3-4 | Review is slow and heavy; many edits needed. |
| 5 | Close, but exceeds the threshold or needs too many edits. |
| 6 | Meets the review-time threshold with light edits. |
| 7-8 | Faster than threshold; only minor edits needed. |
| 9-10 | Almost approval-ready; only tiny wording or formatting edits. |

Evidence to use:

- actual timed review,
- number and severity of edits,
- whether edits are local touch-ups or structural rewrites.

## Scorecard Template

Use one row per asset.

| Asset | Factual accuracy | Coverage | Source attribution | Pedagogical clarity | Asset completeness | House style | Review time | Pass? | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Course Content |  |  |  |  |  |  |  |  |  |
| Learning Objectives |  |  |  |  |  |  |  |  |  |
| Summary |  |  |  |  |  |  |  |  |  |
| Case Study |  |  |  |  |  |  |  |  |  |
| Assessment |  |  |  |  |  |  |  |  |  |
| Important Person |  |  |  |  |  |  |  |  |  |
| Did You Know |  |  |  |  |  |  |  |  |  |
| Activities |  |  |  |  |  |  |  |  |  |
| Resources |  |  |  |  |  |  |  |  |  |

## Final Decision

The output passes Phase 1 only if:

1. Core 5 assets score `6` or higher on every comparative dimension.
2. The full core 5 package is reviewed in 60 minutes or less.
3. Edits are touch-ups, not rewrites.
4. The human reviewer ratifies the final scores.
