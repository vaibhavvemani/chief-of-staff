"""Deterministic source-selection reducer."""

from __future__ import annotations

from copy import deepcopy

from interaction import ChoiceOption, ChoicePrompt


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
