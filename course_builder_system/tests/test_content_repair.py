from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import content_review
from api.main import create_app
from api.services.artifact_repository import ArtifactRepository, VersionConflict

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
TARGET_ASSET = "m1_s1_cc"
TARGET_CLAIM = "m1_s1_cc_c1"


def _seed_course(repository: ArtifactRepository, course_id: str) -> None:
    for path in FIXTURE_ROOT.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        artifact["status"] = "approved"
        if artifact["artifact_type"] == "content_package":
            asset = next(
                asset
                for subtopic in artifact["body"]["subtopics"]
                for asset in subtopic["assets"]
                if asset["id"] == TARGET_ASSET
            )
            asset["claims"][0]["support"] = "unsupported"
            asset["claims"][0]["note"] = (
                "The assigned source is too general to support this exact claim."
            )
            asset["verification"]["supported"] -= 1
            asset["verification"]["unsupported"] += 1
        repository.save(artifact)
    package = repository.require(course_id, "content_package")
    review = content_review.build_content_review_artifact(package)
    for record in review["body"]["assets"]:
        record["decision"] = "approved"
        record["reviewed_at"] = "2026-07-20T00:00:00+00:00"
    review["body"]["summary"] = content_review.review_summary(review["body"])
    review["status"] = "approved"
    repository.save(review)


def _repository(tmp_path: Path) -> ArtifactRepository:
    return ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )


def _app(tmp_path: Path, course_id: str = "content-repair"):
    repository = _repository(tmp_path)
    _seed_course(repository, course_id)
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    return repository, app


def _wait(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Content repair job did not finish")


def _asset_checksums(repository: ArtifactRepository, course_id: str) -> dict[str, str]:
    package = repository.require(course_id, "content_package")
    return {
        asset["id"]: repository.checksum(asset)
        for subtopic in package["body"]["subtopics"]
        for asset in subtopic["assets"]
    }


def _route_better_evidence(client: TestClient, course_id: str) -> tuple[str, str]:
    content = client.get(f"/api/courses/{course_id}/artifacts/content_package").json()
    requested = client.post(
        f"/api/courses/{course_id}/source-repairs",
        json={
            "expected_content_checksum": content["checksum"],
            "subtopic_id": "m1_s1",
            "asset_id": TARGET_ASSET,
            "claim_id": TARGET_CLAIM,
            "finding_id": TARGET_CLAIM,
            "evidence_gap": "Find exact support for the current attributed claim.",
            "mode": "deterministic",
        },
    )
    assert requested.status_code == 202, requested.text
    assert _wait(client, requested.json()["job"]["job_id"])["status"] == "completed"
    ledger = client.get(f"/api/courses/{course_id}/source-repairs").json()
    entry = ledger["entries"][0]
    decided = client.put(
        f"/api/courses/{course_id}/source-repairs/{entry['id']}/decision",
        json={
            "expected_checksum": ledger["checksum"],
            "candidate_id": entry["proposed_candidates"][0]["id"],
            "decision": "approved",
            "rationale": "The bounded preview covers the exact gap.",
        },
    )
    assert decided.status_code == 200, decided.text
    routed = client.put(
        f"/api/courses/{course_id}/source-repairs/{entry['id']}/route",
        json={
            "expected_checksum": decided.json()["checksum"],
            "subtopic_ids": ["m1_s1"],
            "asset_ids": [TARGET_ASSET],
        },
    )
    assert routed.status_code == 200, routed.text
    return entry["id"], routed.json()["checksum"]


def test_content_repair_projection_classifies_findings_advisorially(
    tmp_path: Path,
) -> None:
    _repository_value, app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/courses/content-repair/content/repairs")

    assert response.status_code == 200
    body = response.json()
    finding = next(item for item in body["findings"] if item["claim_id"] == TARGET_CLAIM)
    assert finding["classification"] == "insufficient_evidence"
    assert finding["recommended_strategy"] == "better_evidence"
    assert finding["blocking"] is True
    assert finding["state"] == "ready"
    assert body["groups"]["insufficient_evidence"] == 1
    assert body["hard_blocker_total"] == 1
    assert body["ready_for_package"] is False


def test_content_repair_projection_treats_source_less_and_unattributed_as_hard(
    tmp_path: Path,
) -> None:
    repository, app = _app(tmp_path, "blocker-truth")
    package = repository.require("blocker-truth", "content_package")
    target = next(
        asset
        for subtopic in package["body"]["subtopics"]
        for asset in subtopic["assets"]
        if asset["id"] != TARGET_ASSET and asset.get("claims")
    )
    claim = target["claims"][0]
    claim["source_id"] = None
    claim["support"] = "supported"
    claim["note"] = "The statement has no approved source attribution."
    target["verification"]["supported"] -= 1
    target["verification"]["ungrounded"] += 1
    target["verification"]["unattributed_found"].append(
        "A second factual statement is not attributed."
    )
    repository.save(
        package,
        expected_checksum=repository.checksum(
            repository.require("blocker-truth", "content_package")
        ),
    )

    projection = app.state.content_repairs.project("blocker-truth")
    target_findings = [
        finding for finding in projection["findings"] if finding["asset_id"] == target["id"]
    ]

    assert projection["hard_blocker_total"] == 3
    assert len(target_findings) == 2
    assert all(finding["blocking"] is True for finding in target_findings)
    assert {finding["classification"] for finding in target_findings} == {
        "missing_attribution"
    }
    assert {finding["finding_id"] for finding in target_findings} == {
        claim["id"],
        "unattributed_1",
    }

    current = repository.require("blocker-truth", "content_package")
    current_checksum = repository.checksum(current)
    prepared = app.state.content_repairs.prepare(
        "blocker-truth",
        expected_content_checksum=current_checksum,
        strategy="existing_evidence",
        targets=[
            {
                "asset_id": target["id"],
                "claim_ids": [claim["id"]],
                "finding_ids": [claim["id"]],
            }
        ],
        source_repair_id=None,
        expected_source_repair_checksum=None,
        mode="deterministic",
    )
    assert prepared.asset_ids == (target["id"],)
    target_subtopic_id = next(
        subtopic["subtopic_id"]
        for subtopic in current["body"]["subtopics"]
        if any(asset["id"] == target["id"] for asset in subtopic["assets"])
    )
    requested = app.state.source_repairs.request(
        "blocker-truth",
        expected_content_checksum=current_checksum,
        subtopic_id=target_subtopic_id,
        asset_id=target["id"],
        claim_id=claim["id"],
        finding_id=claim["id"],
        evidence_gap="Find an approved source for this source-less claim.",
        mode="deterministic",
    )
    assert requested["repair_id"] == "repair_1"


def test_existing_evidence_repair_changes_only_target_and_resets_only_its_review(
    tmp_path: Path,
) -> None:
    repository, app = _app(tmp_path)
    before_assets = _asset_checksums(repository, "content-repair")
    lesson_before = deepcopy(repository.require("content-repair", "lesson_plan"))
    before_review = repository.require("content-repair", "content_review")
    prior_review = {
        item["asset_id"]: (item["decision"], item["asset_fingerprint"])
        for item in before_review["body"]["assets"]
    }

    with TestClient(app) as client:
        content = client.get("/api/courses/content-repair/artifacts/content_package").json()
        response = client.post(
            "/api/courses/content-repair/content/repairs",
            json={
                "expected_content_checksum": content["checksum"],
                "strategy": "existing_evidence",
                "targets": [
                    {
                        "asset_id": TARGET_ASSET,
                        "claim_ids": [TARGET_CLAIM],
                        "finding_ids": [TARGET_CLAIM],
                    }
                ],
                "mode": "deterministic",
            },
        )
        assert response.status_code == 202, response.text
        job = _wait(client, response.json()["job"]["job_id"])
        assert job["status"] == "completed", job
        assert job["result"]["changed_asset_ids"] == [TARGET_ASSET]
        assert job["result"]["hard_blocker_total"] == 0
        unit_events = [
            event
            for event in app.state.jobs.events(job["job_id"])
            if event["event_type"].startswith("unit.")
        ]
        assert any(event["event_type"] == "unit.started" for event in unit_events)
        assert any(event["event_type"] == "unit.completed" for event in unit_events)
        assert any(event.get("asset_id") == TARGET_ASSET for event in unit_events)

        projection = client.get("/api/courses/content-repair/content/repairs").json()
        workspace = client.get("/api/courses/content-repair/workspace").json()

    after_assets = _asset_checksums(repository, "content-repair")
    assert after_assets[TARGET_ASSET] != before_assets[TARGET_ASSET]
    for asset_id in set(before_assets) - {TARGET_ASSET}:
        assert after_assets[asset_id] == before_assets[asset_id]
    review = repository.require("content-repair", "content_review")
    reviews = {item["asset_id"]: item for item in review["body"]["assets"]}
    assert reviews[TARGET_ASSET]["decision"] == "pending"
    for asset_id in set(reviews) - {TARGET_ASSET}:
        assert (
            reviews[asset_id]["decision"],
            reviews[asset_id]["asset_fingerprint"],
        ) == prior_review[asset_id]
    assert projection["hard_blocker_total"] == 0
    assert projection["ready_for_package"] is False
    assert (
        next(stage for stage in workspace["stages"] if stage["slug"] == "content")["state"]
        == "awaiting_review"
    )
    assert repository.require("content-repair", "lesson_plan") == lesson_before
    assert repository.require("content-repair", "render_manifest")["status"] == "stale"
    assert repository.require("content-repair", "run_summary")["status"] == "stale"


def test_better_evidence_repair_advances_source_ledger_and_resolves_after_review(
    tmp_path: Path,
) -> None:
    repository, app = _app(tmp_path, "better-repair")
    before_assets = _asset_checksums(repository, "better-repair")

    with TestClient(app) as client:
        repair_id, ledger_checksum = _route_better_evidence(client, "better-repair")
        content = client.get("/api/courses/better-repair/artifacts/content_package").json()
        response = client.post(
            "/api/courses/better-repair/content/repairs",
            json={
                "expected_content_checksum": content["checksum"],
                "strategy": "better_evidence",
                "targets": [
                    {
                        "asset_id": TARGET_ASSET,
                        "claim_ids": [TARGET_CLAIM],
                        "finding_ids": [TARGET_CLAIM],
                    }
                ],
                "source_repair_id": repair_id,
                "expected_source_repair_checksum": ledger_checksum,
                "mode": "deterministic",
            },
        )
        assert response.status_code == 202, response.text
        job = _wait(client, response.json()["job"]["job_id"])
        assert job["status"] == "completed", job
        ledger = client.get("/api/courses/better-repair/source-repairs").json()
        entry = ledger["entries"][0]
        assert entry["status"] == "awaiting_content_review"
        assert entry["final_verifier_result"]["hard_blocker_total"] == 0
        assert entry["final_verifier_result"]["review_status"] == "pending"
        assert entry["final_verifier_result"]["content_body_checksum"] == (
            repository.checksum(repository.require("better-repair", "content_package")["body"])
        )

        review = client.get("/api/courses/better-repair/content/reviews").json()
        decided = client.put(
            f"/api/courses/better-repair/content/reviews/{TARGET_ASSET}",
            json={
                "expected_checksum": review["checksum"],
                "decision": "approved",
            },
        )
        assert decided.status_code == 200, decided.text
        resolved = client.get("/api/courses/better-repair/source-repairs").json()

    assert resolved["entries"][0]["status"] == "resolved"
    assert resolved["entries"][0]["final_verifier_result"]["review_status"] == "approved"
    after_assets = _asset_checksums(repository, "better-repair")
    assert after_assets[TARGET_ASSET] != before_assets[TARGET_ASSET]
    for asset_id in set(before_assets) - {TARGET_ASSET}:
        assert after_assets[asset_id] == before_assets[asset_id]


def test_content_repair_rejects_stale_and_strategy_ambiguous_commands_before_job(
    tmp_path: Path,
) -> None:
    repository, app = _app(tmp_path)
    content = repository.require("content-repair", "content_package")
    job_root = tmp_path / "runtime" / "content-repair" / "jobs"
    with TestClient(app) as client:
        missing_source = client.post(
            "/api/courses/content-repair/content/repairs",
            json={
                "expected_content_checksum": repository.checksum(content),
                "strategy": "better_evidence",
                "targets": [{"asset_id": TARGET_ASSET}],
                "mode": "deterministic",
            },
        )
        stale = client.post(
            "/api/courses/content-repair/content/repairs",
            json={
                "expected_content_checksum": "stale-checksum",
                "strategy": "existing_evidence",
                "targets": [{"asset_id": TARGET_ASSET}],
                "mode": "deterministic",
            },
        )
        duplicates = client.post(
            "/api/courses/content-repair/content/repairs",
            json={
                "expected_content_checksum": repository.checksum(content),
                "strategy": "existing_evidence",
                "targets": [
                    {"asset_id": TARGET_ASSET},
                    {"asset_id": TARGET_ASSET},
                ],
                "mode": "deterministic",
            },
        )
        unknown_finding = client.post(
            "/api/courses/content-repair/content/repairs",
            json={
                "expected_content_checksum": repository.checksum(content),
                "strategy": "existing_evidence",
                "targets": [
                    {
                        "asset_id": TARGET_ASSET,
                        "claim_ids": ["missing_claim"],
                    }
                ],
                "mode": "deterministic",
            },
        )
        stale_artifact = deepcopy(content)
        stale_artifact["status"] = "stale"
        stale_artifact = repository.save(
            stale_artifact,
            expected_checksum=repository.checksum(content),
        )
        stale_state = client.post(
            "/api/courses/content-repair/content/repairs",
            json={
                "expected_content_checksum": repository.checksum(stale_artifact),
                "strategy": "existing_evidence",
                "targets": [{"asset_id": TARGET_ASSET}],
                "mode": "deterministic",
            },
        )

    assert missing_source.status_code == 422
    assert stale.status_code == 409
    assert duplicates.status_code == 422
    assert unknown_finding.status_code == 400
    assert stale_state.status_code == 409
    assert list(job_root.glob("*.json")) == []


def test_better_evidence_generation_failure_preserves_content_and_is_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, app = _app(tmp_path, "retry-repair")
    with TestClient(app) as client:
        repair_id, ledger_checksum = _route_better_evidence(client, "retry-repair")
        content = repository.require("retry-repair", "content_package")
        protected = {
            artifact_type: deepcopy(repository.require("retry-repair", artifact_type))
            for artifact_type in (
                "content_package",
                "content_progress",
                "content_review",
                "lesson_plan",
                "render_manifest",
                "run_summary",
            )
        }
        step = app.state.catalog.steps_for_stage("content", mode="deterministic")[0]

        def fail_generation(_inputs: object, _feedback: object) -> dict:
            raise RuntimeError("token=super-secret-value generation failed")

        monkeypatch.setattr(step, "run", fail_generation)
        monkeypatch.setattr(
            app.state.catalog,
            "steps_for_stage",
            lambda _slug, mode, progress_callback=None: [step],
        )
        with pytest.raises(RuntimeError, match="super-secret-value"):
            app.state.content_repairs.execute(
                "retry-repair",
                expected_content_checksum=repository.checksum(content),
                strategy="better_evidence",
                targets=[
                    {
                        "asset_id": TARGET_ASSET,
                        "claim_ids": [TARGET_CLAIM],
                        "finding_ids": [TARGET_CLAIM],
                    }
                ],
                source_repair_id=repair_id,
                expected_source_repair_checksum=ledger_checksum,
                mode="deterministic",
            )

    for artifact_type, before in protected.items():
        assert repository.require("retry-repair", artifact_type) == before
    entry = repository.require("retry-repair", "source_repair")["body"]["entries"][0]
    assert entry["status"] == "awaiting_content_repair"
    assert "[redacted]" in entry["failure_reason"]
    assert "super-secret-value" not in entry["failure_reason"]


def test_failed_content_repair_job_keeps_typed_retry_available_through_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "http-repair-retry"
    repository, app = _app(tmp_path, course_id)
    with TestClient(app) as client:
        repair_id, _ledger_checksum = _route_better_evidence(client, course_id)
        step = app.state.catalog.steps_for_stage("content", mode="deterministic")[0]
        original_run = step.run

        def fail_generation(_inputs: object, _feedback: object) -> dict:
            raise RuntimeError("api_key=secret-repair-key targeted generation failed")

        monkeypatch.setattr(step, "run", fail_generation)
        monkeypatch.setattr(
            app.state.catalog,
            "steps_for_stage",
            lambda _slug, mode, progress_callback=None: [step],
        )
        content = client.get(f"/api/courses/{course_id}/artifacts/content_package").json()
        ledger = client.get(f"/api/courses/{course_id}/source-repairs").json()
        command = {
            "expected_content_checksum": content["checksum"],
            "strategy": "better_evidence",
            "targets": [
                {
                    "asset_id": TARGET_ASSET,
                    "claim_ids": [TARGET_CLAIM],
                    "finding_ids": [TARGET_CLAIM],
                }
            ],
            "source_repair_id": repair_id,
            "expected_source_repair_checksum": ledger["checksum"],
            "mode": "deterministic",
        }
        requested = client.post(
            f"/api/courses/{course_id}/content/repairs",
            json=command,
        )
        assert requested.status_code == 202, requested.text
        failed = _wait(client, requested.json()["job"]["job_id"])
        assert failed["status"] == "failed"
        assert failed["operation"] == "content_repair"
        assert failed["context"] == {
            "strategy": "better_evidence",
            "source_repair_id": repair_id,
        }
        assert "secret-repair-key" not in failed["error"]["message"]

        workspace = client.get(f"/api/courses/{course_id}/workspace").json()
        content_stage = next(
            stage for stage in workspace["stages"] if stage["slug"] == "content"
        )
        assert content_stage["state"] == "requires_attention"
        assert content_stage["last_failure"] == failed["error"]
        assert "content_repair" in {action["id"] for action in content_stage["actions"]}
        assert "retry" not in {action["id"] for action in content_stage["actions"]}
        retryable_ledger = client.get(f"/api/courses/{course_id}/source-repairs").json()
        assert retryable_ledger["entries"][0]["status"] == "awaiting_content_repair"

        monkeypatch.setattr(step, "run", original_run)
        command["expected_source_repair_checksum"] = retryable_ledger["checksum"]
        retried = client.post(
            f"/api/courses/{course_id}/content/repairs",
            json=command,
        )
        assert retried.status_code == 202, retried.text
        assert _wait(client, retried.json()["job"]["job_id"])["status"] == "completed"
        completed_ledger = client.get(f"/api/courses/{course_id}/source-repairs").json()
        assert completed_ledger["entries"][0]["status"] == "awaiting_content_review"

    assert repository.require(course_id, "content_package")["status"] == "draft"


def test_interrupted_content_repair_recovers_source_entry_and_typed_retry(
    tmp_path: Path,
) -> None:
    course_id = "interrupted-repair"
    runtime_root = tmp_path / "runtime"
    repository, app = _app(tmp_path, course_id)
    with TestClient(app) as client:
        repair_id, ledger_checksum = _route_better_evidence(client, course_id)
        package = repository.require(course_id, "content_package")
        app.state.source_repairs.begin_content_repair(
            course_id,
            repair_id,
            expected_checksum=ledger_checksum,
            expected_content_checksum=repository.checksum(package),
            asset_ids=[TARGET_ASSET],
        )

    interrupted_id = "interruptedcontentrepair"
    jobs_dir = runtime_root / course_id / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    (jobs_dir / f"{interrupted_id}.json").write_text(
        json.dumps(
            {
                "job_id": interrupted_id,
                "course_id": course_id,
                "stage": "content",
                "operation": "content_repair",
                "context": {
                    "strategy": "better_evidence",
                    "source_repair_id": repair_id,
                },
                "status": "running",
                "created_at": "2026-07-20T00:00:00.000+00:00",
                "started_at": "2026-07-20T00:00:01.000+00:00",
                "completed_at": None,
                "result": None,
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    restarted = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=runtime_root,
        include_examples=False,
    )
    with TestClient(restarted) as client:
        recovered_job = client.get(f"/api/jobs/{interrupted_id}").json()
        assert recovered_job["status"] == "failed"
        assert recovered_job["error"]["type"] == "InterruptedJob"
        ledger = client.get(f"/api/courses/{course_id}/source-repairs").json()
        assert ledger["entries"][0]["status"] == "awaiting_content_repair"
        assert "rerun is safe" in ledger["entries"][0]["failure_reason"]
        workspace = client.get(f"/api/courses/{course_id}/workspace").json()
        content_stage = next(
            stage for stage in workspace["stages"] if stage["slug"] == "content"
        )
        assert content_stage["state"] == "requires_attention"
        assert "content_repair" in {action["id"] for action in content_stage["actions"]}

        package = client.get(f"/api/courses/{course_id}/artifacts/content_package").json()
        retried = client.post(
            f"/api/courses/{course_id}/content/repairs",
            json={
                "expected_content_checksum": package["checksum"],
                "strategy": "better_evidence",
                "targets": [
                    {
                        "asset_id": TARGET_ASSET,
                        "claim_ids": [TARGET_CLAIM],
                        "finding_ids": [TARGET_CLAIM],
                    }
                ],
                "source_repair_id": repair_id,
                "expected_source_repair_checksum": ledger["checksum"],
                "mode": "deterministic",
            },
        )
        assert retried.status_code == 202, retried.text
        assert _wait(client, retried.json()["job"]["job_id"])["status"] == "completed"


def test_scope_escaping_generation_is_rejected_without_any_canonical_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, app = _app(tmp_path, "scope-escape")
    protected_types = (
        "content_package",
        "content_progress",
        "content_review",
        "lesson_plan",
        "render_manifest",
        "run_summary",
    )
    protected = {
        artifact_type: deepcopy(repository.require("scope-escape", artifact_type))
        for artifact_type in protected_types
    }
    step = app.state.catalog.steps_for_stage("content", mode="deterministic")[0]
    original_run = step.run

    def escape_scope(inputs: dict, feedback: str) -> dict:
        produced = original_run(inputs, feedback)
        unrelated = next(
            asset
            for subtopic in produced["content_package"]["body"]["subtopics"]
            for asset in subtopic["assets"]
            if asset["id"] != TARGET_ASSET
        )
        unrelated["title"] = unrelated["title"] + " (escaped scope)"
        return produced

    monkeypatch.setattr(step, "run", escape_scope)
    monkeypatch.setattr(
        app.state.catalog,
        "steps_for_stage",
        lambda _slug, mode, progress_callback=None: [step],
    )

    with pytest.raises(ValueError, match="out-of-scope assets"):
        app.state.content_repairs.execute(
            "scope-escape",
            expected_content_checksum=repository.checksum(
                repository.require("scope-escape", "content_package")
            ),
            strategy="existing_evidence",
            targets=[
                {
                    "asset_id": TARGET_ASSET,
                    "claim_ids": [TARGET_CLAIM],
                    "finding_ids": [TARGET_CLAIM],
                }
            ],
            source_repair_id=None,
            expected_source_repair_checksum=None,
            mode="deterministic",
        )

    for artifact_type, before in protected.items():
        assert repository.require("scope-escape", artifact_type) == before


def test_content_repair_prepare_rejects_changed_content_checksum(tmp_path: Path) -> None:
    repository, app = _app(tmp_path)
    service = app.state.content_repairs
    package = repository.require("content-repair", "content_package")
    with pytest.raises(VersionConflict):
        service.prepare(
            "content-repair",
            expected_content_checksum="changed-checksum",
            strategy="existing_evidence",
            targets=[
                {
                    "asset_id": TARGET_ASSET,
                    "claim_ids": [TARGET_CLAIM],
                    "finding_ids": [TARGET_CLAIM],
                }
            ],
            source_repair_id=None,
            expected_source_repair_checksum=None,
            mode="deterministic",
        )
    assert repository.require("content-repair", "content_package") == package


def test_content_repair_projection_rederives_review_readiness_from_current_fingerprints(
    tmp_path: Path,
) -> None:
    repository, app = _app(tmp_path, "stale-review")
    package = repository.require("stale-review", "content_package")
    target = next(
        asset
        for subtopic in package["body"]["subtopics"]
        for asset in subtopic["assets"]
        if asset["id"] == TARGET_ASSET
    )
    target["claims"][0]["support"] = "supported"
    target["claims"][0]["note"] = "Supported for review-readiness setup."
    target["verification"]["supported"] += 1
    target["verification"]["unsupported"] -= 1
    package = repository.save(
        package,
        expected_checksum=repository.checksum(
            repository.require("stale-review", "content_package")
        ),
    )
    review = content_review.build_content_review_artifact(package)
    for record in review["body"]["assets"]:
        record["decision"] = "approved"
        record["reviewed_at"] = "2026-07-20T00:00:00+00:00"
    review["body"]["summary"] = content_review.review_summary(review["body"])
    review["status"] = "approved"
    repository.save(
        review,
        expected_checksum=repository.checksum(repository.require("stale-review", "content_review")),
    )
    current = repository.require("stale-review", "content_package")
    unrelated = next(
        asset
        for subtopic in current["body"]["subtopics"]
        for asset in subtopic["assets"]
        if asset["id"] != TARGET_ASSET
    )
    unrelated["title"] += " changed after review"
    repository.save(
        current,
        expected_checksum=repository.checksum(
            repository.require("stale-review", "content_package")
        ),
    )

    projection = app.state.content_repairs.project("stale-review")

    assert projection["hard_blocker_total"] == 0
    assert projection["review_summary"]["pending"] == 1
    assert projection["ready_for_package"] is False
