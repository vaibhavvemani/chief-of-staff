"""Deterministic source-selection reducer."""

from __future__ import annotations

from copy import deepcopy

from interaction import ChoiceOption, ChoicePrompt
from research_adapter import ResearchProvider
from source_store import SourceStore


def source_choice_prompt(research_dossier: dict) -> ChoicePrompt:
    candidates = research_dossier["body"]["source_candidates"]
    return ChoicePrompt(
        id="source_select",
        stage="research",
        target_artifact="research_dossier",
        question="Select the factual sources approved for downstream use.",
        mode="multi",
        min_selections=1,
        allow_custom=True,
        options=tuple(
            ChoiceOption(
                id=candidate["id"],
                label=candidate["title"],
                description=(f"{candidate['publisher']} - {candidate['relevance']}"),
                recommendation_rationale=candidate["trust_notes"],
                selected_by_default=candidate["status"] == "approved",
                metadata={
                    "content_ref": candidate.get("content_ref"),
                    "locator": candidate.get("locator"),
                    "status": candidate["status"],
                },
            )
            for candidate in candidates
            if candidate["status"] in {"proposed", "approved"}
        ),
    )


def apply_source_decision(
    research_dossier: dict,
    selected_ids: list[str] | tuple[str, ...],
    *,
    rationale: str = "Human source-selection checkpoint.",
) -> dict:
    """Set candidate source statuses from explicit selected ids."""
    selected = set(selected_ids)
    candidate_ids = {candidate["id"] for candidate in research_dossier["body"]["source_candidates"]}
    unknown = selected - candidate_ids
    if unknown:
        raise ValueError(f"cannot approve unknown source ids: {sorted(unknown)}")

    decided = deepcopy(research_dossier)
    approved_count = 0
    for candidate in decided["body"]["source_candidates"]:
        if candidate["id"] in selected:
            if not candidate.get("content_ref"):
                raise ValueError(
                    f"cannot approve source {candidate['id']!r} without stored content_ref"
                )
            candidate["status"] = "approved"
            candidate["decision_rationale"] = rationale
            approved_count += 1
        elif candidate["status"] == "proposed":
            candidate["status"] = "rejected"
            candidate["decision_rationale"] = "Rejected at the source-selection checkpoint."
    if approved_count == 0:
        raise ValueError("at least one source must be approved before downstream use")
    return decided


def recommended_source_ids(research_dossier: dict, *, max_sources: int = 2) -> tuple[str, ...]:
    """Return deterministic defaults for demos when no explicit selection exists."""
    approved = [
        candidate["id"]
        for candidate in research_dossier["body"]["source_candidates"]
        if candidate["status"] == "approved" and candidate.get("content_ref")
    ]
    if approved:
        return tuple(approved[:max_sources])
    proposed = [
        candidate["id"]
        for candidate in research_dossier["body"]["source_candidates"]
        if candidate["status"] == "proposed" and candidate.get("locator")
    ]
    return tuple(proposed[:max_sources])


def apply_source_capture_decision(
    research_dossier: dict,
    selected_ids: list[str] | tuple[str, ...],
    *,
    provider: ResearchProvider,
    store: SourceStore,
    rationale: str = "Human source-selection and capture checkpoint.",
) -> dict:
    """Approve selected source metadata, fetching/storing only approved bodies."""
    selected = set(selected_ids)
    candidate_ids = {candidate["id"] for candidate in research_dossier["body"]["source_candidates"]}
    unknown = selected - candidate_ids
    if unknown:
        raise ValueError(f"cannot approve unknown source ids: {sorted(unknown)}")

    decided = deepcopy(research_dossier)
    approved_count = 0
    for candidate in decided["body"]["source_candidates"]:
        if candidate["id"] in selected:
            content_ref = candidate.get("content_ref")
            if not content_ref:
                locator = candidate.get("locator")
                if not locator:
                    _reject_selected_source(
                        decided,
                        candidate,
                        reason="Selected source did not have a locator to fetch.",
                    )
                    continue
                fetched = provider.fetch(locator)
                if not fetched.ok or not fetched.content:
                    _reject_selected_source(
                        decided,
                        candidate,
                        reason=(
                            "Selected source could not be fetched or did not expose "
                            f"extractable text: {fetched.reason or 'no extractable content'}"
                        ),
                    )
                    continue
                stored = store.persist(
                    course_id=decided["course_id"],
                    source_id=candidate["id"],
                    content=fetched.content,
                    locator=locator,
                )
                content_ref = stored.content_ref
            elif not store.validate_content_ref(content_ref):
                _reject_selected_source(
                    decided,
                    candidate,
                    reason=f"Selected source content_ref is not readable: {content_ref}",
                )
                continue
            candidate["content_ref"] = content_ref
            candidate["status"] = "approved"
            candidate["decision_rationale"] = rationale
            approved_count += 1
        elif candidate["status"] == "proposed":
            candidate["status"] = "rejected"
            candidate["decision_rationale"] = "Rejected at the source-selection checkpoint."
    if approved_count == 0:
        raise ValueError("at least one source must be approved before downstream use")
    return decided


def _reject_selected_source(decided_dossier: dict, candidate: dict, *, reason: str) -> None:
    candidate["status"] = "rejected"
    candidate["decision_rationale"] = reason
    failures = decided_dossier["body"].setdefault("source_failures", [])
    failure_id = f"sf_{candidate['id']}"
    if any(failure.get("id") == failure_id for failure in failures):
        return
    failures.append(
        {
            "id": failure_id,
            "title": candidate["title"],
            "locator": candidate.get("locator"),
            "reason": reason,
        }
    )


def approved_source_registry(research_dossier: dict) -> list[dict]:
    """Return the downstream registry containing approved, available sources only."""
    registry: list[dict] = []
    for candidate in research_dossier["body"]["source_candidates"]:
        if candidate["status"] != "approved":
            continue
        content_ref = candidate.get("content_ref")
        if not content_ref:
            continue
        registry.append(
            {
                "id": candidate["id"],
                "title": candidate["title"],
                "publisher": candidate["publisher"],
                "source_type": candidate["source_type"],
                "locator": candidate["locator"],
                "content_ref": content_ref,
            }
        )
    return registry
