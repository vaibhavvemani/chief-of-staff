"""Bounded verifier-driven source research and atomic route transactions."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents.source_repair import (
    DeterministicSourceRepairProvider,
    RepairResearchScope,
    SourceRepairProvider,
    build_source_repair_artifact,
    candidate_record,
)
from api.services.artifact_repository import (
    ArtifactRepository,
    ReadOnlyCourse,
    VersionConflict,
)
from api.services.local_job_runner import _safe_error_message
from course_model_integrity import validate_course_model_semantics
from schema_validation import validate_json_schema
from source_store import SourceStore


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class SourceRepairOriginChanged(ValueError):
    pass


class SourceRepairService:
    def __init__(
        self,
        repository: ArtifactRepository,
        *,
        deterministic_provider: SourceRepairProvider | None = None,
        live_provider: SourceRepairProvider | None = None,
    ) -> None:
        self.repository = repository
        self.providers: dict[str, SourceRepairProvider | None] = {
            "deterministic": deterministic_provider or DeterministicSourceRepairProvider(),
            "live": live_provider,
        }
        self.schema = json.loads(
            (repository.repo_root / "schemas" / "source_repair.v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def view(self, course_id: str) -> dict[str, Any]:
        self.repository.locate(course_id)
        ledger = self.repository.load(course_id, "source_repair")
        if ledger is None:
            return {"artifact": None, "checksum": "missing", "entries": []}
        self._validate_ledger(ledger)
        return {
            "artifact": ledger,
            "checksum": self.repository.checksum(ledger),
            "entries": ledger.get("body", {}).get("entries", []),
        }

    def request(
        self,
        course_id: str,
        *,
        expected_content_checksum: str,
        subtopic_id: str,
        asset_id: str,
        claim_id: str,
        finding_id: str,
        evidence_gap: str,
        mode: str,
    ) -> dict[str, Any]:
        self._writable(course_id)
        content_package = self.repository.require(course_id, "content_package")
        if content_package.get("status") == "stale":
            raise ValueError("source repair cannot start from a stale Content Package")
        actual = self.repository.checksum(content_package)
        if actual != expected_content_checksum:
            raise VersionConflict(actual)
        self._require_approved_route_inputs(course_id)
        asset, claim = self._validate_origin(
            content_package,
            subtopic_id=subtopic_id,
            asset_id=asset_id,
            claim_id=claim_id,
            finding_id=finding_id,
        )
        if claim.get("support") == "supported":
            raise ValueError("source repair requires a current non-supported finding")
        gap = evidence_gap.strip()
        if not gap:
            raise ValueError("source repair requires an evidence-gap description")
        if len(gap) > 2_000:
            raise ValueError("evidence-gap description is too long")
        if mode not in self.providers:
            raise ValueError(f"unknown source-repair mode: {mode!r}")
        if self.providers[mode] is None:
            raise ValueError(f"{mode} source repair is not configured")

        existing = self.repository.load(course_id, "source_repair")
        ledger = deepcopy(existing) if existing else build_source_repair_artifact(course_id)
        entries = ledger["body"]["entries"]
        timestamp = _now()
        for active_entry in entries:
            if (
                active_entry.get("origin", {}).get("asset_id") == asset_id
                and active_entry.get("origin", {}).get("finding_id") == finding_id
                and active_entry.get("status") not in {"resolved", "failed"}
                and active_entry.get("origin", {}).get("content_checksum") != actual
            ):
                active_entry["status"] = "failed"
                active_entry["failure_reason"] = (
                    "Superseded because the Content Package changed after this repair "
                    "was requested."
                )
                active_entry["updated_at"] = timestamp
        if any(
            entry.get("origin", {}).get("asset_id") == asset_id
            and entry.get("origin", {}).get("finding_id") == finding_id
            and entry.get("status") not in {"resolved", "failed"}
            for entry in entries
        ):
            raise ValueError("an active source repair already exists for this finding")
        cursor = ledger["body"].get("next_repair_id")
        if type(cursor) is not int or cursor < 1:
            raise ValueError("source repair next_repair_id must be a positive integer")
        repair_id = f"repair_{cursor}"
        entries.append(
            {
                "id": repair_id,
                "origin": {
                    "subtopic_id": subtopic_id,
                    "asset_id": asset["id"],
                    "claim_id": claim["id"],
                    "finding_id": finding_id,
                    "content_checksum": actual,
                },
                "evidence_gap": gap,
                "requested_mode": mode,
                "proposed_candidates": [],
                "human_source_decision": None,
                "approved_source_route": None,
                "affected_asset_ids": [],
                "status": "requested",
                "final_verifier_result": None,
                "failure_reason": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        ledger["body"]["next_repair_id"] = cursor + 1
        self._prepare_ledger_revision(
            ledger,
            existing,
            note=f"Requested bounded evidence research for {asset_id}/{finding_id}.",
        )
        self._validate_ledger(ledger)
        saved = self.repository.save(
            ledger,
            expected_checksum=self.repository.checksum(existing) if existing else "missing",
        )
        return {
            "repair_id": repair_id,
            "artifact": saved,
            "checksum": self.repository.checksum(saved),
        }

    def research(
        self,
        course_id: str,
        repair_id: str,
        *,
        emit=lambda *_args, **_kwargs: None,
    ) -> dict[str, Any]:
        ledger = self.repository.require(course_id, "source_repair")
        entry = self._entry(ledger, repair_id)
        if entry["status"] != "requested":
            raise ValueError("source repair is not waiting for research")
        provider = self.providers.get(entry["requested_mode"])
        if provider is None:
            raise ValueError(f"{entry['requested_mode']} source repair is not configured")

        researching = deepcopy(ledger)
        researching_entry = self._entry(researching, repair_id)
        researching_entry["status"] = "researching"
        researching_entry["updated_at"] = _now()
        self._prepare_ledger_revision(
            researching,
            ledger,
            note=f"Started bounded evidence research for {repair_id}.",
        )
        self._validate_ledger(researching)
        researching = self.repository.save(
            researching,
            expected_checksum=self.repository.checksum(ledger),
        )
        emit(
            "source_repair.researching",
            repair_id=repair_id,
            message="Researching one evidence gap",
        )
        scope = RepairResearchScope(
            repair_id=repair_id,
            subtopic_id=entry["origin"]["subtopic_id"],
            asset_id=entry["origin"]["asset_id"],
            claim_id=entry["origin"]["claim_id"],
            finding_id=entry["origin"]["finding_id"],
            evidence_gap=entry["evidence_gap"],
        )
        staged_paths: list[Path] = []
        try:
            # Provider contracts are advisory at the process boundary. Enforce the
            # job's candidate bound locally even if an injected provider ignores it.
            candidates = provider.research(scope, limit=3)[:3]
            if not candidates:
                raise ValueError("bounded evidence research returned no candidates")
            candidate_ids = [candidate.id for candidate in candidates]
            if len(candidate_ids) != len(set(candidate_ids)):
                raise ValueError("bounded evidence research returned duplicate candidate IDs")
            records = []
            for candidate in candidates:
                staged_ref = None
                if candidate.content:
                    staged = SourceStore(
                        self.repository.runtime_location(course_id).artifact_root
                        / "sources"
                        / "_repair_candidates"
                    ).persist(
                        course_id=repair_id,
                        source_id=candidate.id,
                        content=candidate.content,
                        locator=candidate.locator,
                    )
                    staged_ref = staged.content_ref
                    staged_paths.append(Path(staged.content_ref))
                records.append(
                    candidate_record(
                        candidate,
                        evidence_gap=entry["evidence_gap"],
                        staged_content_ref=staged_ref,
                    )
                )
        except Exception as exc:
            for staged_path in staged_paths:
                staged_path.unlink(missing_ok=True)
            failed = deepcopy(researching)
            failed_entry = self._entry(failed, repair_id)
            failed_entry["status"] = "failed"
            failed_entry["failure_reason"] = _safe_error_message(exc)
            failed_entry["updated_at"] = _now()
            self._prepare_ledger_revision(
                failed,
                researching,
                note=f"Bounded evidence research failed for {repair_id}.",
            )
            self._validate_ledger(failed)
            self.repository.save(
                failed,
                expected_checksum=self.repository.checksum(researching),
            )
            raise

        completed = deepcopy(researching)
        completed_entry = self._entry(completed, repair_id)
        completed_entry["proposed_candidates"] = records
        completed_entry["status"] = "awaiting_source_decision"
        completed_entry["updated_at"] = _now()
        self._prepare_ledger_revision(
            completed,
            researching,
            note=f"Captured bounded source candidates for {repair_id}.",
        )
        self._validate_ledger(completed)
        saved = self.repository.save(
            completed,
            expected_checksum=self.repository.checksum(researching),
        )
        emit(
            "source_repair.candidates_ready",
            repair_id=repair_id,
            candidate_count=len(records),
            message="Candidates are ready for human review",
        )
        return {
            "repair_id": repair_id,
            "candidate_count": len(records),
            "checksum": self.repository.checksum(saved),
        }

    def decide_candidate(
        self,
        course_id: str,
        repair_id: str,
        *,
        expected_checksum: str,
        candidate_id: str,
        decision: str,
        rationale: str,
    ) -> dict[str, Any]:
        self._writable(course_id)
        ledger = self.repository.require(course_id, "source_repair")
        actual = self.repository.checksum(ledger)
        if actual != expected_checksum:
            raise VersionConflict(actual)
        entry = self._entry(ledger, repair_id)
        if entry["status"] != "awaiting_source_decision":
            raise ValueError("source repair is not awaiting a source decision")
        try:
            self._require_unchanged_origin(course_id, entry)
        except SourceRepairOriginChanged as exc:
            self._fail_changed_origin(
                ledger,
                repair_id,
                expected_checksum=expected_checksum,
                reason=str(exc),
            )
            raise
        candidates = {candidate["id"]: candidate for candidate in entry["proposed_candidates"]}
        if candidate_id not in candidates:
            raise ValueError(f"unknown repair candidate: {candidate_id}")
        if decision not in {"approved", "rejected"}:
            raise ValueError("source decision must be approved or rejected")
        normalized_rationale = rationale.strip()
        if not normalized_rationale:
            raise ValueError("source decision rationale cannot be blank")
        if decision == "approved" and candidates[candidate_id]["fetch_status"] != "available":
            raise ValueError("a contentless or unavailable candidate cannot be approved")
        updated = deepcopy(ledger)
        updated_entry = self._entry(updated, repair_id)
        updated_entry["human_source_decision"] = {
            "candidate_id": candidate_id,
            "decision": decision,
            "rationale": normalized_rationale,
        }
        updated_entry["status"] = (
            "awaiting_route_confirmation" if decision == "approved" else "failed"
        )
        updated_entry["failure_reason"] = (
            None
            if decision == "approved"
            else "The proposed source was rejected by the course director."
        )
        updated_entry["updated_at"] = _now()
        self._prepare_ledger_revision(
            updated,
            ledger,
            note=f"Recorded the human source decision for {repair_id}.",
        )
        self._validate_ledger(updated)
        saved = self.repository.save(updated, expected_checksum=expected_checksum)
        return {"artifact": saved, "checksum": self.repository.checksum(saved)}

    def confirm_route(
        self,
        course_id: str,
        repair_id: str,
        *,
        expected_checksum: str,
        subtopic_ids: list[str],
        asset_ids: list[str],
    ) -> dict[str, Any]:
        """Apply the human-confirmed route as one exact artifact transaction."""
        self._writable(course_id)
        ledger = self.repository.require(course_id, "source_repair")
        actual = self.repository.checksum(ledger)
        if actual != expected_checksum:
            raise VersionConflict(actual)
        entry = self._entry(ledger, repair_id)
        if entry["status"] != "awaiting_route_confirmation":
            raise ValueError("source repair is not awaiting route confirmation")
        if subtopic_ids != [entry["origin"]["subtopic_id"]]:
            raise ValueError("source repair may route only to its confirmed originating subtopic")
        if asset_ids != [entry["origin"]["asset_id"]]:
            raise ValueError("source repair may route only to its confirmed originating asset")
        decision = entry.get("human_source_decision") or {}
        if decision.get("decision") != "approved":
            raise ValueError("route confirmation requires an approved human source decision")
        candidate = next(
            (
                item
                for item in entry["proposed_candidates"]
                if item["id"] == decision.get("candidate_id")
            ),
            None,
        )
        if candidate is None or candidate.get("fetch_status") != "available":
            raise ValueError("approved repair candidate is unavailable")
        staged_content = self._read_staged_candidate(course_id, candidate)

        dossier = self.repository.require(course_id, "research_dossier")
        registry = self.repository.require(course_id, "approved_source_registry")
        course_model = self.repository.require(course_id, "course_model")
        blueprint = self.repository.require(course_id, "blueprint")
        content_package = self.repository.require(course_id, "content_package")
        self._require_approved_route_inputs(course_id)
        try:
            self._require_unchanged_origin(
                course_id,
                entry,
                content_package=content_package,
            )
        except SourceRepairOriginChanged as exc:
            self._fail_changed_origin(
                ledger,
                repair_id,
                expected_checksum=expected_checksum,
                reason=str(exc),
            )
            raise
        self._validate_origin(
            content_package,
            subtopic_id=subtopic_ids[0],
            asset_id=asset_ids[0],
            claim_id=entry["origin"]["claim_id"],
            finding_id=entry["origin"]["finding_id"],
        )
        if any(
            source.get("id") == candidate["id"]
            for source in registry.get("body", {}).get("source_registry", [])
            if isinstance(source, dict)
        ):
            raise ValueError("approved source ID already exists in the registry")

        source_root = self.repository.runtime_location(course_id).artifact_root / "sources"
        canonical_path = source_root / course_id / f"{candidate['id']}.md"
        if canonical_path.exists():
            raise ValueError("approved source content path already exists")
        stored = SourceStore(source_root).persist(
            course_id=course_id,
            source_id=candidate["id"],
            content=staged_content,
            locator=candidate["locator"],
        )
        try:
            updated_dossier = self._updated_dossier(
                dossier,
                candidate=candidate,
                content_ref=stored.content_ref,
                subtopic_ids=subtopic_ids,
                repair_id=repair_id,
            )
            updated_registry = self._updated_registry(
                registry,
                candidate=candidate,
                content_ref=stored.content_ref,
                repair_id=repair_id,
            )
            updated_model = self._updated_course_model(
                course_model,
                candidate=candidate,
                content_ref=stored.content_ref,
                subtopic_ids=subtopic_ids,
                repair_id=repair_id,
            )
            updated_blueprint = self._updated_blueprint(
                blueprint,
                source_id=candidate["id"],
                asset_ids=asset_ids,
                repair_id=repair_id,
            )
            updated_ledger = deepcopy(ledger)
            updated_entry = self._entry(updated_ledger, repair_id)
            updated_entry["approved_source_route"] = {
                "source_id": candidate["id"],
                "subtopic_ids": subtopic_ids,
                "asset_ids": asset_ids,
            }
            updated_entry["affected_asset_ids"] = asset_ids
            updated_entry["status"] = "awaiting_content_repair"
            updated_entry["updated_at"] = _now()
            self._prepare_ledger_revision(
                updated_ledger,
                ledger,
                note=f"Approved and routed source {candidate['id']} for {repair_id}.",
            )
            self._validate_ledger(updated_ledger)
            integrity_errors = validate_course_model_semantics(
                updated_model,
                course_outcomes=self.repository.require(course_id, "course_outcomes"),
                research_dossier=updated_dossier,
                approved_source_registry=updated_registry,
                blueprint=updated_blueprint,
            )
            if integrity_errors:
                raise ValueError("; ".join(integrity_errors))
            writes = [
                (updated_dossier, self.repository.checksum(dossier)),
                (updated_registry, self.repository.checksum(registry)),
                (updated_model, self.repository.checksum(course_model)),
                (updated_blueprint, self.repository.checksum(blueprint)),
                (updated_ledger, expected_checksum),
            ]
            persisted = self.repository.save_batch(writes)
        except BaseException:
            canonical_path.unlink(missing_ok=True)
            raise
        return {
            "source_id": candidate["id"],
            "affected_asset_ids": asset_ids,
            "artifact_types": [item["artifact_type"] for item in persisted],
            "checksum": self.repository.checksum(persisted[-1]),
        }

    def _validate_ledger(self, ledger: dict[str, Any]) -> None:
        issues = validate_json_schema(ledger, self.schema)
        if issues:
            detail = "; ".join(f"{issue['path']}: {issue['message']}" for issue in issues[:12])
            raise ValueError(f"invalid source_repair artifact: {detail}")

    def _writable(self, course_id: str) -> None:
        if self.repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")

    def _require_approved_route_inputs(self, course_id: str) -> None:
        for artifact_type in (
            "research_dossier",
            "approved_source_registry",
            "course_model",
            "blueprint",
        ):
            artifact = self.repository.require(course_id, artifact_type)
            if artifact.get("status") != "approved":
                raise ValueError(
                    f"{artifact_type} must be approved before using dedicated source repair"
                )

    def _require_unchanged_origin(
        self,
        course_id: str,
        entry: dict[str, Any],
        *,
        content_package: dict[str, Any] | None = None,
    ) -> None:
        current = content_package or self.repository.require(course_id, "content_package")
        requested_checksum = entry.get("origin", {}).get("content_checksum")
        if (
            current.get("status") == "stale"
            or self.repository.checksum(current) != requested_checksum
        ):
            raise SourceRepairOriginChanged(
                "the Content Package changed after this source repair was requested; "
                "return to the current verifier finding before starting a new repair"
            )
        _asset, claim = self._validate_origin(
            current,
            subtopic_id=entry["origin"]["subtopic_id"],
            asset_id=entry["origin"]["asset_id"],
            claim_id=entry["origin"]["claim_id"],
            finding_id=entry["origin"]["finding_id"],
        )
        if claim.get("support") == "supported":
            raise SourceRepairOriginChanged(
                "the originating verifier finding is no longer repairable"
            )

    def _fail_changed_origin(
        self,
        ledger: dict[str, Any],
        repair_id: str,
        *,
        expected_checksum: str,
        reason: str,
    ) -> None:
        failed = deepcopy(ledger)
        failed_entry = self._entry(failed, repair_id)
        failed_entry["status"] = "failed"
        failed_entry["failure_reason"] = reason[:2_000]
        failed_entry["updated_at"] = _now()
        self._prepare_ledger_revision(
            failed,
            ledger,
            note=f"Stopped {repair_id} because its verifier origin changed.",
        )
        self._validate_ledger(failed)
        self.repository.save(failed, expected_checksum=expected_checksum)

    @staticmethod
    def _validate_origin(
        content_package: dict[str, Any],
        *,
        subtopic_id: str,
        asset_id: str,
        claim_id: str,
        finding_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if finding_id != claim_id:
            raise ValueError("the current verifier contract requires finding_id to match claim_id")
        for subtopic in content_package.get("body", {}).get("subtopics", []):
            if subtopic.get("subtopic_id") != subtopic_id:
                continue
            for asset in subtopic.get("assets", []):
                if asset.get("id") != asset_id:
                    continue
                claim = next(
                    (item for item in asset.get("claims", []) if item.get("id") == claim_id),
                    None,
                )
                if claim is None:
                    raise ValueError(f"claim {claim_id!r} does not exist on asset {asset_id!r}")
                return asset, claim
        raise ValueError(f"asset {asset_id!r} does not exist under subtopic {subtopic_id!r}")

    @staticmethod
    def _entry(ledger: dict[str, Any], repair_id: str) -> dict[str, Any]:
        entry = next(
            (
                item
                for item in ledger.get("body", {}).get("entries", [])
                if item.get("id") == repair_id
            ),
            None,
        )
        if entry is None:
            raise ValueError(f"unknown source repair: {repair_id}")
        return entry

    @staticmethod
    def _prepare_ledger_revision(
        updated: dict[str, Any],
        existing: dict[str, Any] | None,
        *,
        note: str,
    ) -> None:
        updated["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        updated["revision_note"] = note
        updated["produced_by_step"] = "source_repair"
        updated["status"] = "approved"

    def _read_staged_candidate(
        self,
        course_id: str,
        candidate: dict[str, Any],
    ) -> str:
        content_ref = candidate.get("staged_content_ref")
        if not isinstance(content_ref, str) or not content_ref:
            raise ValueError("approved repair candidate has no captured content")
        candidate_root = (
            self.repository.runtime_location(course_id).artifact_root
            / "sources"
            / "_repair_candidates"
        ).resolve()
        path = Path(content_ref).resolve()
        try:
            path.relative_to(candidate_root)
        except ValueError as exc:
            raise ValueError("repair candidate content reference escapes its staging root") from exc
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"repair candidate content is unreadable: {exc}") from exc
        if not content.strip():
            raise ValueError("repair candidate content is empty")
        return content

    @staticmethod
    def _human_revision(artifact: dict[str, Any], *, note: str) -> dict[str, Any]:
        updated = deepcopy(artifact)
        updated["revision"] = int(artifact.get("revision", 0)) + 1
        updated["revision_note"] = note
        updated["produced_by_step"] = "human"
        return updated

    def _updated_dossier(
        self,
        dossier: dict[str, Any],
        *,
        candidate: dict[str, Any],
        content_ref: str,
        subtopic_ids: list[str],
        repair_id: str,
    ) -> dict[str, Any]:
        updated = self._human_revision(
            dossier,
            note=f"Source Repair {repair_id} approved and routed one bounded source.",
        )
        candidates = updated.get("body", {}).get("source_candidates", [])
        record = next((item for item in candidates if item.get("id") == candidate["id"]), None)
        values = {
            "id": candidate["id"],
            "title": candidate["title"],
            "publisher": candidate["publisher"],
            "source_type": candidate["source_type"],
            "locator": candidate["locator"],
            "content_ref": content_ref,
            "status": "approved",
            "trust_notes": candidate["trust_notes"],
            "relevance": candidate["relevance"],
            "assigned_node_ids": subtopic_ids,
            "decision_rationale": f"Approved through Source Repair {repair_id}.",
        }
        if record is None:
            candidates.append(values)
        else:
            record.update(values)
        return updated

    def _updated_registry(
        self,
        registry: dict[str, Any],
        *,
        candidate: dict[str, Any],
        content_ref: str,
        repair_id: str,
    ) -> dict[str, Any]:
        updated = self._human_revision(
            registry,
            note=f"Source Repair {repair_id} merged an explicit approved source.",
        )
        body = updated["body"]
        body.setdefault("source_registry", []).append(
            {
                "id": candidate["id"],
                "title": candidate["title"],
                "publisher": candidate["publisher"],
                "source_type": candidate["source_type"],
                "locator": candidate["locator"],
                "content_ref": content_ref,
            }
        )
        decision = body.setdefault("decision", {})
        for key in ("selected_ids", "approved_ids"):
            values = decision.setdefault(key, [])
            if candidate["id"] not in values:
                values.append(candidate["id"])
        rejected = decision.setdefault("rejected_ids", [])
        decision["rejected_ids"] = [item for item in rejected if item != candidate["id"]]
        options = body.setdefault("choice_prompt", {}).setdefault("options", [])
        if not any(item.get("id") == candidate["id"] for item in options):
            options.append(
                {
                    "id": candidate["id"],
                    "label": candidate["title"],
                    "description": f"{candidate['publisher']} - {candidate['relevance']}",
                    "recommended": True,
                    "recommendation_rationale": candidate["trust_notes"],
                }
            )
        return updated

    def _updated_course_model(
        self,
        course_model: dict[str, Any],
        *,
        candidate: dict[str, Any],
        content_ref: str,
        subtopic_ids: list[str],
        repair_id: str,
    ) -> dict[str, Any]:
        updated = self._human_revision(
            course_model,
            note=f"Source Repair {repair_id} added one named subtopic source mapping.",
        )
        source_id = candidate["id"]
        updated.get("body", {}).setdefault("source_registry", []).append(
            {
                "id": source_id,
                "title": candidate["title"],
                "publisher": candidate["publisher"],
                "source_type": candidate["source_type"],
                "locator": candidate["locator"],
                "content_ref": content_ref,
            }
        )
        found: set[str] = set()
        for module in updated.get("body", {}).get("modules", []):
            for subtopic in module.get("subtopics", []):
                if subtopic.get("id") not in subtopic_ids:
                    continue
                found.add(subtopic["id"])
                values = subtopic.setdefault("approved_source_ids", [])
                if source_id not in values:
                    values.append(source_id)
        missing = set(subtopic_ids) - found
        if missing:
            raise ValueError(f"unknown Course Model subtopic route(s): {sorted(missing)}")
        return updated

    def _updated_blueprint(
        self,
        blueprint: dict[str, Any],
        *,
        source_id: str,
        asset_ids: list[str],
        repair_id: str,
    ) -> dict[str, Any]:
        updated = self._human_revision(
            blueprint,
            note=f"Source Repair {repair_id} added one named asset source route.",
        )
        found: set[str] = set()
        for plan in updated.get("body", {}).get("subtopic_plans", []):
            plan_matched = False
            for asset in plan.get("asset_plan", []):
                if asset.get("id") not in asset_ids:
                    continue
                if asset.get("selection_status") != "selected":
                    raise ValueError("source repair cannot route to an unselected Blueprint asset")
                found.add(asset["id"])
                plan_matched = True
                values = asset.setdefault("source_ids", [])
                if source_id not in values:
                    values.append(source_id)
            if plan_matched:
                routed = ", ".join(
                    dict.fromkeys(
                        source
                        for asset in plan.get("asset_plan", [])
                        if asset.get("selection_status") == "selected"
                        for source in asset.get("source_ids", [])
                    )
                )
                plan["source_routing_notes"] = (
                    "Selected assets cite only this subtopic's approved source ids: " + routed
                )
        missing = set(asset_ids) - found
        if missing:
            raise ValueError(f"unknown Blueprint asset route(s): {sorted(missing)}")
        return updated
