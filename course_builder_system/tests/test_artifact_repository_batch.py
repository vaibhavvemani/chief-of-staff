from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

import api.services.artifact_repository as repository_module
from api.services.artifact_repository import ArtifactRepository, VersionConflict
from api.services.lifecycle import ImpactPreviewService, InvalidationService
from api.services.pipeline_catalog import PipelineCatalog
from orchestrator import make_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repository(tmp_path: Path) -> ArtifactRepository:
    return ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )


def _artifact(course_id: str, artifact_type: str, *, marker: str) -> dict:
    artifact = make_artifact(
        course_id,
        artifact_type,
        "test",
        body={"marker": marker},
        inputs=[],
    )
    artifact["status"] = "approved"
    return artifact


def test_save_batch_preflights_every_target_before_replacing_any_file(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-preflight"
    first = repository.save(_artifact(course_id, "brief", marker="first"))
    second = repository.save(_artifact(course_id, "course_outcomes", marker="second"))
    root = repository.courses_root / course_id
    original_bytes = {
        "brief": (root / "brief.json").read_bytes(),
        "course_outcomes": (root / "course_outcomes.json").read_bytes(),
    }
    changed_first = deepcopy(first)
    changed_first["body"]["marker"] = "changed first"
    changed_second = deepcopy(second)
    changed_second["body"]["marker"] = "changed second"

    with pytest.raises(VersionConflict) as exc_info:
        repository.save_batch(
            [
                (changed_first, repository.checksum(first)),
                (changed_second, "not-the-current-checksum"),
            ]
        )

    assert exc_info.value.actual_checksum == repository.checksum(second)
    assert (root / "brief.json").read_bytes() == original_bytes["brief"]
    assert (root / "course_outcomes.json").read_bytes() == original_bytes["course_outcomes"]


def test_save_batch_restores_exact_original_bytes_after_replacement_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-rollback"
    first = repository.save(_artifact(course_id, "brief", marker="first"))
    second = repository.save(_artifact(course_id, "course_outcomes", marker="second"))
    root = repository.courses_root / course_id
    original_bytes = {
        "brief": (root / "brief.json").read_bytes(),
        "course_outcomes": (root / "course_outcomes.json").read_bytes(),
    }
    changed_first = deepcopy(first)
    changed_first["body"]["marker"] = "changed first"
    changed_second = deepcopy(second)
    changed_second["body"]["marker"] = "changed second"
    real_replace = repository_module.os.replace
    failed = False

    def fail_second_replacement(source: str | Path, target: str | Path) -> None:
        nonlocal failed
        source_path = Path(source)
        target_path = Path(target)
        if (
            not failed
            and target_path.name == "course_outcomes.json"
            and source_path.name.startswith(".course_outcomes.")
            and ".rollback." not in source_path.name
        ):
            failed = True
            raise OSError("injected second replacement failure")
        real_replace(source, target)

    monkeypatch.setattr(repository_module.os, "replace", fail_second_replacement)

    with pytest.raises(OSError, match="injected second replacement failure"):
        repository.save_batch(
            [
                (changed_first, repository.checksum(first)),
                (changed_second, repository.checksum(second)),
            ]
        )

    assert failed is True
    assert (root / "brief.json").read_bytes() == original_bytes["brief"]
    assert (root / "course_outcomes.json").read_bytes() == original_bytes["course_outcomes"]
    assert not list(root.glob(".*.rollback.*"))


def test_save_batch_removes_a_new_target_when_a_later_replacement_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-new-target-rollback"
    existing = repository.save(_artifact(course_id, "course_outcomes", marker="existing"))
    root = repository.courses_root / course_id
    existing_bytes = (root / "course_outcomes.json").read_bytes()
    new_brief = _artifact(course_id, "brief", marker="new")
    changed_existing = deepcopy(existing)
    changed_existing["body"]["marker"] = "changed"
    real_replace = repository_module.os.replace
    failed = False

    def fail_existing_replacement(source: str | Path, target: str | Path) -> None:
        nonlocal failed
        source_path = Path(source)
        target_path = Path(target)
        if (
            not failed
            and target_path.name == "course_outcomes.json"
            and ".rollback." not in source_path.name
        ):
            failed = True
            raise OSError("injected existing replacement failure")
        real_replace(source, target)

    monkeypatch.setattr(repository_module.os, "replace", fail_existing_replacement)

    with pytest.raises(OSError, match="injected existing replacement failure"):
        repository.save_batch(
            [
                (new_brief, "missing"),
                (changed_existing, repository.checksum(existing)),
            ]
        )

    assert failed is True
    assert not (root / "brief.json").exists()
    assert (root / "course_outcomes.json").read_bytes() == existing_bytes


def test_invalidation_plan_is_read_only_and_composes_with_atomic_save(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    course_id = "planned-invalidation"
    course_model = repository.save(_artifact(course_id, "course_model", marker="current model"))
    blueprint = repository.save(_artifact(course_id, "blueprint", marker="current plan"))
    root = repository.courses_root / course_id
    bytes_before_plan = (root / "blueprint.json").read_bytes()

    plan = InvalidationService(repository, catalog).plan(
        course_id,
        {"course_model"},
        reason="Stale because Course Model changed.",
    )

    assert len(plan) == 1
    stale_blueprint, expected_blueprint_checksum = plan[0]
    assert stale_blueprint["artifact_type"] == "blueprint"
    assert stale_blueprint["status"] == "stale"
    assert stale_blueprint["revision_note"] == "Stale because Course Model changed."
    assert stale_blueprint["body"] == blueprint["body"]
    assert expected_blueprint_checksum == repository.checksum(blueprint)
    assert (root / "blueprint.json").read_bytes() == bytes_before_plan

    changed_model = deepcopy(course_model)
    changed_model["status"] = "draft"
    changed_model["body"]["marker"] = "changed model"
    saved = repository.save_batch([(changed_model, repository.checksum(course_model)), *plan])

    assert [artifact["artifact_type"] for artifact in saved] == [
        "course_model",
        "blueprint",
    ]
    assert repository.require(course_id, "blueprint")["status"] == "stale"
    assert repository.require(course_id, "blueprint")["body"] == blueprint["body"]


def test_course_model_edit_impact_uses_full_catalog_descendants(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    course_id = "course-model-edit-impact"
    repository.save(_artifact(course_id, "course_model", marker="model"))
    repository.save(_artifact(course_id, "blueprint", marker="plan"))
    package = _artifact(course_id, "content_package", marker="content")
    package["body"] = {
        "subtopics": [
            {
                "subtopic_id": "m1_s1",
                "assets": [{"id": "asset_one"}, {"id": "asset_two"}],
            }
        ]
    }
    repository.save(package)
    service = ImpactPreviewService(
        repository,
        PipelineCatalog(rendered_root=tmp_path / "rendered"),
    )

    preview = service.preview(
        course_id,
        "course-model",
        action="edit",
        target_type="subtopic",
        target_ids=["m1_s1"],
        operation_summary="Rescope one subtopic",
    )

    assert preview["direct_artifacts"] == ["course_model"]
    assert preview["stale_artifacts"] == ["blueprint", "content_package"]
    assert preview["targeted_assets"] == ["asset_one", "asset_two"]
    assert preview["preserved_assets"] == []
    assert preview["impact_level"] == "downstream"
