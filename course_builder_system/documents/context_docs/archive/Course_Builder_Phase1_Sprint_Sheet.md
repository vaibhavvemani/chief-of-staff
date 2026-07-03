# Course Builder — Phase 1 Sprint Sheet

> **Status:** ✅ COMPLETE — final outputs accepted 2026-07-01. Retained as the historical schedule record; active work moves to Phase 2.
> **Audience:** leadership / timeline overview. This is the plan for *when* things happen and *who* does what. The technical detail lives in the companion `Course_Builder_Phase1_Plan.md`.
> **Created:** 2026-06-08.

## What Phase 1 delivers (in one sentence)

A working AI agent that produces **trustworthy, source-verified student course content** for one FRM subtopic ("Nature of Financial Risk"), measured against our existing **hand-built version** of that same subtopic — proving the single capability the whole product depends on.

## Why this phase matters most

This is the **make-or-break** phase. The core question of the entire project is: *can an AI produce teaching content good enough that a human only needs to review it lightly, instead of rewriting it?* Phase 1 answers that on one subtopic. If yes, the remaining phases are largely engineering. So it's worth doing carefully — and it's the one phase where a little extra time is justified.

## At a glance

| | |
|---|---|
| **Duration** | ~3 weeks (target), 4 weeks (ceiling). One-week sprints. |
| **Team** | 2 people — **P1 = Vaibhav**, **P2 = [teammate]** — ~4–6 focused hrs/day each, working closely paired. |
| **Where it sits** | First of 6 remaining phases. ~3 of a ~13.5-week total to finish the whole proof-of-concept (target ~Sep 8, 2026). Achievable but tight — slightly de-risked now that Phase 5's LMS-packaging tool (a SCORM 1.2 converter) is already built; that freed effort is banked as buffer, not used to pull the date in. |
| **The deliverable** | One FRM subtopic's full student content, AI-generated, fact-checked against sources, and judged at least as good as our manual version. |

## Timeline / order of implementation

```
Week 1  ▸  Set the quality bar + gather inputs
Week 2  ▸  Build the content generator
Week 3  ▸  Add the fact-checker + measure & improve
Week 4  ▸  (buffer) finish remaining assets + hand off
```

| Sprint | Week | Goal (plain language) | Key deliverable | P1 (Vaibhav) | P2 (teammate) |
|---|---|---|---|---|---|
| **1 — Foundations** | 1 | Decide exactly what "good" means (a 1-10 scoring rubric vs our manual version) and gather everything the AI needs. | Rubric + the manual benchmark + source material + basic AI plumbing, all in place; a first throwaway sample. | Get the manual subtopic files in; write the rubric. | Assemble source material + the subject-knowledge input; build the model-call tooling; run the first sample. |
| **2 — Generator** | 2 | The AI generates real, source-grounded, attributed course content for the subtopic, running through our pipeline. | An end-to-end run producing real content for the 5 core asset types. | Write the generation logic + prompts. | Wire it into the pipeline; update the data format. |
| **3 — Verify & measure** | 3 | A separate step fact-checks every claim against its source; we score the output vs the manual and improve it until it matches or beats it. | Verified content + a 1-10 scorecard showing the 5 core assets at/above manual quality. | Build the scoring/comparison tool. | Build the fact-checking step. *(Both: the improve-and-re-measure loop.)* |
| **4 — Finish & hand off** | 4 *(buffer)* | Finish the 4 lighter assets, add the review-and-revise loop, do a final blind quality check, write up learnings. | All 9 assets done; sign-off that output ≥ manual with minutes-not-rewrite review; a short learnings write-up. | *Paired — split by remaining gaps.* | *Paired — split by remaining gaps.* |

*Note on Week 4:* if Week 3's improvement loop goes well, this work pulls forward and Phase 1 finishes in ~3 weeks. If quality takes longer to reach, Week 4 is the **planned cushion** — and this is exactly the phase where that's most expected.

## What "done" means (plain language)

For one subtopic, the AI's content is **at least as good as our manual version** on the rubric, and a human can **review it in minutes with light edits** rather than rewriting it.

## What we need from leadership

1. **Access to the manual files** for the "Nature of Financial Risk" subtopic (slides, docs). This is the benchmark we measure against — and our single biggest dependency. *(They are not yet in the project; getting them on Day 1 is the top priority.)*
2. **Agreement on the ~3-week target with a possible 4th-week cushion.** This is the highest-risk phase; the buffer protects quality rather than cutting it.
3. *(For the wider conversation)* Our realistic read on the whole project: **~13.5 weeks for all 6 remaining phases** — achievable but tight against the 3-month target, with little slack. *(Mild de-risk: the Phase 5 SCORM 1.2 packaging tool is already built ahead of schedule; that freed effort is held as buffer, not used to move the date in.)*

## Schedule risks (plain language)

| Risk | What we do about it |
|---|---|
| Can't get the manual benchmark files → no yardstick → slips | Request and import them on Day 1; fall back to a different subtopic if truly unavailable. |
| Reaching "as good as manual" takes longer than expected | The Week-4 buffer absorbs it; this is the planned place for that. |
| Two people newer to this kind of AI work | Tight pairing + AI-assisted build; the first week front-loads the learning curve. |

---

*Companion technical document: `Course_Builder_Phase1_Plan.md` (design decisions, data schema, definition of done, full risk register).*
