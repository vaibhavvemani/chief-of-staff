from __future__ import annotations

from pathlib import Path

from api.models import STAGE_STATES
from api.services.approval_guard import ApprovalGuardService
from api.services.artifact_repository import ArtifactRepository
from api.services.capability_service import StageCapabilityService
from api.services.pipeline_catalog import PipelineCatalog
from api.services.workspace_projector import WorkspaceProjector
from orchestrator import make_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_target_state_vocabulary_is_exhaustive_and_has_an_action_treatment() -> None:
    expected = {
        "locked",
        "needs_input",
        "ready",
        "running",
        "awaiting_review",
        "requires_attention",
        "approved",
        "stale",
        "failed",
    }
    assert STAGE_STATES == expected

    service = StageCapabilityService(PipelineCatalog())
    action_ids = {
        state: [
            action["id"]
            for action in service.actions(
                "brief",
                state,
                read_only=False,
                blocking_stage="outcomes" if state == "locked" else None,
            )
        ]
        for state in expected
    }
    assert action_ids == {
        "locked": ["go_to_blocker"],
        "needs_input": ["edit"],
        "ready": ["run"],
        "running": [],
        "awaiting_review": ["edit", "approve"],
        "requires_attention": ["edit", "approve"],
        "approved": ["reopen", "continue"],
        "stale": ["run"],
        "failed": ["retry"],
    }


def test_capability_matrix_never_projects_unregistered_generic_revisions() -> None:
    catalog = PipelineCatalog()
    capabilities = StageCapabilityService(catalog)

    for stage in catalog.stages:
        actions = capabilities.actions(
            stage.slug,
            "awaiting_review",
            read_only=False,
            approval_failures=[],
        )
        revision = next((item for item in actions if item["id"] == "revise"), None)
        if stage.slug == "content":
            assert revision is not None
            assert revision["revision_targets"] == [
                {
                    "target_type": "asset",
                    "categories": ["clarity", "depth", "evidence"],
                }
            ]
        else:
            assert revision is None

    package_actions = capabilities.actions(
        "package",
        "requires_attention",
        read_only=False,
        approval_failures=[{"message": "Package is blocked."}],
    )
    assert [action["id"] for action in package_actions] == ["approve"]
    assert package_actions[0]["enabled"] is False


def test_state_actions_are_explicit_and_read_only_has_no_mutations() -> None:
    service = StageCapabilityService(PipelineCatalog())

    assert [
        item["id"]
        for item in service.actions("brief", "ready", read_only=False)
    ] == ["run"]
    assert [
        item["id"]
        for item in service.actions("brief", "needs_input", read_only=False)
    ] == ["edit"]
    assert [
        item["id"]
        for item in service.actions("brief", "failed", read_only=False)
    ] == ["retry"]
    assert [
        item["id"]
        for item in service.actions("brief", "approved", read_only=False)
    ] == ["reopen", "continue"]
    assert service.actions(
        "content",
        "locked",
        read_only=False,
        blocking_stage="blueprint",
    ) == [
        {
            "id": "go_to_blocker",
            "label": "Go to Blueprint",
            "enabled": True,
            "reason": None,
            "requires_impact_confirmation": False,
            "target_stage": "blueprint",
        }
    ]
    assert service.actions("brief", "approved", read_only=True) == []


def test_course_model_edit_is_available_only_at_reviewable_mutable_checkpoints() -> None:
    service = StageCapabilityService(PipelineCatalog())

    for state in ("awaiting_review", "requires_attention"):
        actions = service.actions("course-model", state, read_only=False)
        assert [item["id"] for item in actions] == ["edit", "approve"]
        assert actions[0]["label"] == "Edit Course Model"

    assert [
        item["id"]
        for item in service.actions("course-model", "approved", read_only=False)
    ] == ["reopen", "continue"]
    assert [
        item["id"]
        for item in service.actions("course-model", "stale", read_only=False)
    ] == ["run"]
    assert [
        item["id"]
        for item in service.actions("course-model", "failed", read_only=False)
    ] == ["retry"]
    assert service.actions("course-model", "running", read_only=False) == []
    assert service.actions("course-model", "awaiting_review", read_only=True) == []


def test_projector_exposes_needs_input_with_one_documented_action(
    tmp_path: Path,
) -> None:
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    subject = make_artifact(
        "needs-input-course",
        "subject_request",
        "seed",
        body={"subject": "Coffee making"},
        inputs=[],
    )
    subject["status"] = "approved"
    repository.save(subject)
    brief = make_artifact(
        "needs-input-course",
        "brief",
        "intake",
        body={
            "subject": "Coffee making",
            "intake_state": {"unresolved_required_fields": ["audience"]},
        },
        inputs=["subject_request"],
    )
    repository.save(brief)
    projector = WorkspaceProjector(
        repository,
        catalog,
        approval_guards=ApprovalGuardService(repository, catalog),
    )

    stage = projector.stage("needs-input-course", "brief")

    assert stage["state"] == "needs_input"
    assert [action["id"] for action in stage["actions"]] == ["edit"]
