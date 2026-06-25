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

import json
from pathlib import Path

from agents import student_content
from orchestrator import make_artifact

CONTENT_PACKAGE_SCHEMA_VERSION = "0.2"

REPO_ROOT = Path(__file__).resolve().parent
# Phase 1: the Domain Model is no longer a Phase-0 toy stub. It is the
# hand-authored deep DM (S1.7) at domain/m1_s1_domain_model.json - the SAME
# file the generation agent's CLI reads. structure_step surfaces that file's
# body as the pipeline's domain_model so the in-pipeline generator and
# integrity.py see the real grounding registry (g1-g5), not two diverging
# copies. Reading a hand-authored input is still a "dumb" stub: no LLM call.
DEEP_DOMAIN_MODEL_PATH = REPO_ROOT / "domain" / "m1_s1_domain_model.json"


def _deep_domain_model_body() -> dict:
    """Load the hand-authored deep Domain Model body (single source of truth)."""
    if not DEEP_DOMAIN_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"hand-authored Domain Model not found: {DEEP_DOMAIN_MODEL_PATH}"
        )
    artifact = json.loads(DEEP_DOMAIN_MODEL_PATH.read_text(encoding="utf-8"))
    return artifact["body"]


def structure_step(inputs: dict, feedback: str | None) -> dict:
    """subject brief -> Domain Model + TOC (Handoff Section 4.3 / 4.4).

    The Domain Model body is the hand-authored deep DM (S1.7), loaded from
    `domain/m1_s1_domain_model.json` - deep on m1_s1, thin stubs for the other
    m1 subtopics, registering grounding sources g1-g5. The TOC stays a locked
    hardcoded stub; its m1 subtopics (m1_s1..m1_s6) line up with the DM.
    """
    course_id = inputs["brief"]["course_id"]

    domain_model = make_artifact(
        course_id, "domain_model", "structure",
        body=_deep_domain_model_body(),
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


def blueprint_step(inputs: dict, feedback: str | None) -> dict:
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


def student_content_step(inputs: dict, feedback: str | None) -> dict:
    """TOC + Blueprint + Domain Model -> v0.2 Content Package (Handoff Section 4.6).

    Thin adapter (Plan H): call the generation agent for each of the five core
    assets, then assemble them into one v0.2 Content Package. The Course Content
    anchor is generated first; the other four (learning_objectives, summary,
    case_study, assessment) are generated conditioned on it for cross-asset
    coherence. `content` holds clean prose; significant factual claims live in
    `claims[]`; `sources[]` is the derived non-null claim source-id union;
    `solution` is the teacher-only key on the assessment. `file` stays null until
    packaging (Phase 5).

    `feedback` is accepted to satisfy the (inputs, feedback) contract but is NOT
    used in the baseline: feedback-driven targeted per-asset regeneration is
    wired later (S3.6), once the verifier flags exist (Plan D). use_cache stays
    on (default) so repeated pipeline runs reuse cached LLM responses.
    """
    course_id = inputs["toc"]["course_id"]

    gen_inputs = {
        "toc": inputs["toc"],
        "blueprint": inputs["blueprint"],
        "domain_model": inputs["domain_model"],
        "subtopic_id": "m1_s1",
    }

    # Course Content anchor first; the remaining four condition on it.
    cc = student_content.generate_asset(student_content.COURSE_CONTENT_SPEC, gen_inputs)
    assets = [cc]
    for name in ("learning_objectives", "summary", "case_study", "assessment"):
        spec = student_content.ASSET_SPECS[name]
        assets.append(student_content.generate_asset(spec, gen_inputs, course_content=cc))

    content = make_artifact(
        course_id, "content_package", "student_content",
        body={
            # Full 9-type vocabulary even though only the core 5 are generated
            # this sprint; the light 4 land in S3.5.
            "asset_vocabulary": [
                "learning_objectives", "course_content", "summary",
                "case_study", "important_person", "did_you_know",
                "assessment", "activities", "resources",
            ],
            "subtopics": [{"subtopic_id": "m1_s1", "assets": assets}],
        },
        inputs=["toc", "blueprint", "domain_model"],
        schema_version=CONTENT_PACKAGE_SCHEMA_VERSION,
    )
    return {"content_package": content}


def lesson_plan_step(inputs: dict, feedback: str | None) -> dict:
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
