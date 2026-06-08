"""
Course Builder - Phase 0 step STUBS. (Person B's territory.)

Every step here returns a hardcoded artifact body. There are STILL NO LLM calls,
no research, no content generation. That is deliberate: Phase 0 stays dumb so we
can debug the plumbing separately from agent quality (Handoff Section 2).

What changed in Section 7.1: the placeholder bodies (`<module 1>`, `C1`, ...)
have been replaced with the REAL locked shapes from the FRM reference course -
the `*.frm.example.json` worked examples - copied in verbatim and hardcoded.
The shapes here are the v0.1 contracts (Handoff Section 4); the agents that will
fill them for real are Phase 1+. The orchestrator never changes: it only ever
sees the metadata envelope, never these body shapes.

Note the step->artifact mapping is not 1:1. Step 1 (Structure) produces TWO
artifacts (domain_model AND toc), so a step returns a {type: artifact} dict,
not a single artifact.

`feedback` is accepted to satisfy the (inputs, feedback) -> {type: artifact}
contract, but a dumb stub ignores it - it always returns the same fixed shape.
A real Phase 1+ agent would use it to revise. `course_id` is read from `inputs`
(not hardcoded) so the envelope follows the actual run, not the FRM sample.

The five bodies below are mutually referentially consistent: every Blueprint /
Content Package / Lesson Plan reference resolves to a TOC id (see integrity.py).
"""

from __future__ import annotations

from typing import Optional

from orchestrator import make_artifact


def structure_step(inputs: dict, feedback: Optional[str]) -> dict:
    """subject brief -> Domain Model + TOC (Handoff Section 4.3 / 4.4)."""
    course_id = inputs["brief"]["course_id"]

    domain_model = make_artifact(
        course_id, "domain_model", "structure",
        body={
            "subject": "Financial Risk Management",
            "overview": (
                "Financial Risk Management is the discipline of identifying, "
                "measuring, and controlling losses from market movements, "
                "counterparty default, funding shortfalls, and operational "
                "failure. It progresses from foundational definitions through "
                "quantitative measurement to regulatory frameworks and "
                "integrated, firm-wide practice."
            ),
            "concepts": [
                {"id": "c1", "name": "Financial Risk",
                 "summary": "The possibility of loss from market, credit, "
                            "liquidity, or operational exposure.",
                 "depends_on": []},
                {"id": "c2", "name": "Risk vs Uncertainty",
                 "summary": "Knight's distinction: risk is measurable "
                            "probability; uncertainty is not.",
                 "depends_on": ["c1"]},
                {"id": "c3", "name": "Value at Risk (VaR)",
                 "summary": "A quantile measure of maximum expected loss over "
                            "a horizon at a confidence level.",
                 "depends_on": ["c1"]},
                {"id": "c4", "name": "Regulatory Capital (Basel)",
                 "summary": "Minimum capital banks must hold against "
                            "risk-weighted assets under the Basel Accords.",
                 "depends_on": ["c3"]},
            ],
            "grounding_sources": [
                {"category": "GLOBAL FRAMEWORKS",
                 "items": [
                     {"id": "g1", "name": "Basel III framework (BIS)",
                      "url": "https://www.bis.org/bcbs/basel3.htm"},
                     {"id": "g2", "name": "Basel II framework (BIS)",
                      "url": "https://www.bis.org/publ/bcbs128.htm"},
                 ]},
            ],
        },
        inputs=["brief"],
    )
    toc = make_artifact(
        course_id, "toc", "structure",
        body={
            "subject": "Financial Risk Management",
            "modules": [
                {
                    "id": "m1",
                    "order": 1,
                    "title": "Foundations of Financial Risk",
                    "subtopics": [
                        {"id": "m1_s1", "order": 1,
                         "title": "Nature of Financial Risk"},
                        {"id": "m1_s2", "order": 2,
                         "title": "Risk Classification Framework"},
                        {"id": "m1_s3", "order": 3,
                         "title": "Risk Management Process"},
                        {"id": "m1_s4", "order": 4,
                         "title": "Risk Appetite & Capacity"},
                        {"id": "m1_s5", "order": 5,
                         "title": "Evolution of Modern Risk Management"},
                        {"id": "m1_s6", "order": 6,
                         "title": "Institutional Risk Governance"},
                    ],
                },
                {
                    "id": "m2",
                    "order": 2,
                    "title": "Quantitative Foundations for Risk",
                    "subtopics": [
                        {"id": "m2_s1", "order": 1,
                         "title": "Probability Theory"},
                    ],
                },
            ],
        },
        inputs=["brief"],
    )
    return {"domain_model": domain_model, "toc": toc}


def blueprint_step(inputs: dict, feedback: Optional[str]) -> dict:
    """TOC + Domain Model -> Blueprint (Handoff Section 4.5).

    allocations[].node_id and dependencies[].module_id reference the TOC node
    ids produced by structure_step; speakers come from (future) Step 2 research.
    """
    course_id = inputs["toc"]["course_id"]

    blueprint = make_artifact(
        course_id, "blueprint", "blueprint",
        body={
            "allocations": [
                {"node_id": "m1", "hours": 2.5, "slides": 49},
                {"node_id": "m1_s1", "hours": 0.5, "slides": 9},
                {"node_id": "m2", "hours": 3.0, "slides": 55},
            ],
            "dependencies": [
                {"module_id": "m1", "prerequisites": []},
                {"module_id": "m2", "prerequisites": ["m1"]},
            ],
            "speakers": [
                {"id": "sp1", "placed_at": "m1",
                 "topic": "Institutional Risk Governance",
                 "suggested_expert": "<expert from Step 2 research>",
                 "source": "research", "status": "proposed"},
            ],
        },
        inputs=["toc", "domain_model"],
    )
    return {"blueprint": blueprint}


def student_content_step(inputs: dict, feedback: Optional[str]) -> dict:
    """TOC + Blueprint + Domain Model -> Content Package (Handoff Section 4.6).

    The TOC supplies the subtopic titles and module context the content is
    written against; the Blueprint supplies per-subtopic volume (hours/slides);
    the Domain Model supplies concepts and grounding sources. Output is keyed by
    TOC subtopic id. `content` holds the generated material; `file` stays null
    until packaging (Phase 5). `sources` reference Domain Model grounding ids
    (e.g. g1). `solution` is the teacher-only key on assessments.
    """
    course_id = inputs["toc"]["course_id"]

    content = make_artifact(
        course_id, "content_package", "student_content",
        body={
            "asset_vocabulary": [
                "learning_objectives", "course_content", "summary",
                "case_study", "important_person", "did_you_know",
                "assessment", "activities", "resources",
            ],
            "subtopics": [
                {
                    "subtopic_id": "m1_s1",
                    "assets": [
                        {"id": "m1_s1_lo", "type": "learning_objectives",
                         "title": "Learning Objectives", "format": "docx",
                         "content": "Understand the concept of financial risk "
                                    "and how it arises...",
                         "sources": [], "file": None, "status": "done"},
                        {"id": "m1_s1_case", "type": "case_study",
                         "title": "The Lehman Brothers Collapse",
                         "format": "pptx",
                         "content": "Lehman Brothers Collapse (2008) as a "
                                    "multi-risk case...",
                         "sources": ["g1"], "file": None, "status": "done"},
                        {"id": "m1_s1_assess", "type": "assessment",
                         "title": "Self-Assessment: Nature of Financial Risk",
                         "format": "docx",
                         "content": "Q1. Define financial risk and give two "
                                    "examples of how it arises in a bank.",
                         "solution": "Q1. Financial risk is the possibility of "
                                     "loss from market, credit, liquidity, or "
                                     "operational exposure. Examples: a trading "
                                     "loss from market moves; a borrower "
                                     "default (credit).",
                         "sources": [], "file": None, "status": "done"},
                    ],
                },
            ],
        },
        inputs=["toc", "blueprint", "domain_model"],
    )
    return {"content_package": content}


def lesson_plan_step(inputs: dict, feedback: Optional[str]) -> dict:
    """Content Package + Blueprint -> Lesson Plan (Handoff Section 4.7).

    Organized by session (a class). covers[].subtopic_id references TOC
    subtopics; mode is live | self_study; talking_points are teacher-facing.
    """
    course_id = inputs["content_package"]["course_id"]

    plan = make_artifact(
        course_id, "lesson_plan", "lesson_plan",
        body={
            "sessions": [
                {
                    "id": "sess1", "order": 1,
                    "title": "Foundations of Financial Risk",
                    "duration_hours": 2.5,
                    "covers": [
                        {"subtopic_id": "m1_s1", "mode": "live",
                         "talking_points": [
                             "Open with the Lehman collapse as a hook",
                             "Draw the risk-vs-uncertainty distinction (Knight)",
                         ]},
                        {"subtopic_id": "m1_s2", "mode": "live",
                         "talking_points": [
                             "Walk through the risk classification framework",
                         ]},
                        {"subtopic_id": "m1_s3", "mode": "self_study",
                         "talking_points": []},
                    ],
                },
            ],
        },
        inputs=["content_package", "blueprint"],
    )
    return {"lesson_plan": plan}
