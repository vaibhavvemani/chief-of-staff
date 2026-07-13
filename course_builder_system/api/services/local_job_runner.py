"""Small durable in-process job runner for the single-director prototype."""

from __future__ import annotations

import fcntl
import json
import os
import threading
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.services.artifact_repository import ArtifactRepository

TERMINAL_JOB_STATES = frozenset({"completed", "failed", "cancelled"})


class CourseBusy(RuntimeError):
    pass


class JobNotFound(FileNotFoundError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class CourseMutationLocks:
    """Combine an in-process lock with a non-blocking advisory file lock."""

    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root.resolve()
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def acquire(self, course_id: str, *, blocking: bool = False) -> Iterator[None]:
        ArtifactRepository.validate_course_id(course_id)
        with self._guard:
            thread_lock = self._locks.setdefault(course_id, threading.Lock())
        acquired = thread_lock.acquire(blocking=blocking)
        if not acquired:
            raise CourseBusy(f"another mutation is active for course {course_id}")
        lock_dir = self.runtime_root / course_id / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        handle = (lock_dir / "mutation.lock").open("a+")
        try:
            try:
                flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
                fcntl.flock(handle.fileno(), flags)
            except BlockingIOError as exc:
                raise CourseBusy(f"another process is mutating course {course_id}") from exc
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
                thread_lock.release()


class LocalJobRunner:
    def __init__(self, runtime_root: Path, *, max_workers: int = 2) -> None:
        self.runtime_root = runtime_root.resolve()
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.locks = CourseMutationLocks(self.runtime_root)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers), thread_name_prefix="course-builder"
        )
        self._io_lock = threading.Lock()
        self._submit_lock = threading.Lock()
        self._recover_interrupted_jobs()

    def submit(
        self,
        *,
        course_id: str,
        stage: str,
        task: Callable[[Callable[..., dict[str, Any]]], dict[str, Any] | None],
    ) -> dict[str, Any]:
        ArtifactRepository.validate_course_id(course_id)
        with self._submit_lock:
            if self.active_for_course(course_id) is not None:
                raise CourseBusy(f"a mutating job is already active for course {course_id}")
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "course_id": course_id,
                "stage": stage,
                "status": "queued",
                "created_at": _now(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
            }
            self._write_job(job)
            self._emit(job, "job.queued", stage=stage, message=f"{stage} queued")
            self._executor.submit(self._execute, job_id, task)
        return job

    def get(self, job_id: str) -> dict[str, Any]:
        if not job_id or not job_id.isalnum() or len(job_id) > 64:
            raise JobNotFound("invalid job id")
        matches = list(self.runtime_root.glob(f"*/jobs/{job_id}.json"))
        if len(matches) != 1:
            raise JobNotFound(f"job not found: {job_id}")
        return json.loads(matches[0].read_text(encoding="utf-8"))

    def events(self, job_id: str, *, after: str | None = None) -> list[dict[str, Any]]:
        job = self.get(job_id)
        path = self._events_path(job["course_id"], job_id)
        if not path.is_file():
            return []
        events = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if after is None:
            return events
        for index, event in enumerate(events):
            if event.get("event_id") == after:
                return events[index + 1 :]
        return events

    def active_for_course(self, course_id: str) -> dict[str, Any] | None:
        ArtifactRepository.validate_course_id(course_id)
        jobs_dir = self.runtime_root / course_id / "jobs"
        if not jobs_dir.is_dir():
            return None
        active = []
        for path in jobs_dir.glob("*.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("status") not in TERMINAL_JOB_STATES:
                active.append(job)
        if not active:
            return None
        return max(active, key=lambda item: item.get("created_at") or "")

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _execute(
        self,
        job_id: str,
        task: Callable[[Callable[..., dict[str, Any]]], dict[str, Any] | None],
    ) -> None:
        job = self.get(job_id)
        try:
            with self.locks.acquire(job["course_id"], blocking=True):
                job["status"] = "running"
                job["started_at"] = _now()
                self._write_job(job)
                self._emit(job, "job.started", stage=job["stage"], message="Job started")

                def emit(event_type: str, **payload: Any) -> dict[str, Any]:
                    return self._emit(job, event_type, **payload)

                result = task(emit) or {}
                job["status"] = "completed"
                job["completed_at"] = _now()
                job["result"] = result
                self._write_job(job)
                self._emit(job, "job.completed", stage=job["stage"], message="Job completed")
        except Exception as exc:  # persisted failures are part of the job contract
            job["status"] = "failed"
            job["completed_at"] = _now()
            job["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self._write_job(job)
            self._emit(job, "job.failed", stage=job["stage"], message=str(exc))

    def _emit(self, job: dict[str, Any], event_type: str, **payload: Any) -> dict[str, Any]:
        event = {
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "job_id": job["job_id"],
            "course_id": job["course_id"],
            "timestamp": _now(),
            "stage": payload.pop("stage", job.get("stage")),
            **payload,
        }
        path = self._events_path(job["course_id"], job["job_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._io_lock, path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
        return event

    def _write_job(self, job: dict[str, Any]) -> None:
        path = self._job_path(job["course_id"], job["job_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with self._io_lock:
            temporary.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)

    def _job_path(self, course_id: str, job_id: str) -> Path:
        return self.runtime_root / course_id / "jobs" / f"{job_id}.json"

    def _events_path(self, course_id: str, job_id: str) -> Path:
        return self.runtime_root / course_id / "events" / f"{job_id}.jsonl"

    def _recover_interrupted_jobs(self) -> None:
        for path in self.runtime_root.glob("*/jobs/*.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("status") not in {"queued", "running"}:
                continue
            job["status"] = "failed"
            job["completed_at"] = _now()
            job["error"] = {
                "type": "InterruptedJob",
                "message": "The API process stopped before this job completed; rerun is safe.",
            }
            self._write_job(job)
            self._emit(
                job,
                "job.failed",
                stage=job.get("stage"),
                message=job["error"]["message"],
            )
