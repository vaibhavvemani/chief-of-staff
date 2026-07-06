"""Sprint 1 research adapter, source store, and reducer tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import steps
from competitor_analysis import build_competitor_analysis, competitor_finding_from_outline
from interaction import ScriptedResponder
from research_adapter import coffee_mock_provider
from source_selection import apply_source_decision, approved_source_registry, source_choice_prompt
from source_store import MAX_SOURCE_EXCERPT_CHARS, SourceStore

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "course_models"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mock_research_provider_extracts_ordered_outlines_and_coverage_matrix() -> None:
    provider = coffee_mock_provider()
    results = provider.search("coffee brewing beginner course", limit=3)
    outlines = [provider.extract_competitor_outline(result) for result in results]
    findings = [
        competitor_finding_from_outline(outline)
        for outline in outlines
        if outline.outline_status in {"usable", "partial"}
    ]
    analysis = build_competitor_analysis(findings, outcome_ids=["co1", "co2"])

    assert [section["order"] for section in findings[0]["outline_sections"]] == [1, 2, 3, 4, 5]
    grind_row = next(
        row for row in analysis["coverage_matrix"] if row["normalized_topic_id"] == "nt_grind_size"
    )
    assert grind_row["competitor_course_ids"] == [
        "comp_barista",
        "comp_brewlab",
        "comp_homebrew",
    ]
    assert "nt_grind_size" in analysis["common_core_topic_ids"]


def test_mock_provider_represents_fetch_failures_explicitly() -> None:
    provider = coffee_mock_provider()

    result = provider.fetch("https://example.test/locked")

    assert result.ok is False
    assert result.reason


def test_source_store_persists_available_sources_and_records_unavailable(tmp_path) -> None:
    store = SourceStore(tmp_path / "source_store")
    stored = store.persist(
        course_id="coffee-demo",
        source_id="coffee_g1",
        content="Brewing evidence.",
        locator="https://example.test/coffee",
    )
    missing = store.unavailable(
        course_id="coffee-demo",
        source_id="coffee_missing",
        reason="PDF text could not be extracted.",
    )

    assert store.validate_content_ref(stored.content_ref) is True
    assert missing.status == "unavailable"
    assert store.validate_content_ref(missing.content_ref) is False
    with pytest.raises(ValueError, match="stable lowercase id"):
        store.persist(course_id="Coffee Demo", source_id="bad", content="x")


def test_source_store_bounds_large_live_source_excerpts(tmp_path) -> None:
    store = SourceStore(tmp_path / "source_store")
    raw = (" Important source fact.   \n\n" * 2_000) + "Tail that should not enter prompts."

    stored = store.persist(
        course_id="coffee-demo",
        source_id="large_source",
        content=raw,
        locator="https://example.test/large",
    )

    text = Path(stored.content_ref).read_text(encoding="utf-8")
    assert len(text) <= MAX_SOURCE_EXCERPT_CHARS
    assert "   " not in text
    assert text.startswith("Important source fact.")


def test_source_selection_reducer_excludes_rejected_and_merely_proposed_sources() -> None:
    dossier = _load_json(MODEL_DIR / "coffee_demo.research_dossier.json")
    prompt = source_choice_prompt(dossier)
    decision = ScriptedResponder(choices={"source_select": ["coffee_g1"]}).choose(prompt)

    decided = apply_source_decision(dossier, decision.selected_ids)
    registry = approved_source_registry(decided)

    statuses = {
        candidate["id"]: candidate["status"] for candidate in decided["body"]["source_candidates"]
    }
    assert statuses["coffee_g1"] == "approved"
    assert statuses["coffee_g2"] == "rejected"
    assert statuses["coffee_g3"] == "rejected"
    assert [source["id"] for source in registry] == ["coffee_g1"]


def test_source_selection_refuses_unknown_or_contentless_approval() -> None:
    dossier = _load_json(MODEL_DIR / "coffee_demo.research_dossier.json")

    with pytest.raises(ValueError, match="unknown source ids"):
        apply_source_decision(dossier, ["missing"])
    with pytest.raises(ValueError, match="without stored content_ref"):
        apply_source_decision(dossier, ["coffee_g3"])


def test_sprint1_steps_reach_mocked_source_registry_for_coffee() -> None:
    subject_request = _load_json(MODEL_DIR / "coffee_demo.subject_request.json")
    brief = steps.intake_step({"subject_request": subject_request}, None)["brief"]
    course_outcomes = steps.course_outcomes_step({"brief": brief}, None)["course_outcomes"]
    research = steps.research_step({"brief": brief, "course_outcomes": course_outcomes}, None)[
        "research_dossier"
    ]
    registry_artifact = steps.source_selection_step({"research_dossier": research}, None)[
        "approved_source_registry"
    ]

    assert registry_artifact["body"]["decision"]["selected_ids"] == ["coffee_g1"]
    assert [source["id"] for source in registry_artifact["body"]["source_registry"]] == [
        "coffee_g1"
    ]
