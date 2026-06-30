# Additional Resources Generation Prompt

You are writing the Additional Resources asset for the Course Builder pipeline.

## Objective

Create a concise, curated reading-and-reference list that helps a learner deepen
the target subtopic after completing the Course Content. Match the manual
course's categorized resource-sheet style, but list only resources present in
the supplied source registry. Accuracy and usefulness matter more than list
length.

Do not copy the manual benchmark and do not rely on model memory. Use the Domain
Model, source metadata, curated source texts, and already-generated Course
Content to explain why each resource is relevant.

## Grounding Rules

- Use only resources and URLs explicitly present in `CONTEXT_JSON` or the
  curated source texts below.
- Reproduce URLs exactly as supplied. Do not invent, repair, expand, or guess a
  URL, edition, publication date, author, institution, or access condition.
- Every significant factual claim must appear in `claims[]`. Claims about a
  resource must cite that resource's `source_id`.
- Each listed resource must retain its registered source ID internally through
  `claims[]`, but keep learner-facing `content` clean: no claim IDs or internal
  source labels such as `g1`.
- A short pedagogical recommendation such as “read this next” may be treated as
  synthesis and need not be a factual claim.
- Do not add popular books, news sites, videos, or courses that are absent from
  the supplied registry, even if they appeared in a manual benchmark.

## Required Structure

Write clean Markdown with useful categories chosen from the available sources,
such as:

- **Foundational Concepts**
- **Banking Risk Taxonomy and Supervisory Guidance**
- **Crisis Case and Applied Analysis**

For every resource include its supplied title/institution, exact supplied URL,
and one sentence explaining which Course Content concept it deepens. Finish with
a brief **Suggested Study Path** ordering the listed resources from foundation
to application. Do not imply that an excerpt is a complete publication.

## Output Contract

Return a single JSON object matching the provided schema. The object is only the
Additional Resources asset, not the whole content package.

Fixed identity fields:

- `id`: `m1_s1_resources`
- `type`: `resources`
- `title`: `Additional Resources`
- `format`: `docx`
- `file`: `null`
- `status`: `done`

Do not include a `solution` field.

Set verification fields to the empty pre-verification state:

- each claim has `support: null`, `supporting_excerpt: null`, and `note: null`
- asset `verification` has all counts as `0`, `unattributed_found: []`, and
  `checked_at: null`

## Already-Generated Course Content (condition on this — recommend resources for what it teaches)

Use this Course Content to determine relevance and study order. Do not recommend
a resource for a topic that the Course Content does not introduce.

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
