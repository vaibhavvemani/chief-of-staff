from pathlib import Path

from api.services.artifact_repository import ArtifactRepository
from api.services.pipeline_catalog import PipelineCatalog
from api.services.workspace_projector import WorkspaceProjector

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_workspace_projection_uses_current_verifier_attention_gate() -> None:
    projector = WorkspaceProjector(
        ArtifactRepository(repo_root=REPO_ROOT), PipelineCatalog()
    )

    workspace = projector.project("coffee-live-main")

    assert workspace["operator_status"] == "requires_attention"
    assert workspace["attention"]["verification_totals"] == {
        "supported": 109,
        "partial": 14,
        "unsupported": 5,
        "ungrounded": 1,
        "unattributed": 3,
    }
    assert workspace["attention"]["blocking_total"] == 9
    states = {stage["slug"]: stage["state"] for stage in workspace["stages"]}
    assert states["content"] == "requires_attention"
    assert states["package"] == "requires_attention"


def test_workspace_projection_lists_runtime_and_committed_courses(tmp_path: Path) -> None:
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
    )
    from api.services.decision_service import DecisionService

    DecisionService(repository, PipelineCatalog()).create_course(
        subject="Indoor herbs",
        description=None,
        constraints=[],
        known_source_locators=[],
        course_id="indoor-herbs",
    )
    courses = WorkspaceProjector(repository, PipelineCatalog()).list_courses()
    by_id = {course["course_id"]: course for course in courses}

    assert by_id["indoor-herbs"]["source"] == "runtime"
    assert by_id["indoor-herbs"]["read_only"] is False
    assert by_id["coffee-acceptance"]["source"] == "example_acceptance"
    assert by_id["coffee-acceptance"]["read_only"] is True
