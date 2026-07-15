from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

import acceptance
from api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_and_wait(client: TestClient, course_id: str, stage: str) -> None:
    projected = client.get(f"/api/courses/{course_id}/stages/{stage}").json()
    response = client.post(
        f"/api/courses/{course_id}/stages/{stage}/run",
        json={
            "mode": "deterministic",
            "expected_checksum": projected.get("checksum"),
        },
    )
    assert response.status_code == 202, response.text
    job_url = response.json()["job_url"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(job_url).json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    assert job["status"] == "completed", job


def _approve(client: TestClient, course_id: str, stage: str) -> None:
    projected = client.get(f"/api/courses/{course_id}/stages/{stage}").json()
    response = client.post(
        f"/api/courses/{course_id}/stages/{stage}/approve",
        json={"expected_checksum": projected.get("checksum")},
    )
    assert response.status_code == 200, response.text


def test_full_deterministic_studio_workflow_reaches_a_rendered_package(
    tmp_path: Path, monkeypatch
) -> None:
    # The prototype's SourceStore is relative to cwd; isolating cwd keeps this
    # browser/API acceptance path completely out of the developer's runtime data.
    monkeypatch.chdir(tmp_path)
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/courses",
            json={
                "subject": "Coffee making",
                "description": "A compact practical course.",
                "course_id": "studio-smoke",
            },
        )
        assert created.status_code == 201

        for stage in ("brief", "outcomes"):
            _run_and_wait(client, "studio-smoke", stage)
            _approve(client, "studio-smoke", stage)

        _run_and_wait(client, "studio-smoke", "research")
        research_stage = client.get(
            "/api/courses/studio-smoke/stages/research"
        ).json()
        dossier = next(
            artifact
            for artifact in research_stage["artifacts"]
            if artifact["artifact_type"] == "research_dossier"
        )
        selected_ids = [
            candidate["id"]
            for candidate in dossier["body"]["source_candidates"]
            if candidate["status"] in {"proposed", "approved"}
        ][:2]
        decision = client.put(
            "/api/courses/studio-smoke/research/sources/decision",
            json={
                "selected_ids": selected_ids,
                "expected_checksum": research_stage["checksum"],
            },
        )
        assert decision.status_code == 200, decision.text
        _approve(client, "studio-smoke", "research")

        for stage in ("course-model", "blueprint"):
            _run_and_wait(client, "studio-smoke", stage)
            _approve(client, "studio-smoke", stage)

        _run_and_wait(client, "studio-smoke", "content")

        review = client.get("/api/courses/studio-smoke/content/reviews").json()
        for record in review["artifact"]["body"]["assets"]:
            response = client.put(
                f"/api/courses/studio-smoke/content/reviews/{record['asset_id']}",
                json={
                    "decision": "approved",
                    "expected_checksum": review["checksum"],
                },
            )
            assert response.status_code == 200, response.text
            review = response.json()

        _approve(client, "studio-smoke", "content")

        for stage in ("lesson-plan", "package"):
            _run_and_wait(client, "studio-smoke", stage)
            _approve(client, "studio-smoke", stage)

        workspace = client.get("/api/courses/studio-smoke/workspace").json()
        assert workspace["operator_status"] == "complete"
        assert workspace["current_stage"] == "package"
        assert workspace["attention"]["blocking_total"] == 0
        assert set(workspace["artifact_types"]) == (
            acceptance.NEXT_CYCLE_EXPECTED_WORKSPACE_ARTIFACTS
        )
        assert (tmp_path / "rendered" / "studio-smoke" / "README.md").is_file()
