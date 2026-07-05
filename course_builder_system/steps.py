"""Course Builder pipeline steps.

At the start of Phase 2, upstream intelligence remains fixture-backed while the
real Student Content path is preserved. Phase 2 replaces those fixtures in
contract order. The target flow is Course Brief -> approved Course Outcomes ->
Research Dossier/source decisions -> compact Course Model -> Blueprint ->
verified Content Package -> Lesson Plan.
"""

from __future__ import annotations

import json
from pathlib import Path

from agents import blueprint as blueprint_agent
from agents import course_model as course_model_agent
from agents import intake, outcomes, research, revision, student_content, verification
from orchestrator import course_dir, load_artifact, make_artifact
from research_adapter import BoundedLiveResearchProvider, coffee_mock_provider
from source_selection import (
    apply_source_capture_decision,
    apply_source_decision,
    approved_source_registry,
    recommended_source_ids,
    source_choice_prompt,
)
from source_store import SourceStore

CONTENT_PACKAGE_SCHEMA_VERSION = "0.2"
DESIGN_SCHEMA_VERSION = "0.2"

REPO_ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = REPO_ROOT / "course_models"
COURSE_OUTCOMES_FIXTURE = FIXTURE_DIR / "frm_demo.course_outcomes.json"
RESEARCH_DOSSIER_FIXTURE = FIXTURE_DIR / "frm_demo.research_dossier.json"
COFFEE_RESEARCH_DOSSIER_FIXTURE = FIXTURE_DIR / "coffee_demo.research_dossier.json"
COURSE_MODEL_FIXTURE = FIXTURE_DIR / "frm_demo.course_model.json"
BLUEPRINT_FIXTURE = FIXTURE_DIR / "frm_demo.blueprint.json"


def _fixture_body(path: Path, artifact_type: str) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{artifact_type} fixture not found: {path}")
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact.get("artifact_type") != artifact_type or not isinstance(artifact.get("body"), dict):
        raise ValueError(f"invalid {artifact_type} fixture: {path}")
    return artifact["body"]


def intake_step(inputs: dict, feedback: str | None) -> dict:
    """Sparse Subject Request -> schema-valid Course Brief v0.2."""
    subject_request = inputs["subject_request"]
    answers = {}
    if feedback:
        answers["purpose"] = feedback
    artifact = intake.build_brief_artifact(subject_request, answers)
    return {"brief": artifact}


def course_outcomes_step(inputs: dict, feedback: str | None) -> dict:
    """Approved Course Brief -> course-level outcomes."""
    candidates = outcomes.draft_outcomes_from_brief(inputs["brief"])
    if feedback:
        candidates[0]["statement"] = feedback
    artifact = outcomes.build_course_outcomes_artifact(inputs["brief"], candidates)
    return {"course_outcomes": artifact}


def research_step(inputs: dict, feedback: str | None) -> dict:
    """Brief + approved outcomes -> dossier (Phase 2 replacement target)."""
    course_id = inputs["brief"]["course_id"]
    fixture = _research_fixture_for(inputs["brief"])
    artifact = make_artifact(
        course_id,
        "research_dossier",
        "research",
        body=_fixture_body(fixture, "research_dossier"),
        inputs=["brief", "course_outcomes"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )
    return {"research_dossier": artifact}


def sprint2_research_step(inputs: dict, feedback: str | None) -> dict:
    """Brief + approved outcomes -> bounded competitor/source research."""
    provider = coffee_mock_provider()
    artifact = research.build_research_dossier_artifact(
        inputs["brief"],
        inputs["course_outcomes"],
        provider=provider,
    )
    return {"research_dossier": artifact}


def live_research_step(inputs: dict, feedback: str | None) -> dict:
    """Live bounded research provider path for manual Sprint 2 runs."""
    provider = BoundedLiveResearchProvider()
    artifact = research.build_research_dossier_artifact(
        inputs["brief"],
        inputs["course_outcomes"],
        provider=provider,
    )
    return {"research_dossier": artifact}


def source_selection_step(inputs: dict, feedback: str | None) -> dict:
    """Apply explicit source choices and capture approved source bodies."""
    course_id = inputs["research_dossier"]["course_id"]
    prompt = source_choice_prompt(inputs["research_dossier"])
    if feedback:
        selected_ids = tuple(item.strip() for item in feedback.split(",") if item.strip())
    else:
        selected_ids = prompt.default_selected_ids() or recommended_source_ids(
            inputs["research_dossier"],
            max_sources=_default_source_selection_limit(inputs["research_dossier"]),
        )
    if _selection_needs_capture(inputs["research_dossier"], selected_ids):
        decided_dossier = apply_source_capture_decision(
            inputs["research_dossier"],
            selected_ids,
            provider=_provider_for_research(inputs["research_dossier"]),
            store=SourceStore(course_dir(course_id) / "sources"),
        )
    else:
        decided_dossier = apply_source_decision(inputs["research_dossier"], selected_ids)
    registry = approved_source_registry(decided_dossier)
    rejected_ids = [
        candidate["id"]
        for candidate in decided_dossier["body"].get("source_candidates", [])
        if candidate["status"] == "rejected"
    ]
    artifact = make_artifact(
        course_id,
        "approved_source_registry",
        "source_selection",
        body={
            "choice_prompt": {
                "id": prompt.id,
                "stage": prompt.stage,
                "target_artifact": prompt.target_artifact,
                "mode": prompt.mode,
                "options": [
                    {
                        "id": option.id,
                        "label": option.label,
                        "description": option.description,
                        "recommended": option.selected_by_default,
                        "recommendation_rationale": option.recommendation_rationale,
                    }
                    for option in prompt.options
                ],
            },
            "decision": {
                "selected_ids": list(selected_ids),
                "approved_ids": [source["id"] for source in registry],
                "rejected_ids": rejected_ids,
            },
            "source_registry": registry,
        },
        inputs=["research_dossier"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )
    return {"approved_source_registry": artifact}


def structure_step(inputs: dict, feedback: str | None) -> dict:
    """Approved intent + research -> combined compact Course Model."""
    course_id = inputs["brief"]["course_id"]
    if "approved_source_registry" in inputs:
        course_model = course_model_agent.build_course_model_artifact(
            inputs["brief"],
            inputs["course_outcomes"],
            inputs["research_dossier"],
            approved_source_registry=inputs["approved_source_registry"],
        )
    else:
        course_model = make_artifact(
            course_id,
            "course_model",
            "structure",
            body=_fixture_body(COURSE_MODEL_FIXTURE, "course_model"),
            inputs=["brief", "course_outcomes", "research_dossier"],
            schema_version=DESIGN_SCHEMA_VERSION,
        )
    return {"course_model": course_model}


def blueprint_step(inputs: dict, feedback: str | None) -> dict:
    """Approved Course Model -> per-subtopic delivery and asset plan."""
    course_id = inputs["course_model"]["course_id"]
    if "approved_source_registry" in inputs["course_model"].get("inputs", []):
        blueprint = blueprint_agent.build_blueprint_artifact(inputs["course_model"])
    else:
        blueprint = make_artifact(
            course_id,
            "blueprint",
            "blueprint",
            body=_fixture_body(BLUEPRINT_FIXTURE, "blueprint"),
            inputs=["course_model"],
            schema_version=DESIGN_SCHEMA_VERSION,
        )
    return {"blueprint": blueprint}


def student_content_step(inputs: dict, feedback: str | None) -> dict:
    """Course Model + Blueprint -> verified v0.2 Content Package.

    The Phase 1 Blueprint selects all nine assets, while arbitrary courses may
    select a different set for each subtopic. Course Content is generated first;
    conditioned assets follow it for cross-asset coherence. `content` holds
    clean prose; significant factual
    claims live in `claims[]`; `sources[]` is the derived non-null claim source-id
    union; `solution` is the teacher-only key on the assessment. `file` stays
    null until packaging (Phase 5).

    On a checkpoint rejection, feedback targets one or more assets (for example,
    ``course_content: deepen the worked example``) or uses ``verifier`` to
    regenerate only assets with verification flags. Unselected assets are
    preserved, and every revised asset is reverified. ``use_cache`` stays on so
    unchanged calls are reused while a changed feedback prompt gets a new key.
    """
    course_id = inputs["course_model"]["course_id"]
    subtopic_id = inputs.get("subtopic_id", "m1_s1")

    gen_inputs = {
        "course_model": inputs["course_model"],
        "blueprint": inputs["blueprint"],
        "course_outcomes": inputs.get("course_outcomes"),
        "subtopic_id": subtopic_id,
    }

    if feedback:
        existing = load_artifact(course_id, "content_package")
        if existing is None:
            raise ValueError("cannot revise Student Content before a baseline package exists")
        package_body = revision.revise_content_package(
            existing["body"],
            gen_inputs,
            inputs["course_model"],
            feedback,
        )
    else:
        selected_specs = student_content.selected_asset_specs(gen_inputs)
        cc_spec = next(spec for spec in selected_specs if spec.asset_type == "course_content")
        cc = student_content.generate_asset_to_depth(cc_spec, gen_inputs)
        assets = [cc]
        for spec in selected_specs:
            if spec.asset_type == "course_content":
                continue
            course_content = cc if spec.conditioned_on_course_content else None
            assets.append(
                student_content.generate_asset_to_depth(
                    spec,
                    gen_inputs,
                    course_content=course_content,
                )
            )

        package_body = {
            "asset_vocabulary": [
                "learning_objectives",
                "course_content",
                "summary",
                "case_study",
                "important_person",
                "did_you_know",
                "assessment",
                "activities",
                "resources",
            ],
            "subtopics": [{"subtopic_id": subtopic_id, "assets": assets}],
        }

        # Separate adversarial calls annotate every generated asset before the
        # package is assembled. Learner content and source unions remain intact.
        package_body = verification.verify_content_package(
            package_body,
            inputs["course_model"],
            blueprint=inputs["blueprint"],
        )
    _print_verification_summaries(package_body)

    content = make_artifact(
        course_id,
        "content_package",
        "student_content",
        body=package_body,
        inputs=["course_model", "blueprint", "course_outcomes"],
        schema_version=CONTENT_PACKAGE_SCHEMA_VERSION,
    )
    return {"content_package": content}


def _print_verification_summaries(package_body: dict) -> None:
    """Surface compact verifier results before the normal content checkpoint."""
    print("\nVerification summary:")
    print(
        "  Revision syntax: '<asset id or type>: <feedback>' or 'verifier' "
        "to target flagged assets."
    )
    for subtopic in package_body.get("subtopics", []):
        for asset in subtopic.get("assets", []):
            summary = asset.get("verification", {})
            print(
                f"  {asset.get('id', '<unknown>')}: "
                f"supported={summary.get('supported', 0)}, "
                f"partial={summary.get('partial', 0)}, "
                f"unsupported={summary.get('unsupported', 0)}, "
                f"ungrounded={summary.get('ungrounded', 0)}, "
                f"unattributed={len(summary.get('unattributed_found', []))}"
            )


def lesson_plan_step(inputs: dict, feedback: str | None) -> dict:
    """Content Package + Blueprint -> Lesson Plan (Handoff Section 4.7).

    Organized by session (a class). covers[].subtopic_id references Course Model
    subtopics; mode is live | self_study; talking_points are teacher-facing.
    """
    course_id = inputs["content_package"]["course_id"]

    plan = make_artifact(
        course_id,
        "lesson_plan",
        "lesson_plan",
        body={
            "sessions": [
                {
                    "id": "sess1",
                    "order": 1,
                    "title": "Foundations of Financial Risk",
                    "duration_hours": 2.5,
                    "covers": [
                        {
                            "subtopic_id": "m1_s1",
                            "mode": "live",
                            "talking_points": [
                                "Open with the Lehman collapse as a hook",
                                "Draw the risk-vs-uncertainty distinction (Knight)",
                            ],
                        },
                        {
                            "subtopic_id": "m1_s2",
                            "mode": "live",
                            "talking_points": [
                                "Walk through the risk classification framework",
                            ],
                        },
                        {"subtopic_id": "m1_s3", "mode": "self_study", "talking_points": []},
                    ],
                },
            ],
        },
        inputs=["content_package", "blueprint"],
    )
    return {"lesson_plan": plan}


def _research_fixture_for(brief: dict) -> Path:
    subject = brief.get("body", {}).get("subject", "").casefold()
    if brief.get("course_id") == "coffee-demo" or "coffee" in subject:
        return COFFEE_RESEARCH_DOSSIER_FIXTURE
    return RESEARCH_DOSSIER_FIXTURE


def _selection_needs_capture(research_dossier: dict, selected_ids: tuple[str, ...]) -> bool:
    candidates = {
        candidate["id"]: candidate
        for candidate in research_dossier["body"].get("source_candidates", [])
    }
    return any(
        source_id in candidates and not candidates[source_id].get("content_ref")
        for source_id in selected_ids
    )


def _provider_for_research(research_dossier: dict):
    locators = [
        candidate.get("locator") or ""
        for candidate in research_dossier["body"].get("source_candidates", [])
    ]
    if any("example.test" in locator for locator in locators):
        return coffee_mock_provider()
    return BoundedLiveResearchProvider()


def _default_source_selection_limit(research_dossier: dict) -> int:
    locators = [
        candidate.get("locator") or ""
        for candidate in research_dossier["body"].get("source_candidates", [])
    ]
    return 2 if any("example.test" in locator for locator in locators) else 6
