"""Confined access to runtime courses and committed read-only snapshots."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
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
        "source_repair",
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


@dataclass
class _PreparedSave:
    artifact_type: str
    path: Path
    value: dict[str, Any]
    expected_checksum: str | None
    original_bytes: bytes | None = None
    staged_path: Path | None = None


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
        return self._save_batch([(artifact, expected_checksum)], require_exact=False)[0]

    def save_batch(
        self,
        writes: Iterable[tuple[dict[str, Any], str]],
    ) -> list[dict[str, Any]]:
        """Persist one course's artifacts as an exact-precondition transaction.

        Every target is checked before a canonical artifact is touched. Replacements
        are staged beside their targets and committed only after a second preflight.
        If any replacement fails, every already-replaced target is restored to its
        exact original bytes (or removed when it was absent before the transaction).

        Callers must supply an expected checksum for every target. Use the literal
        ``"missing"`` when creation is expected.
        """
        return self._save_batch(list(writes), require_exact=True)

    def _save_batch(
        self,
        writes: list[tuple[dict[str, Any], str | None]],
        *,
        require_exact: bool,
    ) -> list[dict[str, Any]]:
        if not writes:
            return []

        prepared: list[_PreparedSave] = []
        course_id: str | None = None
        targets: set[Path] = set()
        transaction_timestamp = utc_now()
        for artifact, expected_checksum in writes:
            if require_exact and not isinstance(expected_checksum, str):
                raise ValueError("batch saves require an expected checksum for every artifact")
            item_course_id = self.validate_course_id(str(artifact.get("course_id", "")))
            artifact_type = self.validate_artifact_type(str(artifact.get("artifact_type", "")))
            if course_id is None:
                course_id = item_course_id
            elif item_course_id != course_id:
                raise ValueError("batch saves must target exactly one course")
            location = self.runtime_location(item_course_id)
            try:
                existing_location = self.locate(item_course_id)
            except ArtifactNotFound:
                existing_location = location
            if existing_location.read_only:
                raise ReadOnlyCourse(f"committed example course is read-only: {item_course_id}")
            path = self._confined(location.artifact_root, f"{artifact_type}.json")
            if path in targets:
                raise ValueError(f"batch save contains duplicate target: {artifact_type}")
            targets.add(path)
            to_save = dict(artifact)
            to_save["updated_at"] = transaction_timestamp
            prepared.append(
                _PreparedSave(
                    artifact_type=artifact_type,
                    path=path,
                    value=to_save,
                    expected_checksum=expected_checksum,
                )
            )

        # First preflight happens before even temporary replacement files exist.
        self._preflight(prepared)
        if course_id is None:  # pragma: no cover - guarded by the non-empty write list
            raise RuntimeError("batch save did not resolve a course")
        course_dir = self.runtime_location(course_id).artifact_root
        course_dir_created = False
        try:
            try:
                course_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                pass
            else:
                course_dir_created = True
            for item in prepared:
                item.path.parent.mkdir(parents=True, exist_ok=True)
                item.staged_path = self._stage_json(item)
            # Staging can take time. Recheck every target and retain the exact bytes
            # that this transaction is responsible for restoring.
            self._preflight(prepared)
            self._commit_prepared(prepared)
        except BaseException as exc:
            cleanup_failures = self._cleanup_staged(prepared)
            if course_dir_created:
                cleanup_failures.extend(self._remove_created_course_dir(course_dir))
            if cleanup_failures:
                primary_error = str(exc) or type(exc).__name__
                raise RuntimeError(
                    f"{primary_error}; transaction cleanup was also incomplete: "
                    + "; ".join(cleanup_failures)
                ) from exc
            raise
        cleanup_failures = self._cleanup_staged(prepared)
        if cleanup_failures:  # pragma: no cover - committed replacements consume every temp
            raise RuntimeError(
                "artifact batch committed but staged cleanup was incomplete: "
                + "; ".join(cleanup_failures)
            )
        return [item.value for item in prepared]

    def _preflight(self, prepared: list[_PreparedSave]) -> None:
        originals: list[bytes | None] = []
        for item in prepared:
            original = item.path.read_bytes() if item.path.is_file() else None
            if original is None:
                current = None
                actual = "missing"
            else:
                current = json.loads(original.decode("utf-8"))
                if not isinstance(current, dict):
                    raise ValueError(f"artifact is not a JSON object: {item.path}")
                actual = self.checksum(current)
            if item.expected_checksum is not None:
                if actual != item.expected_checksum:
                    raise VersionConflict(actual)
            originals.append(original)
        for item, original in zip(prepared, originals, strict=True):
            item.original_bytes = original

    @staticmethod
    def _stage_json(item: _PreparedSave) -> Path:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{item.artifact_type}.", dir=item.path.parent)
        staged_path = Path(tmp_name)
        # Record the path before serialization so the transaction-level cleanup
        # can retry and aggregate a failed unlink without masking the write error.
        item.staged_path = staged_path
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(item.value, handle, indent=2)
            handle.write("\n")
        return staged_path

    def _commit_prepared(self, prepared: list[_PreparedSave]) -> None:
        committed: list[_PreparedSave] = []
        try:
            for item in prepared:
                if item.staged_path is None:
                    raise RuntimeError(f"artifact replacement was not staged: {item.artifact_type}")
                # Include the current target before replacement. A lower-level
                # failure may be reported after the destination was already changed.
                committed.append(item)
                os.replace(item.staged_path, item.path)
                item.staged_path = None
        except BaseException as exc:
            rollback_failures: list[str] = []
            for item in reversed(committed):
                try:
                    self._restore_original(item)
                except BaseException as rollback_exc:
                    rollback_failures.append(
                        f"{item.artifact_type}: {type(rollback_exc).__name__}: {rollback_exc}"
                    )
            if rollback_failures:
                raise RuntimeError(
                    "artifact batch failed and rollback was incomplete: "
                    + "; ".join(rollback_failures)
                ) from exc
            raise

    @staticmethod
    def _restore_original(item: _PreparedSave) -> None:
        if item.original_bytes is None:
            item.path.unlink(missing_ok=True)
            return
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{item.artifact_type}.rollback.", dir=item.path.parent
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(item.original_bytes)
            os.replace(tmp_name, item.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _cleanup_staged(prepared: list[_PreparedSave]) -> list[str]:
        failures: list[str] = []
        for item in prepared:
            if item.staged_path is None:
                continue
            try:
                item.staged_path.unlink(missing_ok=True)
            except BaseException as exc:
                failures.append(
                    f"{item.artifact_type} staged file: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                item.staged_path = None
        return failures

    @staticmethod
    def _remove_created_course_dir(course_dir: Path) -> list[str]:
        """Remove only an empty course directory created by this transaction."""
        try:
            course_dir.rmdir()
        except FileNotFoundError:
            return []
        except OSError as exc:
            # Another cooperating or out-of-band writer may have populated the
            # directory. Never remove content that this transaction did not stage.
            if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
                return []
            return [f"course directory: {type(exc).__name__}: {exc}"]
        return []

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
