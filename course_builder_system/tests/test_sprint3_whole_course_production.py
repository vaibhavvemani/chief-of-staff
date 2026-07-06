from __future__ import annotations

import copy
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

import course_renderer
import integrity
import orchestrator
import steps
from agents import intake, revision, student_content, whole_course
from tests.schema_check import validate_content_package

EMPTY_VERIFICATION = {
    "supported": 0,
    "partial": 0,
    "unsupported": 0,
    "ungrounded": 0,
    "unattributed_found": [],
    "checked_at": None,
}


def _planning_chain(
    course_id: str = "s3-coffee",
    *,
    courses_dir: Path | None = None,
) -> dict[str, dict]:
    request = intake.subject_request_artifact(
        subject="Coffee making",
        description="A practical beginner course for better home brewing.",
        constraints=["Keep the course compact."],
        course_id=course_id,
    )
    context = (
        patch.object(orchestrator, "COURSES_DIR", courses_dir)
        if courses_dir is not None
        else nullcontext()
    )
    with context:
        brief = steps.intake_step({"subject_request": request}, None)["brief"]
        outcomes = steps.course_outcomes_step({"brief": brief}, None)["course_outcomes"]
        research = steps.sprint2_research_step(
            {"brief": brief, "course_outcomes": outcomes},
            None,
        )["research_dossier"]
        source_registry = steps.source_selection_step({"research_dossier": research}, None)[
            "approved_source_registry"
        ]
        course_model = steps.structure_step(
            {
                "brief": brief,
                "course_outcomes": outcomes,
                "research_dossier": research,
                "approved_source_registry": source_registry,
            },
            None,
        )["course_model"]
        blueprint = steps.blueprint_step({"course_model": course_model}, None)["blueprint"]
    return {
        "subject_request": request,
        "brief": brief,
        "course_outcomes": outcomes,
        "research_dossier": research,
        "approved_source_registry": source_registry,
        "course_model": course_model,
        "blueprint": blueprint,
    }


def _fixture_generate_asset(
    spec: student_content.AssetSpec,
    inputs: dict,
    course_content: dict | None = None,
    feedback: str | None = None,
    model: str = "mock",
    use_cache: bool = True,
) -> dict:
    resolved = student_content.resolve_asset_spec(spec, inputs)
    source_ids = student_content.routed_source_ids(resolved, inputs)
    source_id = source_ids[0]
    content = f"{resolved.title} for {inputs['subtopic_id']} uses approved evidence {source_id}."
    if feedback:
        content += f" Revision feedback: {feedback}."
    if resolved.conditioned_on_course_content:
        assert course_content is not None
        content += f" Anchor: {course_content['id']}."
    asset = {
        "id": resolved.asset_id,
        "type": resolved.asset_type,
        "title": resolved.title,
        "format": resolved.format,
        "content": content,
        "claims": [
            {
                "id": f"{resolved.asset_id}_c1",
                "text": f"{resolved.title} is grounded in approved evidence.",
                "source_id": source_id,
                "support": None,
                "supporting_excerpt": None,
                "note": None,
            }
        ],
        "sources": [source_id],
        "verification": copy.deepcopy(EMPTY_VERIFICATION),
        "file": None,
        "status": "done",
    }
    if resolved.has_solution:
        asset["solution"] = "Teacher answer key."
    return asset


def _fixture_verify_package(content_package: dict, course_model: dict, **kwargs) -> dict:
    verified = copy.deepcopy(content_package)
    body = verified.get("body", verified)
    for subtopic in body["subtopics"]:
        for asset in subtopic["assets"]:
            for claim in asset["claims"]:
                claim["support"] = "supported"
                claim["supporting_excerpt"] = "Fixture evidence."
                claim["note"] = "Supported by mocked verifier."
            asset["verification"] = {
                "supported": len(asset["claims"]),
                "partial": 0,
                "unsupported": 0,
                "ungrounded": 0,
                "unattributed_found": [],
                "checked_at": "2026-07-06T00:00:00+00:00",
            }
    return verified


def _approve_and_save(*artifacts: dict) -> None:
    for artifact in artifacts:
        artifact["status"] = "approved"
        orchestrator.save_artifact(artifact)


def _artifact_inputs(planning: dict[str, dict]) -> dict[str, dict]:
    return {
        "course_model": planning["course_model"],
        "blueprint": planning["blueprint"],
        "course_outcomes": planning["course_outcomes"],
    }


def test_sprint3_gate_generates_exact_assets_lesson_plan_renderer_and_summary(tmp_path):
    courses_dir = tmp_path / "courses"
    planning = _planning_chain(courses_dir=courses_dir)

    with (
        patch.object(orchestrator, "COURSES_DIR", courses_dir),
        patch("steps.student_content.generate_asset_to_depth", side_effect=_fixture_generate_asset),
        patch("steps.verification.verify_content_package", side_effect=_fixture_verify_package),
    ):
        content_outputs = steps.student_content_step(_artifact_inputs(planning), None)

    content_package = content_outputs["content_package"]
    content_progress = content_outputs["content_progress"]
    planned_subtopics = whole_course.planned_subtopic_ids(_artifact_inputs(planning))
    assert 4 <= len(planned_subtopics) <= 8
    assert content_progress["body"]["complete"] is True
    assert validate_content_package(content_package) == []
    whole_course.assert_exact_selected_assets(content_package["body"], _artifact_inputs(planning))

    lesson_plan = steps.lesson_plan_step(
        {
            "content_package": content_package,
            "blueprint": planning["blueprint"],
            "course_model": planning["course_model"],
        },
        None,
    )["lesson_plan"]
    covered = [
        cover["subtopic_id"]
        for session in lesson_plan["body"]["sessions"]
        for cover in session["covers"]
    ]
    assert covered == [item["subtopic_id"] for item in content_package["body"]["subtopics"]]

    real_render_course_folder = course_renderer.render_course_folder

    def render_to_tmp(**kwargs):
        return real_render_course_folder(
            **kwargs,
            output_root=tmp_path / "rendered",
        )

    with patch("steps.course_renderer.render_course_folder", side_effect=render_to_tmp):
        manifest = steps.render_course_folder_step(
            {
                "course_model": planning["course_model"],
                "blueprint": planning["blueprint"],
                "content_package": content_package,
                "lesson_plan": lesson_plan,
            },
            None,
        )["render_manifest"]

    asset_count = sum(len(item["assets"]) for item in content_package["body"]["subtopics"])
    assert len(manifest["body"]["paths"]["assets"]) == asset_count
    for path in manifest["body"]["paths"]["assets"].values():
        assert Path(path).suffix == ".md"
        assert Path(path).exists()

    all_artifacts = [
        planning["brief"],
        planning["course_outcomes"],
        planning["research_dossier"],
        planning["approved_source_registry"],
        planning["course_model"],
        planning["blueprint"],
        content_package,
        content_progress,
        lesson_plan,
        manifest,
    ]
    with patch.object(orchestrator, "COURSES_DIR", courses_dir):
        _approve_and_save(*all_artifacts)
        summary = steps.run_summary_step(
            {
                "brief": planning["brief"],
                "course_outcomes": planning["course_outcomes"],
                "research_dossier": planning["research_dossier"],
                "approved_source_registry": planning["approved_source_registry"],
                "course_model": planning["course_model"],
                "blueprint": planning["blueprint"],
                "content_package": content_package,
                "content_progress": content_progress,
                "lesson_plan": lesson_plan,
                "render_manifest": manifest,
            },
            None,
        )["run_summary"]
        summary["status"] = "approved"
        orchestrator.save_artifact(summary)
        assert integrity.check_referential_integrity(content_package["course_id"]) == []

    assert summary["body"]["stage_totals"]["completed"] >= 8
    assert summary["body"]["student_content_totals"]["completed"] == asset_count
    assert summary["body"]["output_paths"]["lesson_plan"].endswith("lesson_plan.md")


def test_partial_failure_preserves_completed_assets_and_retry_skips_them(tmp_path):
    planning = _planning_chain("s3-retry", courses_dir=tmp_path / "courses")
    inputs = _artifact_inputs(planning)
    targets = whole_course.planned_subtopic_ids(inputs)[:2]
    failing_key = (targets[0], "summary")

    def fail_one_asset(spec, scoped_inputs, **kwargs):
        if (scoped_inputs["subtopic_id"], spec.asset_type) == failing_key:
            raise RuntimeError("forced generation failure")
        return _fixture_generate_asset(spec, scoped_inputs, **kwargs)

    with patch(
        "agents.whole_course.student_content.generate_asset_to_depth", side_effect=fail_one_asset
    ):
        partial_body, partial_progress = whole_course.generate_content_package_body(
            inputs,
            target_subtopic_ids=targets,
            max_retries=1,
        )

    assert partial_progress["complete"] is False
    assert partial_progress["totals"]["failed"] == 1
    preserved_asset = partial_body["subtopics"][0]["assets"][0]

    with patch(
        "agents.whole_course.student_content.generate_asset_to_depth",
        side_effect=_fixture_generate_asset,
    ):
        retried_body, retried_progress = whole_course.generate_content_package_body(
            inputs,
            existing_body=partial_body,
            target_subtopic_ids=targets,
            max_retries=1,
        )

    assert retried_progress["complete"] is True
    assert retried_progress["totals"]["skipped"] > 0
    assert retried_body["subtopics"][0]["assets"][0] == preserved_asset
    whole_course.assert_exact_selected_assets(
        retried_body,
        inputs,
        target_subtopic_ids=targets,
    )


def test_evidence_gap_and_unselected_assets_are_blocked(tmp_path):
    planning = _planning_chain("s3-gap", courses_dir=tmp_path / "courses")
    inputs = _artifact_inputs(planning)
    first_subtopic = whole_course.planned_subtopic_ids(inputs)[0]
    selected_summary = next(
        asset
        for asset in planning["blueprint"]["body"]["subtopic_plans"][0]["asset_plan"]
        if asset["asset_type"] == "summary"
    )
    selected_summary["source_ids"] = []

    with patch(
        "agents.whole_course.student_content.generate_asset_to_depth",
        side_effect=_fixture_generate_asset,
    ):
        body, progress = whole_course.generate_content_package_body(
            inputs,
            target_subtopic_ids=[first_subtopic],
        )

    assert any(
        unit["status"] == "evidence_gap" and unit["asset_type"] == "summary"
        for unit in progress["units"]
    )
    assert all(asset["type"] != "summary" for asset in body["subtopics"][0]["assets"])

    proposed = next(
        asset
        for asset in planning["blueprint"]["body"]["subtopic_plans"][0]["asset_plan"]
        if asset["selection_status"] != "selected"
    )
    scoped = {**inputs, "subtopic_id": first_subtopic}
    with pytest.raises(ValueError, match="did not select"):
        student_content.generate_asset(student_content.ASSET_SPECS[proposed["asset_type"]], scoped)


def test_targeted_revision_changes_one_asset_without_regenerating_unaffected_assets(tmp_path):
    planning = _planning_chain("s3-revision", courses_dir=tmp_path / "courses")
    inputs = _artifact_inputs(planning)
    targets = whole_course.planned_subtopic_ids(inputs)[:2]
    with patch(
        "agents.whole_course.student_content.generate_asset_to_depth",
        side_effect=_fixture_generate_asset,
    ):
        body, progress = whole_course.generate_content_package_body(
            inputs,
            target_subtopic_ids=targets,
        )
    assert progress["complete"] is True

    target_subtopic = targets[1]
    target_asset = next(
        asset
        for subtopic in body["subtopics"]
        if subtopic["subtopic_id"] == target_subtopic
        for asset in subtopic["assets"]
        if asset["type"] == "summary"
    )
    feedback = f"{target_asset['id']}: make it more concise"
    assert revision.infer_revision_subtopic_id(body, feedback) == target_subtopic

    def revised_generate(spec, scoped_inputs, **kwargs):
        asset = _fixture_generate_asset(spec, scoped_inputs, **kwargs)
        asset["content"] = "Revised targeted summary."
        return asset

    def verify_asset(asset, course_model, **kwargs):
        verified = copy.deepcopy(asset)
        for claim in verified["claims"]:
            claim["support"] = "supported"
            claim["supporting_excerpt"] = "Fixture evidence."
            claim["note"] = "Supported by mocked verifier."
        verified["verification"] = {
            "supported": len(verified["claims"]),
            "partial": 0,
            "unsupported": 0,
            "ungrounded": 0,
            "unattributed_found": [],
            "checked_at": "2026-07-06T00:00:00+00:00",
        }
        return verified

    original = copy.deepcopy(body)
    with (
        patch(
            "agents.revision.student_content.generate_asset_to_depth", side_effect=revised_generate
        ),
        patch("agents.revision.verification.verify_asset", side_effect=verify_asset),
    ):
        revised = revision.revise_content_package(
            body,
            {**inputs, "subtopic_id": target_subtopic},
            planning["course_model"],
            feedback,
            subtopic_id=target_subtopic,
        )

    changed = next(
        asset
        for subtopic in revised["subtopics"]
        if subtopic["subtopic_id"] == target_subtopic
        for asset in subtopic["assets"]
        if asset["id"] == target_asset["id"]
    )
    assert changed["content"] == "Revised targeted summary."
    for original_subtopic, revised_subtopic in zip(
        original["subtopics"],
        revised["subtopics"],
        strict=True,
    ):
        for original_asset, revised_asset in zip(
            original_subtopic["assets"],
            revised_subtopic["assets"],
            strict=True,
        ):
            if original_asset["id"] != target_asset["id"]:
                assert revised_asset == original_asset
