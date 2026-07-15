from __future__ import annotations

import json

import acceptance
import orchestrator
import run
from agents import intake
from orchestrator import run_pipeline


def _request() -> dict:
    return intake.subject_request_artifact(
        subject=acceptance.NEXT_CYCLE_ACCEPTANCE_SUBJECT,
        description="A practical beginner course for better home brewing.",
        constraints=["Keep the next-cycle acceptance course compact."],
        course_id=acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID,
    )


def test_next_cycle_acceptance_course_is_isolated_and_has_expected_outputs(
    tmp_path, monkeypatch
) -> None:
    courses_root = tmp_path / "courses"
    rendered_root = tmp_path / "rendered_courses"
    monkeypatch.setattr(orchestrator, "COURSES_DIR", courses_root)

    run_pipeline(
        acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID,
        run.build_sprint4_acceptance_pipeline(output_root=rendered_root),
        {"subject_request": _request()},
        approver=run.auto_approver,
    )

    artifact_root = courses_root / acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID
    actual = {path.stem for path in artifact_root.glob("*.json")}
    assert actual == acceptance.NEXT_CYCLE_EXPECTED_PIPELINE_ARTIFACTS
    assert acceptance.NEXT_CYCLE_EXPECTED_STAGE_OUTPUTS["research"] == {
        "research_dossier",
        "approved_source_registry",
    }
    assert acceptance.NEXT_CYCLE_EXPECTED_STAGE_OUTPUTS["content"] == {
        "content_package",
        "content_progress",
        "content_review",
    }
    manifest = json.loads((artifact_root / "render_manifest.json").read_text())
    assert set(manifest["body"]["paths"]) == acceptance.NEXT_CYCLE_EXPECTED_RENDER_KEYS
    assert (rendered_root / acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID).is_dir()


def test_named_verifier_blocker_and_repair_controls_are_deterministic(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(orchestrator, "COURSES_DIR", tmp_path / "courses")
    base_controls = acceptance.DeterministicAcceptanceControls(
        blocker_asset_ids=frozenset(
            {acceptance.NEXT_CYCLE_KNOWN_BLOCKER_ASSET_ID}
        )
    )
    run_pipeline(
        acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID,
        run.build_sprint4_acceptance_pipeline(
            output_root=tmp_path / "rendered_courses",
            controls=base_controls,
        ),
        {"subject_request": _request()},
        approver=run.auto_approver,
    )
    package = orchestrator.load_artifact(
        acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID, "content_package"
    )
    assert package is not None
    target = next(
        asset
        for subtopic in package["body"]["subtopics"]
        for asset in subtopic["assets"]
        if asset["id"] == acceptance.NEXT_CYCLE_KNOWN_BLOCKER_ASSET_ID
    )
    assert target["verification"]["unsupported"] == 1

    repaired = acceptance.deterministic_verify_asset(
        target,
        orchestrator.load_artifact(
            acceptance.NEXT_CYCLE_ACCEPTANCE_COURSE_ID, "course_model"
        ),
        controls=acceptance.DeterministicAcceptanceControls(
            blocker_asset_ids=base_controls.blocker_asset_ids,
            repaired_asset_ids=frozenset(
                {acceptance.NEXT_CYCLE_KNOWN_BLOCKER_ASSET_ID}
            ),
        ),
    )
    assert repaired["verification"]["unsupported"] == 0
    assert repaired["verification"]["supported"] == 1
