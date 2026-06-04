"""
Course Builder - Phase 0 orchestrator (the walking skeleton).

This is the ENGINE. It knows nothing about what a Domain Model or a TOC
actually contains. It treats every artifact as an opaque JSON *body* wrapped in
a small, fixed metadata *envelope*. Its only jobs are:

  1. run the steps in order,
  2. feed each step the artifacts it consumes,
  3. save what each step produces into a per-course folder,
  4. pause after each step for human approve / request-changes,
  5. on "request-changes", re-run ONLY that step with the feedback.

Because it depends only on the envelope (never the body), the real schema work
you do next will not require changing a single line of this file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

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
) -> dict:
    """Wrap a step's output body in the fixed metadata envelope.

    The lifecycle fields (status, revision, revision_note, updated_at) are
    owned by the orchestrator, not the step - they are set/overwritten when
    the artifact is saved. A step just declares identity + body + what it read.
    """
    return {
        "course_id": course_id,
        "artifact_type": artifact_type,
        "produced_by_step": produced_by_step,
        "schema_version": SCHEMA_VERSION,
        "status": "draft",          # draft -> approved (set by orchestrator)
        "revision": 0,              # bumped by orchestrator on re-run
        "revision_note": None,      # the feedback that triggered the re-run
        "inputs": inputs,           # which artifact_types this consumed
        "updated_at": _now(),
        "body": body,               # OPAQUE to the engine
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# A Step is a pure function of (inputs, feedback) -> produced artifacts.
# The pipeline is just a list of these. Phase 1+ swaps each `run` from a stub
# to a real agent; nothing else in this file changes.
# --------------------------------------------------------------------------
@dataclass
class Step:
    name: str                                  # e.g. "structure"
    consumes: list[str]                         # artifact_types it reads
    produces: list[str]                         # artifact_types it writes
    run: Callable[[dict, Optional[str]], dict]
    # run(inputs, feedback) -> {artifact_type: artifact_envelope}
    # inputs is {artifact_type: artifact_envelope}


@dataclass
class Decision:
    approved: bool
    feedback: Optional[str] = None


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


def load_artifact(course_id: str, artifact_type: str) -> Optional[dict]:
    path = artifact_path(course_id, artifact_type)
    if not path.exists():
        return None
    return json.loads(path.read_text())


# --------------------------------------------------------------------------
# The default human-in-the-loop: a console prompt. This is injectable so an
# eval harness (or Phase 6's nicer UI) can drive the pipeline without changing
# the engine - pass your own `approver` to run_pipeline().
# --------------------------------------------------------------------------
def console_approver(step_name: str, produced: dict) -> Decision:
    print(f"\n=== Step '{step_name}' produced: {', '.join(produced)} ===")
    for atype, art in produced.items():
        print(f"\n--- {atype}  (revision {art['revision']}) ---")
        print(json.dumps(art["body"], indent=2))
    while True:
        choice = input(f"\n[{step_name}] (a)pprove / (c)hanges / (q)uit > ").strip().lower()
        if choice in ("a", "approve"):
            return Decision(approved=True)
        if choice in ("c", "changes"):
            fb = input("  what should change? > ").strip()
            return Decision(approved=False, feedback=fb)
        if choice in ("q", "quit"):
            raise KeyboardInterrupt
        print("  please type: a, c, or q")


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
        art["status"] = "approved"
        save_artifact(art)

    for step in pipeline:
        # --- resume: skip a step whose outputs are already approved on disk.
        # (Saves re-approving Steps 1-2 every time you tweak Step 3. To force a
        # redo of an approved step, delete its .json files and re-run.)
        existing = [load_artifact(course_id, t) for t in step.produces]
        if existing and all(a and a["status"] == "approved" for a in existing):
            print(f"[skip]  '{step.name}' already approved - resuming past it")
            continue

        # --- gather inputs this step consumes
        inputs = {}
        for t in step.consumes:
            art = load_artifact(course_id, t)
            if art is None:
                raise RuntimeError(
                    f"step '{step.name}' needs '{t}', but it is not on disk"
                )
            inputs[t] = art

        # --- run / approve loop: re-runs ONLY this step until approved
        feedback: Optional[str] = None
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
