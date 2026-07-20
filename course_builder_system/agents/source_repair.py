"""Provider-neutral Source Repair artifact and deterministic research contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from agents.source_quality import project_source_quality
from orchestrator import make_artifact

SOURCE_REPAIR_SCHEMA_VERSION = "0.1"
SOURCE_REPAIR_STATES = frozenset(
    {
        "requested",
        "researching",
        "awaiting_source_decision",
        "awaiting_route_confirmation",
        "awaiting_content_repair",
        "regenerating",
        "awaiting_content_review",
        "resolved",
        "failed",
    }
)


@dataclass(frozen=True)
class RepairResearchScope:
    repair_id: str
    subtopic_id: str
    asset_id: str
    claim_id: str
    finding_id: str
    evidence_gap: str


@dataclass(frozen=True)
class RepairSourceCandidate:
    id: str
    title: str
    publisher: str
    source_type: str
    locator: str
    trust_notes: str
    relevance: str
    content: str | None
    fetch_reason: str | None = None


class SourceRepairProvider(Protocol):
    def research(
        self,
        scope: RepairResearchScope,
        *,
        limit: int,
    ) -> list[RepairSourceCandidate]: ...


class DeterministicSourceRepairProvider:
    """Synthetic bounded provider used only for deterministic contract evidence."""

    def research(
        self,
        scope: RepairResearchScope,
        *,
        limit: int,
    ) -> list[RepairSourceCandidate]:
        if limit < 1:
            return []
        digest = hashlib.sha256(
            f"{scope.subtopic_id}:{scope.asset_id}:{scope.claim_id}:{scope.evidence_gap}".encode()
        ).hexdigest()[:12]
        source_id = f"repair_src_{digest}"
        content = (
            f"# Focused evidence for {scope.subtopic_id}\n\n"
            f"Evidence need: {scope.evidence_gap}\n\n"
            "This deterministic passage exists to prove the bounded research, human "
            "decision, and route transaction contracts. It is not a live-source quality "
            "claim and must be replaced by the live provider before learner release.\n\n"
            f"The passage is scoped to asset {scope.asset_id} and claim {scope.claim_id}."
        )
        return [
            RepairSourceCandidate(
                id=source_id,
                title=f"Focused evidence for {scope.subtopic_id}",
                publisher="Deterministic Evidence Institute",
                source_type="deterministic evidence fixture",
                locator=f"https://evidence.example.test/{digest}",
                trust_notes=(
                    "Synthetic deterministic fixture for workflow evidence; live-source "
                    "authority still requires NC-912."
                ),
                relevance=f"Targets the evidence gap: {scope.evidence_gap}",
                content=content,
            )
        ][:limit]


def build_source_repair_artifact(course_id: str) -> dict[str, Any]:
    artifact = make_artifact(
        course_id,
        "source_repair",
        "source_repair",
        body={"next_repair_id": 1, "entries": []},
        inputs=[
            "research_dossier",
            "approved_source_registry",
            "course_model",
            "blueprint",
            "content_package",
        ],
        schema_version=SOURCE_REPAIR_SCHEMA_VERSION,
    )
    artifact["status"] = "approved"
    return artifact


def candidate_record(
    candidate: RepairSourceCandidate,
    *,
    evidence_gap: str,
    staged_content_ref: str | None,
) -> dict[str, Any]:
    projection = project_source_quality(
        {
            "id": candidate.id,
            "title": candidate.title,
            "publisher": candidate.publisher,
            "source_type": candidate.source_type,
            "locator": candidate.locator,
            "trust_notes": candidate.trust_notes,
            "relevance": candidate.relevance,
        },
        evidence_needs=[evidence_gap],
        content=candidate.content,
        fetch_reason=candidate.fetch_reason,
    )
    return {
        "id": candidate.id,
        "title": candidate.title,
        "publisher": candidate.publisher,
        "source_type": candidate.source_type,
        "locator": candidate.locator,
        "trust_notes": candidate.trust_notes,
        "relevance": candidate.relevance,
        "staged_content_ref": staged_content_ref,
        "fetch_status": "available" if candidate.content else "unavailable",
        "fetch_reason": candidate.fetch_reason,
        "quality": projection,
    }
