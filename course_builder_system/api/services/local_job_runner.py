"""Small durable in-process job runner for the single-director prototype."""

from __future__ import annotations

import fcntl
import json
import os
import re
import threading
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.services.artifact_repository import ArtifactRepository

TERMINAL_JOB_STATES = frozenset({"completed", "failed", "cancelled"})
_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_EVENT_TEXT_FIELDS = frozenset(
    {
        "stage",
        "mode",
        "message",
        "subtopic_id",
        "asset_id",
        "record_id",
        "provider",
        "model",
        "error_type",
        "strategy",
        "repair_id",
    }
)
_EVENT_NUMBER_FIELDS = frozenset(
    {
        "call_index",
        "input_chars",
        "max_tokens",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "retry_count",
        "attempt",
        "attempts",
        "hard_blocker_total",
        "candidate_count",
    }
)
_EVENT_BOOLEAN_FIELDS = frozenset({"cache_hit"})
_EVENT_ID_LIST_FIELDS = frozenset({"asset_ids"})


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
        self._recovered_interrupted_jobs = self._recover_interrupted_jobs()

    def submit(
        self,
        *,
        course_id: str,
        stage: str,
        operation: str = "run",
        context: dict[str, str] | None = None,
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
                "operation": operation,
                "context": dict(context or {}),
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

    def recovered_interrupted_jobs(self) -> list[dict[str, Any]]:
        """Return jobs this runner changed from active to failed during startup."""
        return deepcopy(self._recovered_interrupted_jobs)

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

    def latest_for_stage(self, course_id: str, stage: str) -> dict[str, Any] | None:
        ArtifactRepository.validate_course_id(course_id)
        jobs_dir = self.runtime_root / course_id / "jobs"
        if not jobs_dir.is_dir():
            return None
        matches: list[dict[str, Any]] = []
        for path in jobs_dir.glob("*.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("stage") == stage:
                matches.append(job)
        if not matches:
            return None
        return max(matches, key=lambda item: item.get("created_at") or "")

    def event_emitter(
        self,
        course_id: str,
        stage: str,
    ) -> Callable[..., dict[str, Any]]:
        """Create one durable safe-event stream for a synchronous live operation."""
        ArtifactRepository.validate_course_id(course_id)
        if not isinstance(stage, str) or not stage:
            raise ValueError("event stage must be a non-empty string")
        event_job = {
            "job_id": f"sync{uuid.uuid4().hex}",
            "course_id": course_id,
            "stage": stage,
        }

        def emit(event_type: str, **payload: Any) -> dict[str, Any]:
            return self._emit(event_job, event_type, **payload)

        return emit

    def activity_for_course(
        self,
        course_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read recent persisted events, returning only the operator-safe contract."""
        ArtifactRepository.validate_course_id(course_id)
        if type(limit) is not int or limit < 1 or limit > 500:
            raise ValueError("activity limit must be an integer from 1 to 500")
        events_dir = self.runtime_root / course_id / "events"
        if not events_dir.is_dir():
            return []
        events: list[dict[str, Any]] = []
        for path in events_dir.glob("*.jsonl"):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                safe = _safe_event(event)
                if safe.get("course_id") == course_id:
                    events.append(safe)
        events.sort(key=lambda event: (str(event.get("timestamp") or ""), event["event_id"]))
        return events[-limit:]

    def diagnostics_for_course(self, course_id: str) -> dict[str, Any]:
        """Aggregate safe model-call telemetry by stage from persisted events."""
        events = self.activity_for_course(course_id, limit=500)
        by_stage: dict[str, dict[str, Any]] = {}
        for event in events:
            event_type = event.get("event_type")
            if event_type not in {
                "model.call.completed",
                "model.call.failed",
                "job.failed",
                "unit.completed",
                "unit.failed",
            }:
                continue
            stage = str(event.get("stage") or "unknown")
            summary = by_stage.setdefault(
                stage,
                {
                    "stage": stage,
                    "providers": set(),
                    "models": set(),
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "cache_hits": 0,
                    "retries": 0,
                    "errors": [],
                },
            )
            if event_type == "job.failed":
                summary["errors"].append(
                    {
                        "type": str(event.get("error_type") or "JobFailed"),
                        "message": str(event.get("message") or "The job failed safely."),
                        "at": event.get("timestamp"),
                    }
                )
                continue
            if event_type in {"unit.completed", "unit.failed"}:
                summary["retries"] += max(
                    _safe_nonnegative_int(event.get("attempts")) - 1,
                    0,
                )
                continue
            provider = event.get("provider")
            model = event.get("model")
            if isinstance(provider, str) and provider:
                summary["providers"].add(provider)
            if isinstance(model, str) and model:
                summary["models"].add(model)
            summary["calls"] += 1
            summary["input_tokens"] += _safe_nonnegative_int(event.get("input_tokens"))
            summary["output_tokens"] += _safe_nonnegative_int(event.get("output_tokens"))
            cost = event.get("estimated_cost_usd")
            if isinstance(cost, int | float) and not isinstance(cost, bool) and cost >= 0:
                summary["estimated_cost_usd"] += float(cost)
            summary["cache_hits"] += int(event.get("cache_hit") is True)
            summary["retries"] += _safe_nonnegative_int(event.get("retry_count"))
            if event_type == "model.call.failed":
                summary["errors"].append(
                    {
                        "type": str(event.get("error_type") or "ModelCallFailed"),
                        "message": str(event.get("message") or "The model call failed safely."),
                        "at": event.get("timestamp"),
                    }
                )
        stages = []
        for stage in sorted(by_stage):
            summary = by_stage[stage]
            summary["providers"] = sorted(summary["providers"])
            summary["models"] = sorted(summary["models"])
            summary["estimated_cost_usd"] = round(summary["estimated_cost_usd"], 8)
            summary["errors"] = summary["errors"][-10:]
            stages.append(summary)
        return {
            "stages": stages,
            "totals": {
                "calls": sum(item["calls"] for item in stages),
                "input_tokens": sum(item["input_tokens"] for item in stages),
                "output_tokens": sum(item["output_tokens"] for item in stages),
                "estimated_cost_usd": round(
                    sum(item["estimated_cost_usd"] for item in stages),
                    8,
                ),
                "cache_hits": sum(item["cache_hits"] for item in stages),
                "retries": sum(item["retries"] for item in stages),
                "errors": sum(len(item["errors"]) for item in stages),
            },
        }

    @contextmanager
    def mutate_now(self, course_id: str) -> Iterator[None]:
        """Serialize a synchronous mutation against queued and running jobs."""
        ArtifactRepository.validate_course_id(course_id)
        with self._submit_lock:
            if self.active_for_course(course_id) is not None:
                raise CourseBusy(f"a mutating job is already active for course {course_id}")
            with self.locks.acquire(course_id, blocking=False):
                yield

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
            job["error"] = {
                "type": type(exc).__name__,
                "message": _safe_error_message(exc),
            }
            self._write_job(job)
            self._emit(
                job,
                "job.failed",
                stage=job["stage"],
                error_type=job["error"]["type"],
                message=job["error"]["message"],
            )

    def _emit(self, job: dict[str, Any], event_type: str, **payload: Any) -> dict[str, Any]:
        if not _EVENT_TYPE.fullmatch(event_type):
            raise ValueError(f"invalid job event type: {event_type!r}")
        payload = {"stage": payload.pop("stage", job.get("stage")), **payload}
        event = {
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "job_id": job["job_id"],
            "course_id": job["course_id"],
            "timestamp": _now(),
            **_safe_event_payload(payload),
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

    def _recover_interrupted_jobs(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
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
                error_type=job["error"]["type"],
                message=job["error"]["message"],
            )
            recovered.append(deepcopy(job))
        return recovered


def _safe_error_message(exc: Exception) -> str:
    """Persist a bounded operator-safe error without credential-like tokens."""
    message = str(exc).strip() or type(exc).__name__
    secret_field = (
        r"[a-z0-9_-]*(?:api[_-]?key|authorization|credential|token|secret|password|"
        r"private[_-]?key|access[_-]?key)[a-z0-9_-]*"
    )
    # Structured provider errors often render mappings with quoted keys and values.
    # Redact those before the simpler unquoted key/value pass so whitespace inside an
    # Authorization value cannot leak the remainder of the credential.
    message = re.sub(
        rf"(?i)(?:[\"']?)(?P<key>{secret_field})(?:[\"']?)"
        r"\s*[:=]\s*(?P<quote>[\"']).*?(?P=quote)",
        lambda match: f"{match.group('key')}=[redacted]",
        message,
    )
    message = re.sub(
        r"(?i)(?:[\"']?)(?P<key>[a-z0-9_-]*authorization[a-z0-9_-]*)"
        r"(?:[\"']?)\s*[:=]\s*[^,;}}]+",
        lambda match: f"{match.group('key')}=[redacted]",
        message,
    )
    message = re.sub(
        rf"(?i)(?:[\"']?)(?P<key>{secret_field})(?:[\"']?)"
        r"\s*[:=]\s*[^\s,;}}]+",
        lambda match: f"{match.group(1)}=[redacted]",
        message,
    )
    message = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [redacted]", message)
    message = re.sub(r"\b(?:sk|key)-[A-Za-z0-9_-]{12,}\b", "[redacted]", message)
    return message[:2000]


def _safe_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Allowlist bounded event telemetry and drop accidental content/prompt bodies."""
    safe: dict[str, Any] = {}
    for field in _EVENT_TEXT_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str):
            continue
        cleaned = _safe_error_message(RuntimeError(value))
        safe[field] = cleaned[:500] if field == "message" else cleaned[:200]
    for field in _EVENT_NUMBER_FIELDS:
        value = payload.get(field)
        if isinstance(value, int | float) and not isinstance(value, bool) and value >= 0:
            safe[field] = value
    for field in _EVENT_BOOLEAN_FIELDS:
        value = payload.get(field)
        if isinstance(value, bool):
            safe[field] = value
    for field in _EVENT_ID_LIST_FIELDS:
        value = payload.get(field)
        if isinstance(value, list):
            safe[field] = [
                _safe_error_message(RuntimeError(item))[:200]
                for item in value[:100]
                if isinstance(item, str)
            ]
    progress = payload.get("progress")
    if isinstance(progress, dict):
        safe["progress"] = {
            field: value
            for field in ("completed", "expected")
            if isinstance((value := progress.get(field)), int)
            and not isinstance(value, bool)
            and value >= 0
        }
    return safe


def _safe_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("event_type") or "")
    if not _EVENT_TYPE.fullmatch(event_type):
        event_type = "job.event_invalid"
    return {
        "event_id": str(event.get("event_id") or "")[:64],
        "event_type": event_type,
        "job_id": str(event.get("job_id") or "")[:64],
        "course_id": str(event.get("course_id") or "")[:128],
        "timestamp": str(event.get("timestamp") or "")[:64],
        **_safe_event_payload(event),
    }


def _safe_nonnegative_int(value: Any) -> int:
    return value if type(value) is int and value >= 0 else 0
