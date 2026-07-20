from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.source_quality import (
    MAX_PREVIEW_CHARS,
    capture_relevant_sections,
    known_source_candidate,
    project_source_quality,
)
from agents.source_repair import RepairResearchScope, RepairSourceCandidate
from api.main import create_app
from api.services.artifact_repository import ArtifactRepository, VersionConflict
from api.services.source_quality_service import SourceQualityService
from api.services.source_repair_service import SourceRepairService

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_ROOT = REPO_ROOT / "examples" / "live-runs" / "coffee-live-main" / "course_artifacts"


def _load(name: str) -> dict:
    return json.loads((LIVE_ROOT / f"{name}.json").read_text(encoding="utf-8"))


def _repository(tmp_path: Path) -> ArtifactRepository:
    return ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )


def _seed_repair_course(repository: ArtifactRepository, course_id: str = "repair-course") -> None:
    for artifact_type in (
        "subject_request",
        "brief",
        "course_outcomes",
        "research_dossier",
        "approved_source_registry",
        "course_model",
        "blueprint",
        "content_package",
    ):
        artifact = _load(artifact_type)
        artifact["course_id"] = course_id
        artifact["status"] = "approved"
        if artifact_type == "content_package":
            claim = artifact["body"]["subtopics"][0]["assets"][0]["claims"][0]
            claim["support"] = "unsupported"
            claim["note"] = "The current approved routes do not support this claim."
            artifact["body"]["subtopics"][0]["assets"][0]["verification"]["unsupported"] = 1
            artifact["body"]["subtopics"][0]["assets"][0]["verification"]["supported"] -= 1
        repository.save(artifact)


class _UnavailableSourceRepairProvider:
    def research(
        self,
        scope: RepairResearchScope,
        *,
        limit: int,
    ) -> list[RepairSourceCandidate]:
        return [
            RepairSourceCandidate(
                id=f"unavailable_{scope.repair_id}",
                title="Unavailable focused source",
                publisher="Example Publisher",
                source_type="web page",
                locator="https://example.edu/unavailable",
                trust_notes="Metadata only; content capture failed.",
                relevance=scope.evidence_gap,
                content=None,
                fetch_reason="The source could not be fetched.",
            )
        ][:limit]


class _OverproducingSourceRepairProvider:
    def research(
        self,
        scope: RepairResearchScope,
        *,
        limit: int,
    ) -> list[RepairSourceCandidate]:
        del limit
        return [
            RepairSourceCandidate(
                id=f"bounded_candidate_{index}",
                title=f"Bounded candidate {index}",
                publisher="Example University",
                source_type="official guide",
                locator=f"https://example.edu/bounded/{index}",
                trust_notes="Institutional guidance for deterministic bounds testing.",
                relevance=scope.evidence_gap,
                content=f"Focused content for {scope.evidence_gap} candidate {index}.",
            )
            for index in range(5)
        ]


class _DuplicateSourceRepairProvider:
    def research(
        self,
        scope: RepairResearchScope,
        *,
        limit: int,
    ) -> list[RepairSourceCandidate]:
        del limit
        return [
            RepairSourceCandidate(
                id="duplicate_candidate",
                title=f"Duplicate {index}",
                publisher="Example University",
                source_type="official guide",
                locator=f"https://example.edu/duplicate/{index}",
                trust_notes="Deterministic duplicate-ID regression candidate.",
                relevance=scope.evidence_gap,
                content=f"Conflicting content {index} for {scope.evidence_gap}.",
            )
            for index in range(2)
        ]


class _SecretFailingSourceRepairProvider:
    def research(
        self,
        scope: RepairResearchScope,
        *,
        limit: int,
    ) -> list[RepairSourceCandidate]:
        del scope, limit
        raise RuntimeError(
            "authorization=Bearer-secret-token password=hunter2 sk-exampletoken123456"
        )


def _advance_repair_to_route_confirmation(
    repository: ArtifactRepository,
    service: SourceRepairService,
    *,
    course_id: str = "repair-course",
) -> tuple[str, str, str]:
    content = repository.require(course_id, "content_package")
    requested = service.request(
        course_id,
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Need focused evidence for the current unsupported claim.",
        mode="deterministic",
    )
    repair_id = requested["repair_id"]
    service.research(course_id, repair_id)
    ledger = repository.require(course_id, "source_repair")
    candidate_id = ledger["body"]["entries"][0]["proposed_candidates"][0]["id"]
    decided = service.decide_candidate(
        course_id,
        repair_id,
        expected_checksum=repository.checksum(ledger),
        candidate_id=candidate_id,
        decision="approved",
        rationale="Approve the available bounded evidence for its named route only.",
    )
    return repair_id, candidate_id, decided["checksum"]


def test_source_quality_scoring_is_transparent_advisory_and_bounded() -> None:
    content = (
        "# Water temperature\n\nWater temperature changes extraction and flavor. "
        "Use a controlled range and record the result.\n\n" + "Broad unrelated background. " * 1_000
    )
    projection = project_source_quality(
        {
            "title": "University water-temperature guidance 2026",
            "publisher": "Example University",
            "source_type": "official guide",
            "locator": "https://example.edu/water-temperature",
            "trust_notes": "University extension guidance.",
            "relevance": "Supports extraction and water-temperature decisions.",
        },
        evidence_needs=["How water temperature changes extraction"],
        content=content,
    )

    assert projection["advisory_only"] is True
    assert set(projection["dimensions"]) == {
        "authority",
        "fit",
        "specificity",
        "freshness",
        "fetch_status",
        "content_availability",
    }
    assert all("reason" in value for value in projection["dimensions"].values())
    assert projection["coverage"][0]["matched_terms"]
    assert sum(len(section["text"]) for section in projection["preview_sections"]) <= (
        MAX_PREVIEW_CHARS
    )
    assert len(capture_relevant_sections(content, evidence_needs=["temperature"])) <= 4


def test_known_source_candidate_normalizes_url_and_never_self_approves() -> None:
    candidate = known_source_candidate(
        "HTTPS://Example.EDU/guides/water-temperature#details",
        title="Water temperature guide",
    )

    assert candidate["id"].startswith("known_")
    assert candidate["locator"] == "https://example.edu/guides/water-temperature"
    assert candidate["status"] == "proposed"
    assert candidate["content_ref"] is None
    with pytest.raises(ValueError, match="absolute http or https"):
        known_source_candidate("file:///private/secret")
    with pytest.raises(ValueError, match="credentials"):
        known_source_candidate("https://user:pass@example.edu/guide")


def test_known_source_mutation_is_checksum_safe_and_preserves_approved_registry(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceQualityService(repository)
    dossier = repository.require("repair-course", "research_dossier")
    registry_before = deepcopy(repository.require("repair-course", "approved_source_registry"))

    saved = service.add_known_source(
        "repair-course",
        expected_checksum=repository.checksum(dossier),
        locator="https://example.edu/focused-guide",
        title="Focused guide",
        publisher="Example University",
        trust_notes="University guidance; still requires review.",
        relevance="Addresses the missing evidence area.",
    )

    added = saved["body"]["source_candidates"][-1]
    assert added["status"] == "proposed"
    assert saved["status"] == "approved"
    assert repository.require("repair-course", "approved_source_registry") == registry_before
    with pytest.raises(VersionConflict):
        service.add_known_source(
            "repair-course",
            expected_checksum=repository.checksum(dossier),
            locator="https://example.edu/another-guide",
            title=None,
            publisher=None,
            trust_notes=None,
            relevance=None,
        )


def test_source_repair_full_deterministic_flow_updates_only_confirmed_route(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(repository)
    content = repository.require("repair-course", "content_package")
    model_before = deepcopy(repository.require("repair-course", "course_model"))
    blueprint_with_custom_note = deepcopy(repository.require("repair-course", "blueprint"))
    blueprint_with_custom_note["body"]["subtopic_plans"][1]["source_routing_notes"] = (
        "Preserve this unrelated historical routing note verbatim."
    )
    repository.save(
        blueprint_with_custom_note,
        expected_checksum=repository.checksum(repository.require("repair-course", "blueprint")),
    )
    blueprint_before = deepcopy(repository.require("repair-course", "blueprint"))
    unrelated_model = deepcopy(model_before["body"]["modules"][0]["subtopics"][1])
    unrelated_plan = deepcopy(blueprint_before["body"]["subtopic_plans"][1])

    requested = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Find focused evidence for the unsupported coffee-origin claim.",
        mode="deterministic",
    )
    repair_id = requested["repair_id"]
    assert service.view("repair-course")["entries"][0]["status"] == "requested"

    researched = service.research("repair-course", repair_id)
    ledger = repository.require("repair-course", "source_repair")
    entry = ledger["body"]["entries"][0]
    assert researched["candidate_count"] == 1
    assert entry["status"] == "awaiting_source_decision"
    candidate = entry["proposed_candidates"][0]
    assert candidate["quality"]["advisory_only"] is True
    assert candidate["quality"]["preview_sections"]
    assert candidate["fetch_status"] == "available"
    assert candidate["id"] not in {
        item["id"]
        for item in repository.require("repair-course", "approved_source_registry")["body"][
            "source_registry"
        ]
    }

    decided = service.decide_candidate(
        "repair-course",
        repair_id,
        expected_checksum=repository.checksum(ledger),
        candidate_id=candidate["id"],
        decision="approved",
        rationale="The bounded preview directly addresses the named evidence gap.",
    )
    assert decided["artifact"]["body"]["entries"][0]["status"] == ("awaiting_route_confirmation")

    routed = service.confirm_route(
        "repair-course",
        repair_id,
        expected_checksum=decided["checksum"],
        subtopic_ids=["m1_s1"],
        asset_ids=["m1_s1_cc"],
    )

    assert routed["affected_asset_ids"] == ["m1_s1_cc"]
    assert set(routed["artifact_types"]) == {
        "research_dossier",
        "approved_source_registry",
        "course_model",
        "blueprint",
        "source_repair",
    }
    source_id = routed["source_id"]
    registry = repository.require("repair-course", "approved_source_registry")
    assert source_id in registry["body"]["decision"]["approved_ids"]
    model = repository.require("repair-course", "course_model")
    blueprint = repository.require("repair-course", "blueprint")
    assert source_id in model["body"]["modules"][0]["subtopics"][0]["approved_source_ids"]
    assert source_id in blueprint["body"]["subtopic_plans"][0]["asset_plan"][1]["source_ids"]
    assert model["body"]["modules"][0]["subtopics"][1] == unrelated_model
    assert blueprint["body"]["subtopic_plans"][1] == unrelated_plan
    assert repository.require("repair-course", "content_package") == content
    final_entry = repository.require("repair-course", "source_repair")["body"]["entries"][0]
    assert final_entry["status"] == "awaiting_content_repair"
    assert final_entry["approved_source_route"] == {
        "source_id": source_id,
        "subtopic_ids": ["m1_s1"],
        "asset_ids": ["m1_s1_cc"],
    }


def test_source_repair_rejects_scope_expansion_without_mutating_routes(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(repository)
    content = repository.require("repair-course", "content_package")
    requested = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Need focused evidence.",
        mode="deterministic",
    )
    service.research("repair-course", requested["repair_id"])
    ledger = repository.require("repair-course", "source_repair")
    candidate = ledger["body"]["entries"][0]["proposed_candidates"][0]
    decided = service.decide_candidate(
        "repair-course",
        requested["repair_id"],
        expected_checksum=repository.checksum(ledger),
        candidate_id=candidate["id"],
        decision="approved",
        rationale="Approve for the named gap only.",
    )
    model_before = deepcopy(repository.require("repair-course", "course_model"))

    with pytest.raises(ValueError, match="originating subtopic"):
        service.confirm_route(
            "repair-course",
            requested["repair_id"],
            expected_checksum=decided["checksum"],
            subtopic_ids=["m1_s2"],
            asset_ids=["m1_s1_cc"],
        )
    assert repository.require("repair-course", "course_model") == model_before


def test_source_repair_blocks_contentless_candidate_approval(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(
        repository,
        deterministic_provider=_UnavailableSourceRepairProvider(),
    )
    content = repository.require("repair-course", "content_package")
    registry_before = deepcopy(repository.require("repair-course", "approved_source_registry"))
    requested = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Need focused evidence.",
        mode="deterministic",
    )
    service.research("repair-course", requested["repair_id"])
    ledger = repository.require("repair-course", "source_repair")
    candidate = ledger["body"]["entries"][0]["proposed_candidates"][0]

    assert candidate["fetch_status"] == "unavailable"
    assert candidate["quality"]["preview_sections"] == []
    with pytest.raises(ValueError, match="contentless or unavailable"):
        service.decide_candidate(
            "repair-course",
            requested["repair_id"],
            expected_checksum=repository.checksum(ledger),
            candidate_id=candidate["id"],
            decision="approved",
            rationale="This should not be accepted.",
        )
    assert repository.require("repair-course", "approved_source_registry") == (registry_before)


def test_source_repair_enforces_candidate_bound_when_provider_overproduces(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(
        repository,
        deterministic_provider=_OverproducingSourceRepairProvider(),
    )
    content = repository.require("repair-course", "content_package")
    requested = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Need focused evidence.",
        mode="deterministic",
    )

    researched = service.research("repair-course", requested["repair_id"])
    ledger = repository.require("repair-course", "source_repair")

    assert researched["candidate_count"] == 3
    assert len(ledger["body"]["entries"][0]["proposed_candidates"]) == 3


def test_source_repair_rejects_duplicate_provider_ids_before_staging(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(
        repository,
        deterministic_provider=_DuplicateSourceRepairProvider(),
    )
    content = repository.require("repair-course", "content_package")
    registry_before = deepcopy(repository.require("repair-course", "approved_source_registry"))
    requested = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Need focused evidence.",
        mode="deterministic",
    )

    with pytest.raises(ValueError, match="duplicate candidate IDs"):
        service.research("repair-course", requested["repair_id"])

    entry = repository.require("repair-course", "source_repair")["body"]["entries"][0]
    staged_root = (
        repository.runtime_location("repair-course").artifact_root
        / "sources"
        / "_repair_candidates"
    )
    assert entry["status"] == "failed"
    assert list(staged_root.rglob("*.md")) == []
    assert repository.require("repair-course", "approved_source_registry") == (registry_before)


def test_source_repair_redacts_provider_failure_from_canonical_ledger(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(
        repository,
        deterministic_provider=_SecretFailingSourceRepairProvider(),
    )
    content = repository.require("repair-course", "content_package")
    requested = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Need focused evidence.",
        mode="deterministic",
    )

    with pytest.raises(RuntimeError, match="authorization"):
        service.research("repair-course", requested["repair_id"])

    failure = repository.require("repair-course", "source_repair")["body"]["entries"][0][
        "failure_reason"
    ]
    assert "[redacted]" in failure
    assert "hunter2" not in failure
    assert "exampletoken123456" not in failure


def test_source_repair_route_failure_rolls_back_artifacts_and_source_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(repository)
    repair_id, candidate_id, ledger_checksum = _advance_repair_to_route_confirmation(
        repository,
        service,
    )
    protected_types = (
        "research_dossier",
        "approved_source_registry",
        "course_model",
        "blueprint",
        "content_package",
        "source_repair",
    )
    before = {
        artifact_type: deepcopy(repository.require("repair-course", artifact_type))
        for artifact_type in protected_types
    }
    source_path = (
        repository.runtime_location("repair-course").artifact_root
        / "sources"
        / "repair-course"
        / f"{candidate_id}.md"
    )

    def fail_transaction(_writes: object) -> list[dict]:
        raise RuntimeError("injected batch failure")

    monkeypatch.setattr(repository, "save_batch", fail_transaction)
    with pytest.raises(RuntimeError, match="injected batch failure"):
        service.confirm_route(
            "repair-course",
            repair_id,
            expected_checksum=ledger_checksum,
            subtopic_ids=["m1_s1"],
            asset_ids=["m1_s1_cc"],
        )

    assert source_path.exists() is False
    for artifact_type, artifact_before in before.items():
        assert repository.require("repair-course", artifact_type) == artifact_before


def test_source_repair_rejects_same_id_claim_changed_after_research(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _seed_repair_course(repository)
    service = SourceRepairService(repository)
    repair_id, candidate_id, ledger_checksum = _advance_repair_to_route_confirmation(
        repository,
        service,
    )
    protected_types = (
        "research_dossier",
        "approved_source_registry",
        "course_model",
        "blueprint",
    )
    protected_before = {
        artifact_type: deepcopy(repository.require("repair-course", artifact_type))
        for artifact_type in protected_types
    }
    changed_content = deepcopy(repository.require("repair-course", "content_package"))
    changed_claim = changed_content["body"]["subtopics"][0]["assets"][0]["claims"][0]
    changed_claim["text"] = "A newly generated claim retaining the historical ID."
    changed_claim["support"] = "partial"
    changed_claim["supporting_excerpt"] = "New evidence from another generation."
    repository.save(
        changed_content,
        expected_checksum=repository.checksum(
            repository.require("repair-course", "content_package")
        ),
    )
    source_path = (
        repository.runtime_location("repair-course").artifact_root
        / "sources"
        / "repair-course"
        / f"{candidate_id}.md"
    )

    with pytest.raises(ValueError, match="Content Package changed"):
        service.confirm_route(
            "repair-course",
            repair_id,
            expected_checksum=ledger_checksum,
            subtopic_ids=["m1_s1"],
            asset_ids=["m1_s1_cc"],
        )

    assert source_path.exists() is False
    for artifact_type, artifact_before in protected_before.items():
        assert repository.require("repair-course", artifact_type) == artifact_before
    failed_ledger = repository.require("repair-course", "source_repair")
    assert failed_ledger["body"]["entries"][0]["status"] == "failed"
    assert repository.require("repair-course", "content_package")["body"]["subtopics"][0]["assets"][
        0
    ]["claims"][0]["text"] == ("A newly generated claim retaining the historical ID.")
    current_content = repository.require("repair-course", "content_package")
    restarted = service.request(
        "repair-course",
        expected_content_checksum=repository.checksum(current_content),
        subtopic_id="m1_s1",
        asset_id="m1_s1_cc",
        claim_id="cl1",
        finding_id="cl1",
        evidence_gap="Research the current partial finding, not its superseded text.",
        mode="deterministic",
    )
    assert restarted["repair_id"] == "repair_2"


def test_http_source_quality_known_source_and_repair_contract(tmp_path: Path) -> None:
    courses_root = tmp_path / "courses"
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    _seed_repair_course(repository, course_id="http-repair")
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )

    with TestClient(app) as client:
        quality = client.get("/api/courses/http-repair/research/sources/quality")
        assert quality.status_code == 200
        assert quality.json()["sources"][0]["quality"]["advisory_only"] is True

        dossier = client.get("/api/courses/http-repair/artifacts/research_dossier").json()
        added = client.post(
            "/api/courses/http-repair/research/sources",
            json={
                "expected_checksum": dossier["checksum"],
                "locator": "https://example.edu/known-source",
                "title": "Known focused source",
            },
        )
        assert added.status_code == 201
        assert added.json()["artifact"]["body"]["source_candidates"][-1]["status"] == "proposed"

        content = client.get("/api/courses/http-repair/artifacts/content_package").json()
        requested = client.post(
            "/api/courses/http-repair/source-repairs",
            json={
                "expected_content_checksum": content["checksum"],
                "subtopic_id": "m1_s1",
                "asset_id": "m1_s1_cc",
                "claim_id": "cl1",
                "finding_id": "cl1",
                "evidence_gap": "The current route does not support this claim.",
                "mode": "deterministic",
            },
        )
        assert requested.status_code == 202
        job_id = requested.json()["job"]["job_id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert job["status"] == "completed"

        ledger_view = client.get("/api/courses/http-repair/source-repairs").json()
        entry = ledger_view["entries"][0]
        candidate_id = entry["proposed_candidates"][0]["id"]
        decided = client.put(
            f"/api/courses/http-repair/source-repairs/{entry['id']}/decision",
            json={
                "expected_checksum": ledger_view["checksum"],
                "candidate_id": candidate_id,
                "decision": "approved",
                "rationale": "The bounded preview covers the named gap.",
            },
        )
        assert decided.status_code == 200
        routed = client.put(
            f"/api/courses/http-repair/source-repairs/{entry['id']}/route",
            json={
                "expected_checksum": decided.json()["checksum"],
                "subtopic_ids": ["m1_s1"],
                "asset_ids": ["m1_s1_cc"],
            },
        )
        assert routed.status_code == 200
        assert routed.json()["affected_asset_ids"] == ["m1_s1_cc"]


def test_http_source_mutations_require_backend_projected_capabilities(
    tmp_path: Path,
) -> None:
    courses_root = tmp_path / "courses"
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    _seed_repair_course(repository, course_id="stale-research")
    stale_dossier = deepcopy(repository.require("stale-research", "research_dossier"))
    stale_dossier["status"] = "stale"
    stale_dossier = repository.save(
        stale_dossier,
        expected_checksum=repository.checksum(
            repository.require("stale-research", "research_dossier")
        ),
    )
    _seed_repair_course(repository, course_id="stale-content")
    stale_content = deepcopy(repository.require("stale-content", "content_package"))
    stale_content["status"] = "stale"
    stale_content = repository.save(
        stale_content,
        expected_checksum=repository.checksum(
            repository.require("stale-content", "content_package")
        ),
    )
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )

    with TestClient(app) as client:
        known = client.post(
            "/api/courses/stale-research/research/sources",
            json={
                "expected_checksum": repository.checksum(stale_dossier),
                "locator": "https://example.edu/should-not-be-added",
            },
        )
        repair = client.post(
            "/api/courses/stale-content/source-repairs",
            json={
                "expected_content_checksum": repository.checksum(stale_content),
                "subtopic_id": "m1_s1",
                "asset_id": "m1_s1_cc",
                "claim_id": "cl1",
                "finding_id": "cl1",
                "evidence_gap": "This stale package must not start repair.",
                "mode": "deterministic",
            },
        )

    assert known.status_code == 409
    assert repair.status_code == 409
    assert repository.load("stale-content", "source_repair") is None
    assert len(
        repository.require("stale-research", "research_dossier")["body"]["source_candidates"]
    ) == len(stale_dossier["body"]["source_candidates"])
