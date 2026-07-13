from __future__ import annotations

from pathlib import Path

import pytest

from api.services.artifact_repository import (
    ArtifactRepository,
    ReadOnlyCourse,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repository_rejects_course_artifact_and_output_path_traversal(tmp_path: Path) -> None:
    courses_root = tmp_path / "courses"
    rendered_root = tmp_path / "rendered"
    output = rendered_root / "safe-course" / "course_overview.md"
    output.parent.mkdir(parents=True)
    output.write_text("# Safe output\n", encoding="utf-8")
    (courses_root / "safe-course").mkdir(parents=True)

    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=rendered_root,
        include_examples=False,
    )

    with pytest.raises(ValueError):
        repository.locate("../coffee-live-main")
    with pytest.raises(ValueError):
        repository.load("safe-course", "../brief")
    with pytest.raises(ValueError):
        repository.output_path("safe-course", "../secret.md")
    with pytest.raises(ValueError):
        repository.output_path("safe-course", "/etc/passwd")

    assert repository.output_path("safe-course", "course_overview.md") == output


def test_committed_course_snapshots_are_read_only() -> None:
    repository = ArtifactRepository(repo_root=REPO_ROOT)
    existing = repository.require("coffee-live-main", "brief")

    with pytest.raises(ReadOnlyCourse):
        repository.save(existing, expected_checksum=repository.checksum(existing))
