from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import create_app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    with TestClient(app) as value:
        yield value


def test_run_stage_returns_nested_durable_job_contract(client: TestClient) -> None:
    created = client.post(
        "/api/courses",
        json={"subject": "Indoor gardening", "course_id": "indoor-gardening"},
    )
    assert created.status_code == 201

    brief = client.get("/api/courses/indoor-gardening/artifacts/brief").json()
    completed = client.patch(
        "/api/courses/indoor-gardening/brief",
        json={
            "expected_checksum": brief["checksum"],
            "updates": {
                "audience": "Apartment gardeners",
                "purpose": "Grow herbs indoors",
                "prior_knowledge": "None",
                "level": "beginner",
                "duration": "3 hours",
                "modality": "self_paced",
                "language": "English",
            },
        },
    )
    assert completed.status_code == 200
    brief_stage = client.get("/api/courses/indoor-gardening/stages/brief").json()
    approved = client.post(
        "/api/courses/indoor-gardening/stages/brief/approve",
        json={"expected_checksum": brief_stage["checksum"]},
    )
    assert approved.status_code == 200

    response = client.post(
        "/api/courses/indoor-gardening/stages/outcomes/run",
        json={"mode": "deterministic"},
    )

    assert response.status_code == 202
    accepted = response.json()
    assert set(accepted) == {"job", "job_url", "events_url"}
    assert accepted["job"]["status"] == "queued"
    assert accepted["job_url"].endswith(accepted["job"]["job_id"])
    assert accepted["events_url"].endswith("/events")

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = client.get(accepted["job_url"]).json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    assert job["status"] == "completed"
    snapshot = client.get(f"{accepted['events_url']}/snapshot").json()["events"]
    assert snapshot[0]["event_type"] == "job.queued"
    assert snapshot[-1]["event_type"] == "job.completed"
    assert any(event["event_type"] == "checkpoint.awaiting_review" for event in snapshot)


def test_command_models_reject_unknown_fields(client: TestClient) -> None:
    response = client.post(
        "/api/courses",
        json={
            "subject": "Indoor gardening",
            "course_id": "indoor-gardening",
            "silently_ignored": True,
        },
    )

    assert response.status_code == 422
