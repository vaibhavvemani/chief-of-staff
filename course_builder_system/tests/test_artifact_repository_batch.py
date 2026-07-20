from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

import api.services.artifact_repository as repository_module
from api.services.artifact_repository import (
    ArtifactNotFound,
    ArtifactRepository,
    VersionConflict,
)
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


@pytest.mark.parametrize("invalid_bytes", [b"null\n", b"[]\n"])
def test_save_batch_missing_rejects_existing_non_object_without_changing_bytes(
    tmp_path: Path,
    invalid_bytes: bytes,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-non-object"
    root = repository.courses_root / course_id
    root.mkdir(parents=True)
    target = root / "brief.json"
    target.write_bytes(invalid_bytes)

    with pytest.raises(ValueError, match="artifact is not a JSON object"):
        repository.save_batch(
            [(_artifact(course_id, "brief", marker="replacement"), "missing")]
        )

    assert target.read_bytes() == invalid_bytes
    assert not list(root.glob(".*"))


def test_save_batch_staging_failure_removes_new_empty_course_directory(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-staging-failure"
    invalid = _artifact(course_id, "brief", marker="invalid")
    invalid["body"]["not_json"] = {"set values are not JSON serializable"}

    with pytest.raises(TypeError, match="not JSON serializable"):
        repository.save_batch([(invalid, "missing")])

    assert not (repository.courses_root / course_id).exists()
    with pytest.raises(ArtifactNotFound):
        repository.locate(course_id)


def test_save_batch_later_staging_failure_preserves_files_and_cleans_temps(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-later-staging-failure"
    current = repository.save(_artifact(course_id, "brief", marker="current"))
    root = repository.courses_root / course_id
    before = (root / "brief.json").read_bytes()
    changed = deepcopy(current)
    changed["body"]["marker"] = "changed"
    invalid = _artifact(course_id, "course_outcomes", marker="invalid")
    invalid["body"]["not_json"] = {"set values are not JSON serializable"}

    with pytest.raises(TypeError, match="not JSON serializable"):
        repository.save_batch(
            [
                (changed, repository.checksum(current)),
                (invalid, "missing"),
            ]
        )

    assert (root / "brief.json").read_bytes() == before
    assert not (root / "course_outcomes.json").exists()
    assert not list(root.glob(".*"))


def test_save_batch_partial_new_transaction_removes_new_empty_course_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-new-course-rollback"
    root = repository.courses_root / course_id
    real_replace = repository_module.os.replace

    def fail_second_replacement(source: str | Path, target: str | Path) -> None:
        if (
            Path(target).name == "course_outcomes.json"
            and ".rollback." not in Path(source).name
        ):
            raise OSError("injected new-course replacement failure")
        real_replace(source, target)

    monkeypatch.setattr(repository_module.os, "replace", fail_second_replacement)

    with pytest.raises(OSError, match="injected new-course replacement failure"):
        repository.save_batch(
            [
                (_artifact(course_id, "brief", marker="first"), "missing"),
                (_artifact(course_id, "course_outcomes", marker="second"), "missing"),
            ]
        )

    assert not root.exists()
    with pytest.raises(ArtifactNotFound):
        repository.locate(course_id)


def test_save_batch_cleanup_aggregates_every_failure_without_masking_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-cleanup-aggregate"
    first = repository.save(_artifact(course_id, "brief", marker="first"))
    second = repository.save(_artifact(course_id, "course_outcomes", marker="second"))
    third = repository.save(_artifact(course_id, "research_dossier", marker="third"))
    changed = [deepcopy(first), deepcopy(second), deepcopy(third)]
    for artifact in changed:
        artifact["body"]["marker"] += " changed"
    root = repository.courses_root / course_id
    real_replace = repository_module.os.replace
    real_unlink = Path.unlink
    cleanup_attempts: list[str] = []

    def fail_commit_and_rollback(source: str | Path, target: str | Path) -> None:
        source_path = Path(source)
        target_path = Path(target)
        if (
            target_path.name == "course_outcomes.json"
            and ".rollback." not in source_path.name
        ):
            raise OSError("injected commit failure")
        if target_path.name == "brief.json" and ".rollback." in source_path.name:
            raise PermissionError("injected rollback failure")
        real_replace(source, target)

    def fail_staged_cleanup(self: Path, *args, **kwargs) -> None:
        for artifact_type in ("course_outcomes", "research_dossier"):
            if self.name.startswith(f".{artifact_type}.") and ".rollback." not in self.name:
                cleanup_attempts.append(artifact_type)
                raise PermissionError(f"injected {artifact_type} cleanup failure")
        real_unlink(self, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(repository_module.os, "replace", fail_commit_and_rollback)
        patcher.setattr(Path, "unlink", fail_staged_cleanup)
        with pytest.raises(RuntimeError) as exc_info:
            repository.save_batch(
                [
                    (changed[0], repository.checksum(first)),
                    (changed[1], repository.checksum(second)),
                    (changed[2], repository.checksum(third)),
                ]
            )

    message = str(exc_info.value)
    assert message.startswith("artifact batch failed and rollback was incomplete")
    assert "injected rollback failure" in message
    assert "transaction cleanup was also incomplete" in message
    assert "injected course_outcomes cleanup failure" in message
    assert "injected research_dossier cleanup failure" in message
    assert cleanup_attempts == ["course_outcomes", "research_dossier"]
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert isinstance(exc_info.value.__cause__.__cause__, OSError)

    for staged_path in root.glob(".*"):
        staged_path.unlink()


def test_save_batch_uses_one_timestamp_and_returns_persisted_checksums(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    course_id = "batch-timestamp-checksum"

    saved = repository.save_batch(
        [
            (_artifact(course_id, "brief", marker="first"), "missing"),
            (_artifact(course_id, "course_outcomes", marker="second"), "missing"),
        ]
    )
    persisted = [
        repository.require(course_id, artifact["artifact_type"])
        for artifact in saved
    ]

    assert len({artifact["updated_at"] for artifact in saved}) == 1
    assert saved == persisted
    assert [repository.checksum(artifact) for artifact in saved] == [
        repository.checksum(artifact) for artifact in persisted
    ]


def test_save_batch_rejects_duplicate_and_cross_course_targets_before_writes(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    first = _artifact("batch-one", "brief", marker="first")

    with pytest.raises(ValueError, match="duplicate target"):
        repository.save_batch([(first, "missing"), (deepcopy(first), "missing")])
    with pytest.raises(ValueError, match="exactly one course"):
        repository.save_batch(
            [
                (first, "missing"),
                (_artifact("batch-two", "course_outcomes", marker="second"), "missing"),
            ]
        )

    assert not repository.courses_root.exists()


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
