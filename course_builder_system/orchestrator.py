"""
Course Builder - Phase 0 orchestrator (the walking skeleton).

This is the ENGINE. It knows nothing about what a Course Model, Blueprint, or
Content Package actually contains. It treats every artifact as an opaque JSON *body* wrapped in
a small, fixed metadata *envelope*. Its only jobs are:

  1. run the steps in order,
  2. feed each step the artifacts it consumes,
  3. save what each step produces into a per-course folder,
  4. pause after each step for human approve / request-changes,
  5. on "request-changes", re-run ONLY that step with the feedback.

Because it depends only on the envelope (never the body), schema/content work
stays in steps.py. The envelope itself may still gain orchestrator-owned fields
- e.g. the optional `schema_version` override on `make_artifact` that lets one
artifact pin a newer schema version (Content Package v0.2) while the rest stay
v0.1. That is an envelope contract change, not a body-shape change.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "0.1"
COURSES_DIR = Path("courses")


# --------------------------------------------------------------------------
# The artifact envelope. This is the ONE contract the orchestrator depends on.
# `body` is whatever the step produced; the engine never looks inside it.
# --------------------------------------------------------------------------
def make_artifact(
    course_id: str,
    artifact_type: str,
    produced_by_step: str,
    body: dict,
    inputs: list[str],
    schema_version: str | None = None,
) -> dict:
    """Wrap a step's output body in the fixed metadata envelope.

    The lifecycle fields (status, revision, revision_note, updated_at) are
    owned by the orchestrator, not the step - they are set/overwritten when
    the artifact is saved. A step just declares identity + body + what it read.

    `schema_version` defaults to the global SCHEMA_VERSION; a step may pass an
    override so one artifact can pin a newer contract (e.g. Content Package
    "0.2") while the rest stay on the default. This is an envelope field, not
    body shape, so it lives here rather than in steps.py.
    """
    return {
        "course_id": course_id,
        "artifact_type": artifact_type,
        "produced_by_step": produced_by_step,
        "schema_version": schema_version or SCHEMA_VERSION,
        "status": "draft",  # draft -> approved (set by orchestrator)
        "revision": 0,  # bumped by orchestrator on re-run
        "revision_note": None,  # the feedback that triggered the re-run
        "inputs": inputs,  # which artifact_types this consumed
        "updated_at": _now(),
        "body": body,  # OPAQUE to the engine
    }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# A Step is a pure function of (inputs, feedback) -> produced artifacts.
# The pipeline is just a list of these. Phase 1+ swaps each `run` from a stub
# to a real agent; nothing else in this file changes.
# --------------------------------------------------------------------------
@dataclass
class Step:
    name: str  # e.g. "structure"
    consumes: list[str]  # artifact_types it reads
    produces: list[str]  # artifact_types it writes
    run: Callable[[dict, str | None], dict]
    # run(inputs, feedback) -> {artifact_type: artifact_envelope}
    # inputs is {artifact_type: artifact_envelope}


@dataclass
class Decision:
    approved: bool
    feedback: str | None = None


class PipelineCancelled(RuntimeError):
    """Raised when an operator intentionally stops a pipeline at a checkpoint."""

    def __init__(self, step_name: str) -> None:
        super().__init__(f"pipeline cancelled at checkpoint '{step_name}'")
        self.step_name = step_name


# --------------------------------------------------------------------------
# Storage: plain JSON files, one folder per course. No database (Phase 6+).
# --------------------------------------------------------------------------
def course_dir(course_id: str) -> Path:
    return COURSES_DIR / course_id


def artifact_path(course_id: str, artifact_type: str) -> Path:
    return course_dir(course_id) / f"{artifact_type}.json"


def save_artifact(artifact: dict) -> Path:
    path = artifact_path(artifact["course_id"], artifact["artifact_type"])
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact["updated_at"] = _now()
    path.write_text(json.dumps(artifact, indent=2))
    return path


def save_seed_artifact(artifact: dict) -> Path | None:
    """Save a seed artifact only when its meaningful content changed."""
    existing = load_artifact(artifact["course_id"], artifact["artifact_type"])
    if (
        existing is not None
        and existing.get("status") == "approved"
        and existing.get("body") == artifact.get("body")
        and existing.get("inputs") == artifact.get("inputs")
        and existing.get("schema_version") == artifact.get("schema_version")
    ):
        return None
    artifact["status"] = "approved"
    return save_artifact(artifact)


def load_artifact(course_id: str, artifact_type: str) -> dict | None:
    path = artifact_path(course_id, artifact_type)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _approved_outputs_current(existing: list[dict | None], inputs: dict[str, dict]) -> bool:
    """Return True when approved outputs are current for the loaded inputs."""
    if not existing or not all(existing):
        return False
    if not all(artifact["status"] == "approved" for artifact in existing if artifact):
        return False
    latest_input_update = max(
        (artifact.get("updated_at", "") for artifact in inputs.values()),
        default="",
    )
    return all(
        artifact
        and artifact.get("updated_at")
        and artifact.get("updated_at", "") >= latest_input_update
        for artifact in existing
    )


# --------------------------------------------------------------------------
# The default human-in-the-loop: a console prompt. This is injectable so an
# eval harness (or Phase 6's nicer UI) can drive the pipeline without changing
# the engine - pass your own `approver` to run_pipeline().
# --------------------------------------------------------------------------
def console_approver(step_name: str, produced: dict) -> Decision:
    print(f"\n=== Step '{step_name}' produced: {', '.join(produced)} ===")
    for atype, art in produced.items():
        print(f"\n--- {atype}  (revision {art['revision']}) ---")
        summary = artifact_summary(art)
        if summary:
            print(f"Summary: {summary}")
        print(json.dumps(art["body"], indent=2))
    while True:
        choice = input(
            f"\n[{step_name}] approve / changes / quit [a/c/q] > "
        ).strip().lower()
        if choice in ("a", "approve"):
            return Decision(approved=True)
        if choice in ("c", "changes"):
            fb = input("  what should change? > ").strip()
            if not fb:
                print("  change feedback cannot be empty")
                continue
            return Decision(approved=False, feedback=fb)
        if choice in ("q", "quit"):
            raise PipelineCancelled(step_name)
        print("  please type approve, changes, or quit")


def artifact_summary(artifact: dict) -> str:
    """Return a compact generic summary for terminal checkpoint review."""
    body = artifact.get("body")
    if not isinstance(body, dict):
        return ""
    parts: list[str] = []
    for key in sorted(body):
        value = body[key]
        if isinstance(value, list):
            parts.append(f"{key}: {len(value)} item(s)")
        elif isinstance(value, dict):
            parts.append(f"{key}: {len(value)} field(s)")
        elif value is None:
            parts.append(f"{key}: null")
        else:
            label = str(value).replace("\n", " ")
            parts.append(f"{key}: {label[:80]}")
        if len(parts) >= 8:
            break
    return "; ".join(parts)


# --------------------------------------------------------------------------
# The runner. This is the whole skeleton.
# --------------------------------------------------------------------------
def run_pipeline(
    course_id: str,
    pipeline: list[Step],
    seed_artifacts: dict,
    approver: Callable[[str, dict], Decision] = console_approver,
) -> None:
    """Run the steps in order, pausing for approval after each.

    seed_artifacts: artifacts the human supplies up front (e.g. the brief).
                    Saved pre-approved so Step 1 can consume them.
    """
    for art in seed_artifacts.values():
        save_seed_artifact(art)

    for step in pipeline:
        # --- gather inputs this step consumes
        inputs = {}
        for t in step.consumes:
            art = load_artifact(course_id, t)
            if art is None:
                raise RuntimeError(f"step '{step.name}' needs '{t}', but it is not on disk")
            inputs[t] = art

        # --- resume: skip a step whose outputs are already approved on disk.
        # (Saves re-approving Steps 1-2 every time you tweak Step 3. To force a
        # redo of an approved step, delete its .json files and re-run. If an
        # input was revised after an output was approved, the step is no longer
        # considered current and will rerun.)
        existing = [load_artifact(course_id, t) for t in step.produces]
        if _approved_outputs_current(existing, inputs) and all(
            a and set(a.get("inputs", [])) == set(step.consumes) for a in existing
        ):
            print(f"[skip]  '{step.name}' already approved - resuming past it")
            continue

        # --- run / approve loop: re-runs ONLY this step until approved
        feedback: str | None = None
        revision = 0
        while True:
            produced = step.run(inputs, feedback)

            # orchestrator owns the lifecycle fields, not the step
            for art in produced.values():
                art["revision"] = revision
                art["revision_note"] = feedback
                art["status"] = "draft"
                save_artifact(art)

            decision = approver(step.name, produced)
            if decision.approved:
                for art in produced.values():
                    art["status"] = "approved"
                    save_artifact(art)
                print(f"[ok]    '{step.name}' approved")
                break

            feedback = decision.feedback
            revision += 1
            print(f"[redo]  re-running ONLY '{step.name}' (revision {revision})")

    print(f"\nDone. Course folder: {course_dir(course_id)}/")
