"""Confined access to runtime courses and committed read-only snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COURSE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
ARTIFACT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CANONICAL_ARTIFACT_TYPES = frozenset(
    {
        "subject_request",
        "brief",
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
        # Historical prototype artifacts remain inspectable.
        "domain_model",
        "toc",
    }
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class CourseLocation:
    course_id: str
    artifact_root: Path
    output_root: Path | None
    source: str
    read_only: bool


class ArtifactNotFound(FileNotFoundError):
    pass


class ReadOnlyCourse(PermissionError):
    pass


class VersionConflict(RuntimeError):
    def __init__(self, actual_checksum: str) -> None:
        super().__init__("artifact changed since it was loaded")
        self.actual_checksum = actual_checksum


class ArtifactRepository:
    """Load artifacts without allowing IDs to become filesystem paths."""

    def __init__(
        self,
        *,
        repo_root: Path,
        courses_root: Path | None = None,
        rendered_root: Path | None = None,
        include_examples: bool = True,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.courses_root = (courses_root or self.repo_root / "courses").resolve()
        self.rendered_root = (rendered_root or self.repo_root / "rendered_courses").resolve()
        self.include_examples = include_examples

    @staticmethod
    def validate_course_id(course_id: str) -> str:
        if not COURSE_ID_PATTERN.fullmatch(course_id):
            raise ValueError(
                "course_id must be 1-64 lowercase letters, digits, or hyphens"
            )
        return course_id

    @staticmethod
    def validate_artifact_type(artifact_type: str) -> str:
        if (
            not ARTIFACT_TYPE_PATTERN.fullmatch(artifact_type)
            or artifact_type not in CANONICAL_ARTIFACT_TYPES
        ):
            raise ValueError(f"unsupported artifact type: {artifact_type!r}")
        return artifact_type

    def runtime_location(self, course_id: str) -> CourseLocation:
        course_id = self.validate_course_id(course_id)
        return CourseLocation(
            course_id,
            self.courses_root / course_id,
            self.rendered_root / course_id,
            "runtime",
            False,
        )

    def locate(self, course_id: str) -> CourseLocation:
        course_id = self.validate_course_id(course_id)
        runtime = self.runtime_location(course_id)
        if runtime.artifact_root.is_dir():
            return runtime
        if self.include_examples:
            for source, parent in (
                ("example_acceptance", self.repo_root / "examples" / "acceptance"),
                ("example_live", self.repo_root / "examples" / "live-runs"),
            ):
                root = parent / course_id
                artifacts = root / "course_artifacts"
                if artifacts.is_dir():
                    return CourseLocation(
                        course_id,
                        artifacts.resolve(),
                        (root / "rendered_course").resolve(),
                        source,
                        True,
                    )
        raise ArtifactNotFound(f"course not found: {course_id}")

    def list_locations(self) -> list[CourseLocation]:
        found: dict[str, CourseLocation] = {}
        if self.courses_root.is_dir():
            for path in self.courses_root.iterdir():
                if path.is_dir() and COURSE_ID_PATTERN.fullmatch(path.name):
                    found[path.name] = self.runtime_location(path.name)
        if self.include_examples:
            for source, parent in (
                ("example_acceptance", self.repo_root / "examples" / "acceptance"),
                ("example_live", self.repo_root / "examples" / "live-runs"),
            ):
                if not parent.is_dir():
                    continue
                for root in parent.iterdir():
                    if (
                        root.name not in found
                        and COURSE_ID_PATTERN.fullmatch(root.name)
                        and (root / "course_artifacts").is_dir()
                    ):
                        found[root.name] = CourseLocation(
                            root.name,
                            (root / "course_artifacts").resolve(),
                            (root / "rendered_course").resolve(),
                            source,
                            True,
                        )
        return sorted(found.values(), key=lambda item: item.course_id)

    def list_artifact_types(self, course_id: str) -> list[str]:
        location = self.locate(course_id)
        return sorted(
            path.stem
            for path in location.artifact_root.glob("*.json")
            if path.is_file() and path.stem in CANONICAL_ARTIFACT_TYPES
        )

    def load(self, course_id: str, artifact_type: str) -> dict[str, Any] | None:
        location = self.locate(course_id)
        artifact_type = self.validate_artifact_type(artifact_type)
        path = self._confined(location.artifact_root, f"{artifact_type}.json")
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"artifact is not a JSON object: {path}")
        return data

    def require(self, course_id: str, artifact_type: str) -> dict[str, Any]:
        artifact = self.load(course_id, artifact_type)
        if artifact is None:
            raise ArtifactNotFound(f"artifact not found: {course_id}/{artifact_type}")
        return artifact

    def save(
        self,
        artifact: dict[str, Any],
        *,
        expected_checksum: str | None = None,
    ) -> dict[str, Any]:
        course_id = self.validate_course_id(str(artifact.get("course_id", "")))
        artifact_type = self.validate_artifact_type(str(artifact.get("artifact_type", "")))
        location = self.runtime_location(course_id)
        try:
            existing_location = self.locate(course_id)
        except ArtifactNotFound:
            existing_location = location
        if existing_location.read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        path = self._confined(location.artifact_root, f"{artifact_type}.json")
        current = None
        if path.is_file():
            current = json.loads(path.read_text(encoding="utf-8"))
        if expected_checksum is not None:
            actual = self.checksum(current) if current is not None else "missing"
            if actual != expected_checksum:
                raise VersionConflict(actual)
        to_save = dict(artifact)
        to_save["updated_at"] = utc_now()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{artifact_type}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(to_save, handle, indent=2)
                handle.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return to_save

    def output_path(self, course_id: str, relative_path: str) -> Path:
        location = self.locate(course_id)
        if location.output_root is None:
            raise ArtifactNotFound(f"course has no rendered output: {course_id}")
        if not relative_path or relative_path.startswith(("/", "\\")):
            raise ValueError("output path must be relative")
        path = self._confined(location.output_root, relative_path)
        if not path.is_file():
            raise ArtifactNotFound(f"rendered output not found: {relative_path}")
        return path

    @staticmethod
    def checksum(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _confined(root: Path, relative: str) -> Path:
        root = root.resolve()
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("path escapes its configured root") from exc
        return path
