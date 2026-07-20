"""Typed verifier-driven Content repair and advisory repair projection."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from agents import content_review
from api.services.approval_guard import hard_verifier_blocker_count
from api.services.artifact_repository import (
    ArtifactRepository,
    ReadOnlyCourse,
    VersionConflict,
)
from api.services.lifecycle import InvalidationService
from api.services.local_job_runner import _safe_error_message
from api.services.pipeline_catalog import PipelineCatalog
from api.services.revision_service import NoOpRevision, RevisionService
from api.services.source_repair_service import SourceRepairService
from schema_validation import validate_json_schema


@dataclass(frozen=True)
class PreparedContentRepair:
    strategy: str
    asset_ids: tuple[str, ...]
    subtopic_id: str
    instruction: str
    feedback: str
    mode: str
    expected_content_checksum: str
    source_repair_id: str | None
    expected_source_repair_checksum: str | None


class ContentRepairService:
    """Regenerate, reverify, review-sync, and invalidate one bounded asset set."""

    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        revisions: RevisionService,
        invalidation: InvalidationService,
        source_repairs: SourceRepairService,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.revisions = revisions
        self.invalidation = invalidation
        self.source_repairs = source_repairs
        self.content_schema = json.loads(
            (repository.repo_root / "schemas" / "content_package.v0.2.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def project(self, course_id: str) -> dict[str, Any]:
        package = self.repository.require(course_id, "content_package")
        review = self.repository.load(course_id, "content_review") or {}
        source_entries = self.source_repairs.view(course_id)["entries"]
        content_checksum = self.repository.checksum(package)
        content_body_checksum = self.repository.checksum(package.get("body", {}))
        findings: list[dict[str, Any]] = []
        hard_total = 0
        partial_total = 0
        for subtopic in package.get("body", {}).get("subtopics", []):
            if not isinstance(subtopic, dict):
                continue
            subtopic_id = str(subtopic.get("subtopic_id") or "")
            for asset in subtopic.get("assets", []):
                if not isinstance(asset, dict) or not asset.get("id"):
                    continue
                asset_id = str(asset["id"])
                explicit_hard = 0
                for claim in asset.get("claims", []):
                    if not isinstance(claim, dict):
                        continue
                    source_id = claim.get("source_id")
                    has_source = isinstance(source_id, str) and bool(source_id.strip())
                    if claim.get("support") == "supported" and has_source:
                        continue
                    classification, reason, recommendation, blocking = self._classify_claim(claim)
                    explicit_hard += int(blocking)
                    partial_total += int(not blocking)
                    findings.append(
                        self._finding_projection(
                            source_entries,
                            current_content_checksum=content_checksum,
                            current_content_body_checksum=content_body_checksum,
                            subtopic_id=subtopic_id,
                            asset_id=asset_id,
                            claim_id=str(claim.get("id") or "verification_contract"),
                            finding_id=str(claim.get("id") or "verification_contract"),
                            text=str(claim.get("text") or "Verifier finding"),
                            note=str(claim.get("note") or ""),
                            classification=classification,
                            reason=reason,
                            recommendation=recommendation,
                            blocking=blocking,
                        )
                    )
                verification = asset.get("verification", {})
                unattributed = (
                    verification.get("unattributed_found", [])
                    if isinstance(verification, dict)
                    else []
                )
                if isinstance(unattributed, list):
                    for index, text in enumerate(unattributed, start=1):
                        explicit_hard += 1
                        findings.append(
                            self._finding_projection(
                                source_entries,
                                current_content_checksum=content_checksum,
                                current_content_body_checksum=content_body_checksum,
                                subtopic_id=subtopic_id,
                                asset_id=asset_id,
                                claim_id=None,
                                finding_id=f"unattributed_{index}",
                                text=str(text),
                                note="The verifier found a factual statement without attribution.",
                                classification="missing_attribution",
                                reason=(
                                    "No approved source attribution is attached to this statement."
                                ),
                                recommendation="existing_evidence",
                                blocking=True,
                            )
                        )
                asset_hard = hard_verifier_blocker_count(asset)
                hard_total += asset_hard
                for index in range(max(0, asset_hard - explicit_hard)):
                    findings.append(
                        self._finding_projection(
                            source_entries,
                            current_content_checksum=content_checksum,
                            current_content_body_checksum=content_body_checksum,
                            subtopic_id=subtopic_id,
                            asset_id=asset_id,
                            claim_id=None,
                            finding_id=f"verification_contract_{index + 1}",
                            text="The current claim ledger and verifier summary do not reconcile.",
                            note="Regenerate and reverify this asset before release.",
                            classification="likely_content_error",
                            reason=(
                                "The verifier contract is missing, stale, or internally "
                                "inconsistent."
                            ),
                            recommendation="existing_evidence",
                            blocking=True,
                        )
                    )
        group_counts = {
            name: sum(1 for finding in findings if finding["classification"] == name)
            for name in (
                "likely_content_error",
                "missing_attribution",
                "insufficient_evidence",
                "human_review",
            )
        }
        synchronized_review = content_review.build_content_review_artifact(
            package,
            existing_review=review or None,
        )
        review_summary = synchronized_review.get("body", {}).get("summary", {})
        if not isinstance(review_summary, dict):
            review_summary = {}
        return {
            "content_checksum": content_checksum,
            "findings": findings,
            "groups": group_counts,
            "hard_blocker_total": hard_total,
            "partial_total": partial_total,
            "review_summary": review_summary,
            "ready_for_package": bool(review_summary.get("ready_for_package")) and hard_total == 0,
        }

    def prepare(
        self,
        course_id: str,
        *,
        expected_content_checksum: str,
        strategy: str,
        targets: list[dict[str, Any]],
        source_repair_id: str | None,
        expected_source_repair_checksum: str | None,
        mode: str,
    ) -> PreparedContentRepair:
        self._writable(course_id)
        package = self.repository.require(course_id, "content_package")
        actual = self.repository.checksum(package)
        if actual != expected_content_checksum:
            raise VersionConflict(actual)
        if package.get("status") == "stale":
            raise ValueError("Content repair cannot start from a stale Content Package")
        if mode == "live":
            load_dotenv()
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "Live Student Content repair requires ANTHROPIC_API_KEY on the Python server."
                )
        elif mode != "deterministic":
            raise ValueError(f"unknown Content repair mode: {mode!r}")

        assets, subtopics = self._assets(package)
        asset_ids = tuple(target["asset_id"] for target in targets)
        unknown = sorted(set(asset_ids) - set(assets))
        if unknown:
            raise ValueError("unknown Content repair asset(s): " + ", ".join(unknown))
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("Content repair asset IDs must be unique")
        target_subtopics = {subtopics[asset_id] for asset_id in asset_ids}
        if len(target_subtopics) != 1:
            raise ValueError("one Content repair command cannot span multiple subtopics")
        for target in targets:
            self._validate_target(assets[target["asset_id"]], target)

        if strategy == "better_evidence":
            if not source_repair_id or not expected_source_repair_checksum:
                raise ValueError("better-evidence repair requires a Source Repair entry")
            view = self.source_repairs.view(course_id)
            if view["checksum"] != expected_source_repair_checksum:
                raise VersionConflict(view["checksum"])
            entry = next(
                (item for item in view["entries"] if item.get("id") == source_repair_id),
                None,
            )
            if entry is None:
                raise ValueError(f"unknown source repair: {source_repair_id}")
            if entry.get("status") != "awaiting_content_repair":
                raise ValueError("source repair is not awaiting targeted Content repair")
            if entry.get("requested_mode") != mode:
                raise ValueError("Content repair mode must match the approved Source Repair mode")
            if entry.get("affected_asset_ids") != list(asset_ids):
                raise ValueError("better-evidence repair must use the exact approved asset route")
            if entry.get("origin", {}).get("content_checksum") != actual:
                raise ValueError("the routed Source Repair no longer matches current Content")
        elif strategy != "existing_evidence":
            raise ValueError(f"unknown Content repair strategy: {strategy!r}")
        elif source_repair_id is not None or expected_source_repair_checksum is not None:
            raise ValueError("existing-evidence repair cannot name a Source Repair entry")

        instruction = self._instruction(strategy, targets, source_repair_id)
        revision = self.revisions.prepare(
            course_id,
            "content",
            target_type="asset",
            target_ids=list(asset_ids),
            category="evidence",
            instruction=instruction,
        )
        return PreparedContentRepair(
            strategy=strategy,
            asset_ids=asset_ids,
            subtopic_id=next(iter(target_subtopics)),
            instruction=instruction,
            feedback=revision.feedback,
            mode=mode,
            expected_content_checksum=expected_content_checksum,
            source_repair_id=source_repair_id,
            expected_source_repair_checksum=expected_source_repair_checksum,
        )

    def execute(
        self,
        course_id: str,
        *,
        expected_content_checksum: str,
        strategy: str,
        targets: list[dict[str, Any]],
        source_repair_id: str | None,
        expected_source_repair_checksum: str | None,
        mode: str,
        emit=lambda *_args, **_kwargs: None,
    ) -> dict[str, Any]:
        prepared = self.prepare(
            course_id,
            expected_content_checksum=expected_content_checksum,
            strategy=strategy,
            targets=targets,
            source_repair_id=source_repair_id,
            expected_source_repair_checksum=expected_source_repair_checksum,
            mode=mode,
        )
        started_ledger: dict[str, Any] | None = None
        committed = False
        if prepared.source_repair_id is not None:
            started_ledger = self.source_repairs.begin_content_repair(
                course_id,
                prepared.source_repair_id,
                expected_checksum=prepared.expected_source_repair_checksum or "",
                expected_content_checksum=prepared.expected_content_checksum,
                asset_ids=list(prepared.asset_ids),
            )
        emit(
            "content_repair.regenerating",
            strategy=prepared.strategy,
            asset_ids=list(prepared.asset_ids),
            message=f"Regenerating {len(prepared.asset_ids)} named Content asset(s)",
        )
        try:
            previous_package = self.repository.require(course_id, "content_package")
            if self.repository.checksum(previous_package) != prepared.expected_content_checksum:
                raise VersionConflict(self.repository.checksum(previous_package))
            previous_progress = self.repository.load(course_id, "content_progress")
            previous_review = self.repository.load(course_id, "content_review")
            step = self.catalog.steps_for_stage("content", mode=prepared.mode)[0]
            inputs: dict[str, dict[str, Any]] = {}
            for artifact_type in step.consumes:
                artifact = self.repository.require(course_id, artifact_type)
                if artifact.get("status") != "approved":
                    raise ValueError(
                        f"{artifact_type} must be approved before targeted Content repair"
                    )
                inputs[artifact_type] = artifact
            inputs["existing_content_package"] = previous_package
            produced = step.run(inputs, prepared.feedback)
            if set(produced) != {"content_package", "content_progress"}:
                raise ValueError("Content repair step produced an unexpected artifact set")
            package = deepcopy(produced["content_package"])
            progress = deepcopy(produced["content_progress"])
            self._validate_artifact(course_id, "content_package", package)
            self._validate_artifact(course_id, "content_progress", progress)
            issues = validate_json_schema(package, self.content_schema)
            if issues:
                detail = "; ".join(f"{issue['path']}: {issue['message']}" for issue in issues[:12])
                raise ValueError(f"repaired Content Package is invalid: {detail}")
            changed_ids, preserved_ids = self._validate_scope(
                previous_package,
                package,
                expected_ids=prepared.asset_ids,
            )
            progress["body"] = {
                "stage": "student_content",
                "current": None,
                "units": [
                    {
                        "stage": "student_content",
                        "subtopic_id": prepared.subtopic_id,
                        "asset_type": "targeted_repair",
                        "asset_id": asset_id,
                        "status": "completed",
                        "attempts": 1,
                        "error": None,
                    }
                    for asset_id in changed_ids
                ],
                "totals": {"completed": len(changed_ids)},
                "expected_asset_count": len(changed_ids),
                "completed_asset_count": len(changed_ids),
                "complete": True,
            }
            review = content_review.build_content_review_artifact(
                package,
                existing_review=previous_review,
            )
            note = prepared.instruction
            self._prepare_artifact(package, previous_package, status="draft", note=note)
            self._prepare_artifact(progress, previous_progress, status="draft", note=note)
            self._prepare_artifact(review, previous_review, status="approved", note=note)

            writes: list[tuple[dict[str, Any], str]] = [
                (package, self.repository.checksum(previous_package)),
                (
                    progress,
                    self.repository.checksum(previous_progress)
                    if previous_progress is not None
                    else "missing",
                ),
                (
                    review,
                    self.repository.checksum(previous_review)
                    if previous_review is not None
                    else "missing",
                ),
            ]
            if started_ledger is not None and prepared.source_repair_id is not None:
                completed_ledger = self.source_repairs.content_repair_completion(
                    started_ledger,
                    prepared.source_repair_id,
                    content_package=package,
                    changed_asset_ids=changed_ids,
                )
                writes.append((completed_ledger, self.repository.checksum(started_ledger)))
            writes.extend(
                self.invalidation.plan(
                    course_id,
                    {"content_package", "content_progress", "content_review"},
                    reason="Stale because targeted Content repair changed learner assets.",
                    transaction_outputs={
                        "content_package",
                        "content_progress",
                        "content_review",
                        "source_repair",
                    },
                    bounded_artifacts={"render_manifest", "run_summary"},
                )
            )
            persisted = self.repository.save_batch(writes)
            committed = True
            for asset_id in changed_ids:
                emit(
                    "unit.completed",
                    stage="content",
                    subtopic_id=prepared.subtopic_id,
                    asset_id=asset_id,
                    progress={
                        "completed": changed_ids.index(asset_id) + 1,
                        "expected": len(changed_ids),
                    },
                    message=f"{asset_id} regenerated and reverified",
                )
            blocker_total = sum(
                hard_verifier_blocker_count(asset) for asset in self._assets(package)[0].values()
            )
            emit(
                "content_repair.awaiting_review",
                strategy=prepared.strategy,
                asset_ids=changed_ids,
                hard_blocker_total=blocker_total,
                message="Targeted Content repair is ready for human review",
            )
            return {
                "strategy": prepared.strategy,
                "changed_asset_ids": changed_ids,
                "preserved_asset_ids": preserved_ids,
                "hard_blocker_total": blocker_total,
                "review_summary": review.get("body", {}).get("summary", {}),
                "artifact_types": [artifact["artifact_type"] for artifact in persisted],
                "source_repair_id": prepared.source_repair_id,
            }
        except Exception as exc:
            if (
                not committed
                and started_ledger is not None
                and prepared.source_repair_id is not None
            ):
                current = self.repository.require(course_id, "source_repair")
                self.source_repairs.fail_content_repair(
                    course_id,
                    prepared.source_repair_id,
                    expected_checksum=self.repository.checksum(current),
                    reason=_safe_error_message(exc),
                )
            raise

    @staticmethod
    def _classify_claim(claim: dict[str, Any]) -> tuple[str, str, str | None, bool]:
        support = claim.get("support")
        note = str(claim.get("note") or "").lower()
        source_id = claim.get("source_id")
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or support
            in {
                "ungrounded",
                "unattributed",
            }
        ):
            return (
                "missing_attribution",
                "The claim has no usable approved-source attribution.",
                "existing_evidence",
                True,
            )
        if support == "partial":
            return (
                "human_review",
                "The verifier found partial support; this remains visible for human judgment.",
                None,
                False,
            )
        if any(token in note for token in ("incorrect", "contradict", "out of scope")):
            return (
                "likely_content_error",
                "The verifier note indicates the learner-facing statement may need correction.",
                "existing_evidence",
                True,
            )
        if support == "unsupported":
            return (
                "insufficient_evidence",
                "The assigned approved source does not fully support the claim.",
                "better_evidence",
                True,
            )
        return (
            "likely_content_error",
            "The current verifier result requires a bounded rewrite and recheck.",
            "existing_evidence",
            True,
        )

    @staticmethod
    def _finding_projection(
        source_entries: list[dict[str, Any]],
        *,
        current_content_checksum: str,
        current_content_body_checksum: str,
        subtopic_id: str,
        asset_id: str,
        claim_id: str | None,
        finding_id: str,
        text: str,
        note: str,
        classification: str,
        reason: str,
        recommendation: str | None,
        blocking: bool,
    ) -> dict[str, Any]:
        source_entry = next(
            (
                entry
                for entry in reversed(source_entries)
                if entry.get("origin", {}).get("asset_id") == asset_id
                and entry.get("origin", {}).get("finding_id") == finding_id
                and ContentRepairService._source_entry_matches_content(
                    entry,
                    content_checksum=current_content_checksum,
                    content_body_checksum=current_content_body_checksum,
                )
            ),
            None,
        )
        return {
            "id": f"{asset_id}:{finding_id}",
            "subtopic_id": subtopic_id,
            "asset_id": asset_id,
            "claim_id": claim_id,
            "finding_id": finding_id,
            "text": text,
            "note": note,
            "classification": classification,
            "classification_reason": reason,
            "recommended_strategy": recommendation,
            "blocking": blocking,
            "state": source_entry.get("status") if source_entry else "ready",
            "source_repair_id": source_entry.get("id") if source_entry else None,
        }

    @staticmethod
    def _source_entry_matches_content(
        entry: dict[str, Any],
        *,
        content_checksum: str,
        content_body_checksum: str,
    ) -> bool:
        if entry.get("status") in {"awaiting_content_review", "resolved"}:
            result = entry.get("final_verifier_result")
            return (
                isinstance(result, dict)
                and result.get("content_body_checksum") == content_body_checksum
            )
        return entry.get("origin", {}).get("content_checksum") == content_checksum

    @staticmethod
    def _instruction(
        strategy: str,
        targets: list[dict[str, Any]],
        source_repair_id: str | None,
    ) -> str:
        named = []
        for target in targets:
            identifiers = [*target.get("claim_ids", []), *target.get("finding_ids", [])]
            suffix = f" ({', '.join(dict.fromkeys(identifiers))})" if identifiers else ""
            named.append(f"{target['asset_id']}{suffix}")
        evidence = (
            f"the newly approved exact route from Source Repair {source_repair_id}"
            if strategy == "better_evidence"
            else "only the currently routed approved evidence"
        )
        return (
            "Resolve the current verifier findings for "
            + ", ".join(named)
            + f" using {evidence}. Rewrite, narrow, remove, or correctly attribute "
            "unsupported statements, then reverify every named asset."
        )

    @staticmethod
    def _validate_target(asset: dict[str, Any], target: dict[str, Any]) -> None:
        claims = {
            str(claim.get("id")): claim
            for claim in asset.get("claims", [])
            if isinstance(claim, dict) and claim.get("id")
        }
        claim_ids = target.get("claim_ids", [])
        finding_ids = target.get("finding_ids", [])
        unknown_claims = sorted(set(claim_ids) - set(claims))
        if unknown_claims:
            raise ValueError("unknown Content repair claim(s): " + ", ".join(unknown_claims))
        unknown_findings = sorted(set(finding_ids) - set(claims))
        if unknown_findings:
            raise ValueError("unknown Content repair finding(s): " + ", ".join(unknown_findings))
        selected = set(claim_ids) | set(finding_ids)
        supported = sorted(
            claim_id
            for claim_id in selected
            if ContentRepairService._claim_is_supported_and_attributed(claims[claim_id])
        )
        if supported:
            raise ValueError(
                "Content repair cannot target supported claim(s): " + ", ".join(supported)
            )
        verification = asset.get("verification", {})
        unattributed = (
            verification.get("unattributed_found", []) if isinstance(verification, dict) else []
        )
        has_repairable = any(
            not ContentRepairService._claim_is_supported_and_attributed(claim)
            for claim in claims.values()
        ) or bool(unattributed)
        if not has_repairable:
            raise ValueError(
                f"asset {target['asset_id']!r} has no current verifier finding to repair"
            )

    @staticmethod
    def _claim_is_supported_and_attributed(claim: dict[str, Any]) -> bool:
        source_id = claim.get("source_id")
        return (
            claim.get("support") == "supported"
            and isinstance(source_id, str)
            and bool(source_id.strip())
        )

    @staticmethod
    def _assets(
        package: dict[str, Any],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        assets: dict[str, dict[str, Any]] = {}
        subtopics: dict[str, str] = {}
        count = 0
        for subtopic in package.get("body", {}).get("subtopics", []):
            if not isinstance(subtopic, dict):
                continue
            subtopic_id = str(subtopic.get("subtopic_id") or "")
            for asset in subtopic.get("assets", []):
                if not isinstance(asset, dict):
                    continue
                count += 1
                asset_id = asset.get("id")
                if not isinstance(asset_id, str) or not asset_id:
                    raise ValueError("Content Package contains a missing asset ID")
                if asset_id in assets:
                    raise ValueError("Content Package contains duplicate asset IDs")
                assets[asset_id] = asset
                subtopics[asset_id] = subtopic_id
        if count != len(assets):
            raise ValueError("Content Package contains invalid asset identities")
        return assets, subtopics

    def _validate_scope(
        self,
        previous: dict[str, Any],
        candidate: dict[str, Any],
        *,
        expected_ids: tuple[str, ...],
    ) -> tuple[list[str], list[str]]:
        before_assets, _ = self._assets(previous)
        after_assets, _ = self._assets(candidate)
        if set(before_assets) != set(after_assets):
            raise ValueError("Content repair changed the asset identity set")
        if self.repository.checksum(self._package_skeleton(previous)) != self.repository.checksum(
            self._package_skeleton(candidate)
        ):
            raise ValueError("Content repair changed data outside asset bodies")
        changed = sorted(
            asset_id
            for asset_id in before_assets
            if self.repository.checksum(before_assets[asset_id])
            != self.repository.checksum(after_assets[asset_id])
        )
        if not changed:
            raise NoOpRevision(
                "Content repair produced no content change; the prior artifacts were preserved"
            )
        if set(changed) != set(expected_ids):
            missing = sorted(set(expected_ids) - set(changed))
            outside = sorted(set(changed) - set(expected_ids))
            details = []
            if missing:
                details.append("unchanged requested assets: " + ", ".join(missing))
            if outside:
                details.append("out-of-scope assets: " + ", ".join(outside))
            raise ValueError("Content repair scope violation (" + "; ".join(details) + ")")
        return changed, sorted(set(before_assets) - set(changed))

    @staticmethod
    def _package_skeleton(package: dict[str, Any]) -> dict[str, Any]:
        skeleton = deepcopy(package.get("body", {}))
        for subtopic in skeleton.get("subtopics", []):
            if isinstance(subtopic, dict):
                subtopic["assets"] = [
                    asset.get("id")
                    for asset in subtopic.get("assets", [])
                    if isinstance(asset, dict)
                ]
        return skeleton

    @staticmethod
    def _prepare_artifact(
        artifact: dict[str, Any],
        existing: dict[str, Any] | None,
        *,
        status: str,
        note: str,
    ) -> None:
        artifact["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        artifact["revision_note"] = note
        artifact["status"] = status

    @staticmethod
    def _validate_artifact(
        course_id: str,
        artifact_type: str,
        artifact: dict[str, Any],
    ) -> None:
        if artifact.get("course_id") != course_id:
            raise ValueError(f"{artifact_type} output has the wrong course_id")
        if artifact.get("artifact_type") != artifact_type:
            raise ValueError(f"{artifact_type} output has the wrong artifact_type")
        if not isinstance(artifact.get("body"), dict):
            raise ValueError(f"{artifact_type} output body must be an object")

    def _writable(self, course_id: str) -> None:
        if self.repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
