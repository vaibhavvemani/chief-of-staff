from __future__ import annotations

from pathlib import Path

import pytest

from api.services.artifact_repository import ArtifactRepository
from api.services.lifecycle import InvalidationService
from api.services.pipeline_catalog import PipelineCatalog
from orchestrator import make_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_catalog_derives_transitive_dependencies_from_pipeline_contracts() -> None:
    catalog = PipelineCatalog()

    assert set(catalog.downstream_artifacts({"brief"})) == {
        "course_outcomes",
        "research_dossier",
        "approved_source_registry",
        "course_model",
        "blueprint",
        "content_package",
        "content_progress",
        "content_review",
        "lesson_plan",
        "render_manifest",
        "run_summary",
    }
    assert set(catalog.downstream_artifacts({"approved_source_registry"})) == {
        "course_model",
        "blueprint",
        "content_package",
        "content_progress",
        "content_review",
        "lesson_plan",
        "render_manifest",
        "run_summary",
    }
    assert set(catalog.downstream_artifacts({"lesson_plan"})) == {
        "render_manifest",
        "run_summary",
    }


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (
            "brief",
            {
                "course_outcomes",
                "research_dossier",
                "approved_source_registry",
                "course_model",
                "blueprint",
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            },
        ),
        (
            "course_outcomes",
            {
                "research_dossier",
                "approved_source_registry",
                "course_model",
                "blueprint",
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            },
        ),
        (
            "research_dossier",
            {
                "approved_source_registry",
                "course_model",
                "blueprint",
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            },
        ),
        (
            "approved_source_registry",
            {
                "course_model",
                "blueprint",
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            },
        ),
        (
            "course_model",
            {
                "blueprint",
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            },
        ),
        (
            "blueprint",
            {
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            },
        ),
        (
            "content_package",
            {"content_review", "lesson_plan", "render_manifest", "run_summary"},
        ),
        ("lesson_plan", {"render_manifest", "run_summary"}),
    ],
)
def test_each_consequential_stage_change_has_an_exact_stale_set(
    changed: str, expected: set[str]
) -> None:
    assert set(PipelineCatalog().downstream_artifacts({changed})) == expected


def test_explicit_invalidation_preserves_bodies_and_marks_descendants_stale(
    tmp_path: Path,
) -> None:
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    course_id = "invalidation-course"
    artifacts = (
        ("subject_request", []),
        ("brief", ["subject_request"]),
        ("course_outcomes", ["brief"]),
        ("research_dossier", ["brief", "course_outcomes"]),
        ("approved_source_registry", ["research_dossier"]),
        ("course_model", ["approved_source_registry"]),
        ("blueprint", ["course_model"]),
        ("content_package", ["course_model", "blueprint"]),
        ("content_progress", ["course_model", "blueprint"]),
        ("content_review", ["content_package"]),
        ("lesson_plan", ["content_package"]),
        ("render_manifest", ["lesson_plan"]),
        ("run_summary", ["render_manifest"]),
    )
    body_checksums: dict[str, str] = {}
    for artifact_type, inputs in artifacts:
        artifact = make_artifact(
            course_id,
            artifact_type,
            "test",
            body={"marker": artifact_type},
            inputs=inputs,
        )
        artifact["status"] = "approved"
        saved = repository.save(artifact)
        body_checksums[artifact_type] = repository.checksum(saved["body"])

    invalidated = InvalidationService(repository, catalog).invalidate(
        course_id,
        {"course_model"},
        reason="Course Model reopened by the course director.",
    )

    invalidated_types = {artifact["artifact_type"] for artifact in invalidated}
    assert invalidated_types == {
        "blueprint",
        "content_package",
        "content_progress",
        "content_review",
        "lesson_plan",
        "render_manifest",
        "run_summary",
    }
    assert repository.require(course_id, "course_model")["status"] == "approved"
    for artifact_type in invalidated_types:
        artifact = repository.require(course_id, artifact_type)
        assert artifact["status"] == "stale"
        assert repository.checksum(artifact["body"]) == body_checksums[artifact_type]
