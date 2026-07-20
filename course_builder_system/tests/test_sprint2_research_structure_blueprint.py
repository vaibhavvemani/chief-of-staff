"""Sprint 2 research, Course Model, Blueprint, and resume tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import integrity
import orchestrator
import run
import steps
from agents import blueprint as blueprint_agent
from agents import course_model as course_model_agent
from agents import intake, research
from course_model_integrity import validate_course_model_semantics
from orchestrator import Decision, Step, artifact_path, make_artifact, run_pipeline
from research_adapter import BoundedLiveResearchProvider, coffee_mock_provider
from source_selection import (
    apply_source_capture_decision,
    approved_source_registry,
    recommended_source_ids,
)
from source_store import SourceStore
from tests.schema_check import validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
MODEL_DIR = REPO_ROOT / "course_models"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(body: dict, artifact_type: str) -> dict:
    return make_artifact(
        "coffee-demo",
        artifact_type,
        artifact_type,
        body=body,
        inputs=[],
        schema_version="0.2",
    )


def _coffee_research_artifact() -> dict:
    return research.build_research_dossier_artifact(
        _load_json(MODEL_DIR / "coffee_demo.brief.json"),
        _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json"),
        provider=coffee_mock_provider(),
    )


def _approved_registry_artifact(dossier: dict, tmp_path: Path) -> dict:
    selected = recommended_source_ids(dossier)
    decided = apply_source_capture_decision(
        dossier,
        selected,
        provider=coffee_mock_provider(),
        store=SourceStore(tmp_path / "source_store"),
    )
    return make_artifact(
        dossier["course_id"],
        "approved_source_registry",
        "source_selection",
        body={
            "source_registry": approved_source_registry(decided),
            "decision": {
                "selected_ids": list(selected),
                "rejected_ids": [
                    candidate["id"]
                    for candidate in decided["body"]["source_candidates"]
                    if candidate["status"] == "rejected"
                ],
            },
        },
        inputs=["research_dossier"],
        schema_version="0.2",
    )


def test_intake_gap_analysis_detects_ambiguity_and_conflicts() -> None:
    subject_request = intake.subject_request_artifact(subject="AI", course_id="ai-demo")
    answers = {
        "audience": "everyone",
        "level": "beginner",
        "prior_knowledge": "advanced professional machine learning",
        "in_scope": "model deployment, prompt design",
        "out_of_scope": "model deployment",
    }

    gaps = intake.analyze_intake_gaps(subject_request, answers)
    followups = intake.gap_followups(subject_request, answers, max_questions=99)

    assert {gap.kind for gap in gaps} == {"ambiguity", "conflict"}
    assert len(followups) <= 3
    assert all(question.id.startswith("brief_followup_") for question in followups)
    assert intake.INTAKE_FOLLOWUP_MODEL == "claude-haiku-4-5"


def test_live_provider_parses_search_html_fetches_html_and_pdf_text() -> None:
    def fetch_bytes(locator: str) -> tuple[int, dict[str, str], bytes]:
        if "search.test" in locator:
            return (
                200,
                {"content-type": "text/html"},
                b"""
                <html><body>
                  <a href="https://course.test/outline">Coffee Outline</a>
                </body></html>
                """,
            )
        if locator.endswith(".pdf"):
            return (
                200,
                {"content-type": "application/pdf"},
                b"%PDF visible fallback text about brewing ratios and grind control.",
            )
        return (
            200,
            {"content-type": "text/html"},
            b"""
            <html><body>
              <h1>Course outline</h1>
              <h2>Recipe basics</h2>
              <h2>Grind adjustment</h2>
              <h2>Water control</h2>
            </body></html>
            """,
        )

    provider = BoundedLiveResearchProvider(
        search_url_template="https://search.test/?q={query}",
        fetch_bytes=fetch_bytes,
    )

    results = provider.search("coffee course", limit=3)
    html_fetch = provider.fetch("https://course.test/outline")
    pdf_fetch = provider.fetch("https://course.test/file.pdf")
    outline = provider.extract_competitor_outline(results[0])

    assert results[0].locator == "https://course.test/outline"
    assert html_fetch.ok is True
    assert "Recipe basics" in html_fetch.content
    assert pdf_fetch.ok is True
    assert "brewing ratios" in pdf_fetch.content
    assert outline.outline_status == "usable"


def test_live_provider_retries_search_transport_failures() -> None:
    attempts = 0

    def fetch_bytes(locator: str) -> tuple[int, dict[str, str], bytes]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary search failure")
        return (
            200,
            {"content-type": "text/html"},
            b'<a href="https://course.test/outline">Course Outline</a>',
        )

    provider = BoundedLiveResearchProvider(
        search_url_template="https://search.test/?q={query}",
        max_retries=2,
        retry_backoff_s=0,
        fetch_bytes=fetch_bytes,
    )

    results = provider.search("bounded retry", limit=1)

    assert attempts == 3
    assert [result.locator for result in results] == ["https://course.test/outline"]


def test_live_provider_ids_are_stable_when_search_order_changes() -> None:
    pages = [
        b'<a href="https://course.test/alpha">Alpha</a>'
        b'<a href="https://course.test/beta">Beta</a>',
        b'<a href="https://course.test/beta">Beta</a>'
        b'<a href="https://course.test/alpha">Alpha</a>',
    ]

    def fetch_bytes(_locator: str) -> tuple[int, dict[str, str], bytes]:
        return 200, {"content-type": "text/html"}, pages.pop(0)

    provider = BoundedLiveResearchProvider(
        search_url_template="https://search.test/?q={query}",
        fetch_bytes=fetch_bytes,
    )

    first = {item.locator: item.id for item in provider.search("first", limit=2)}
    second = {item.locator: item.id for item in provider.search("second", limit=2)}

    assert first == second
    assert all(value.startswith("live_") and len(value) == 21 for value in first.values())


def test_live_provider_retries_transient_http_statuses_for_search_and_fetch() -> None:
    attempts: dict[str, int] = {"search": 0, "page": 0}

    def fetch_bytes(locator: str) -> tuple[int, dict[str, str], bytes]:
        key = "search" if "search.test" in locator else "page"
        attempts[key] += 1
        if attempts[key] == 1:
            return 503, {"content-type": "text/html"}, b"temporary"
        if key == "search":
            return (
                200,
                {"content-type": "text/html"},
                b'<a href="https://course.test/page">Course Page</a>',
            )
        return 200, {"content-type": "text/html"}, b"<p>Usable page evidence.</p>"

    provider = BoundedLiveResearchProvider(
        search_url_template="https://search.test/?q={query}",
        max_retries=1,
        retry_backoff_s=0,
        fetch_bytes=fetch_bytes,
    )

    results = provider.search("retry status", limit=1)
    fetched = provider.fetch(results[0].locator)

    assert attempts == {"search": 2, "page": 2}
    assert fetched.ok is True


def test_research_assembly_requires_three_outlines_and_defers_source_ingestion() -> None:
    dossier = _coffee_research_artifact()

    usable = [
        finding
        for finding in dossier["body"]["competitor_findings"]
        if finding["outline_status"] == "usable"
    ]
    candidates = {candidate["id"]: candidate for candidate in dossier["body"]["source_candidates"]}

    assert len(usable) >= 3
    assert candidates["coffee_g1"]["status"] == "proposed"
    assert candidates["coffee_g1"]["content_ref"] is None
    assert candidates["coffee_g3"]["status"] == "rejected"


def test_source_capture_ingests_only_selected_sources_and_rejects_the_rest(tmp_path) -> None:
    dossier = _coffee_research_artifact()
    selected = ("coffee_g1", "coffee_g2")

    decided = apply_source_capture_decision(
        dossier,
        selected,
        provider=coffee_mock_provider(),
        store=SourceStore(tmp_path / "source_store"),
    )
    registry = approved_source_registry(decided)
    statuses = {
        candidate["id"]: candidate["status"] for candidate in decided["body"]["source_candidates"]
    }

    assert [source["id"] for source in registry] == ["coffee_g1", "coffee_g2"]
    assert statuses["coffee_g4"] == "rejected"
    assert statuses["coffee_g3"] == "rejected"
    assert all(Path(source["content_ref"]).is_file() for source in registry)


def test_source_capture_records_selected_fetch_failure_but_keeps_successes(tmp_path) -> None:
    dossier = _coffee_research_artifact()
    for candidate in dossier["body"]["source_candidates"]:
        if candidate["id"] == "coffee_g2":
            candidate["locator"] = "https://example.test/missing-source"

    decided = apply_source_capture_decision(
        dossier,
        ("coffee_g1", "coffee_g2"),
        provider=coffee_mock_provider(),
        store=SourceStore(tmp_path / "source_store"),
    )
    registry = approved_source_registry(decided)
    statuses = {
        candidate["id"]: candidate["status"] for candidate in decided["body"]["source_candidates"]
    }

    assert [source["id"] for source in registry] == ["coffee_g1"]
    assert statuses["coffee_g2"] == "rejected"
    assert any(failure["id"] == "sf_coffee_g2" for failure in decided["body"]["source_failures"])


def test_source_selection_step_fails_atomically_when_any_selected_capture_fails(
    tmp_path,
    monkeypatch,
) -> None:
    dossier = _coffee_research_artifact()
    for candidate in dossier["body"]["source_candidates"]:
        if candidate["id"] == "coffee_g2":
            candidate["locator"] = "https://example.test/missing-source"
    monkeypatch.setattr(
        steps,
        "_provider_for_research",
        lambda _dossier: coffee_mock_provider(),
    )
    monkeypatch.setattr(steps, "course_dir", lambda _course_id: tmp_path / "course")

    with pytest.raises(ValueError, match="no source decision was saved.*coffee_g2"):
        steps.source_selection_step(
            {"research_dossier": dossier},
            "coffee_g1,coffee_g2",
        )


def test_generated_course_model_and_blueprint_match_schema_and_integrity(tmp_path) -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    outcomes = _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json")
    dossier = _coffee_research_artifact()
    registry_artifact = _approved_registry_artifact(dossier, tmp_path)

    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry_artifact,
    )
    blueprint = blueprint_agent.build_blueprint_artifact(course_model)
    course_schema = _load_json(SCHEMA_DIR / "course_model.v0.2.schema.json")
    blueprint_schema = _load_json(SCHEMA_DIR / "blueprint.v0.2.schema.json")

    assert validate(course_model, course_schema) == []
    assert validate(blueprint, blueprint_schema) == []
    assert (
        validate_course_model_semantics(
            course_model,
            course_outcomes=outcomes,
            research_dossier=dossier,
            approved_source_registry=registry_artifact,
            blueprint=blueprint,
        )
        == []
    )
    assert len(blueprint["body"]["subtopic_plans"]) >= 4
    first_assets = {
        asset["asset_type"]
        for asset in blueprint["body"]["subtopic_plans"][0]["asset_plan"]
        if asset["selection_status"] == "selected"
    }
    second_assets = {
        asset["asset_type"]
        for asset in blueprint["body"]["subtopic_plans"][1]["asset_plan"]
        if asset["selection_status"] == "selected"
    }
    assert first_assets != second_assets


def test_blueprint_decision_flow_supports_exceptions_and_requires_anchor_waiver(
    tmp_path,
) -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    outcomes = _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json")
    dossier = _coffee_research_artifact()
    registry_artifact = _approved_registry_artifact(dossier, tmp_path)
    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry_artifact,
    )
    blueprint = blueprint_agent.build_blueprint_artifact(course_model)

    with pytest.raises(ValueError, match="without an explicit anchor waiver"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types={"m1_s2": ["learning_objectives", "assessment"]},
        )

    decided = blueprint_agent.apply_blueprint_decision(
        blueprint,
        selected_asset_types={"m1_s2": ["learning_objectives", "course_content", "assessment"]},
        depth_overrides={
            "m1_s2": {
                "target_learning_minutes": 45,
                "target_word_range": {"minimum": 1800, "target": 2200, "maximum": 2600},
            }
        },
    )

    plan = next(
        item for item in decided["body"]["subtopic_plans"] if item["subtopic_id"] == "m1_s2"
    )
    selected_types = {
        asset["asset_type"]
        for asset in plan["asset_plan"]
        if asset["selection_status"] == "selected"
    }
    assert selected_types == {"learning_objectives", "course_content", "assessment"}
    assert plan["depth_budget"]["target_learning_minutes"] == 45
    assert len(decided["body"]["decision_log"]) >= 3


def test_blueprint_decision_applies_defaults_exceptions_and_authoritative_source_routes(
    tmp_path,
) -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    outcomes = _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json")
    dossier = _coffee_research_artifact()
    registry_artifact = _approved_registry_artifact(dossier, tmp_path)
    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry_artifact,
    )
    blueprint = blueprint_agent.build_blueprint_artifact(course_model)
    plans = blueprint["body"]["subtopic_plans"]
    first_id = plans[0]["subtopic_id"]
    second_id = plans[1]["subtopic_id"]
    source_ids = {
        subtopic["id"]: subtopic["approved_source_ids"]
        for module in course_model["body"]["modules"]
        for subtopic in module["subtopics"]
    }

    decided = blueprint_agent.apply_blueprint_decision(
        blueprint,
        default_asset_types=["course_content", "activities"],
        default_depth={"target_learning_minutes": 35, "required_example_count": 3},
        selected_asset_types={first_id: ["course_content", "assessment"]},
        depth_overrides={first_id: {"required_example_count": 5}},
        approved_source_ids_by_subtopic=source_ids,
        rationale="Use a practice-led course baseline.",
    )

    assert decided["body"]["course_defaults"]["default_asset_types"] == [
        "course_content",
        "activities",
    ]
    assert decided["body"]["course_defaults"]["depth_budget"][
        "target_learning_minutes"
    ] == 35
    first = next(
        plan for plan in decided["body"]["subtopic_plans"] if plan["subtopic_id"] == first_id
    )
    second = next(
        plan for plan in decided["body"]["subtopic_plans"] if plan["subtopic_id"] == second_id
    )
    assert {
        asset["asset_type"]
        for asset in first["asset_plan"]
        if asset["selection_status"] == "selected"
    } == {"course_content", "assessment"}
    assert {
        asset["asset_type"]
        for asset in second["asset_plan"]
        if asset["selection_status"] == "selected"
    } == {"course_content", "activities"}
    assert first["depth_budget"]["required_example_count"] == 5
    assert second["depth_budget"]["required_example_count"] == 3
    for plan in decided["body"]["subtopic_plans"]:
        for asset in plan["asset_plan"]:
            expected = (
                source_ids[plan["subtopic_id"]]
                if asset["selection_status"] == "selected"
                else []
            )
            assert asset["source_ids"] == expected


def test_blueprint_decision_rejects_invalid_ids_assets_depth_and_waivers(tmp_path) -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    outcomes = _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json")
    dossier = _coffee_research_artifact()
    registry_artifact = _approved_registry_artifact(dossier, tmp_path)
    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry_artifact,
    )
    blueprint = blueprint_agent.build_blueprint_artifact(course_model)
    subtopic_id = blueprint["body"]["subtopic_plans"][0]["subtopic_id"]

    with pytest.raises(ValueError, match="unknown subtopics"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types={"missing": ["course_content"]},
        )
    with pytest.raises(ValueError, match="unknown asset types"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types={subtopic_id: ["course_content", "video"]},
        )
    with pytest.raises(ValueError, match="selects no assets"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types={subtopic_id: []},
        )
    with pytest.raises(ValueError, match="minimum <= target <= maximum"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            depth_overrides={
                subtopic_id: {
                    "target_word_range": {"minimum": 900, "target": 700, "maximum": 800}
                }
            },
        )
    with pytest.raises(ValueError, match="without an explicit anchor waiver"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types={subtopic_id: ["assessment"]},
        )
    with pytest.raises(ValueError, match="while course_content remains selected"):
        blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types={subtopic_id: ["course_content", "assessment"]},
            anchor_waivers={subtopic_id},
        )

    waived = blueprint_agent.apply_blueprint_decision(
        blueprint,
        selected_asset_types={subtopic_id: ["assessment"]},
        anchor_waivers={subtopic_id},
    )
    plan = next(
        item for item in waived["body"]["subtopic_plans"] if item["subtopic_id"] == subtopic_id
    )
    assert plan["anchor_asset_waiver_confirmed"] is True


def test_integrity_rejects_rejected_source_leakage_and_unknown_outcome(tmp_path) -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    outcomes = _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json")
    dossier = _coffee_research_artifact()
    registry_artifact = _approved_registry_artifact(dossier, tmp_path)
    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry_artifact,
    )
    course_model["body"]["source_registry"].append(
        {
            "id": "coffee_g4",
            "title": "Rejected source",
            "publisher": "example.test",
            "source_type": "web page",
            "locator": "https://example.test/troubleshooting-chart",
            "content_ref": "sources/rejected.md",
        }
    )
    course_model["body"]["course_metadata"]["course_outcome_ids"].append("missing_outcome")

    errors = validate_course_model_semantics(
        course_model,
        course_outcomes=outcomes,
        research_dossier=dossier,
        approved_source_registry=registry_artifact,
    )

    assert any("not approved for downstream use" in error for error in errors)
    assert any("unknown course outcome" in error for error in errors)


def test_course_model_rationale_does_not_invent_research_topic_refs(tmp_path) -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    outcomes = _load_json(MODEL_DIR / "coffee_demo.course_outcomes.json")
    dossier = _coffee_research_artifact()
    dossier["body"]["normalized_topics"] = []
    dossier["body"]["common_core_topic_ids"] = []
    dossier["body"]["structural_implications"] = []
    registry_artifact = _approved_registry_artifact(dossier, tmp_path)

    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry_artifact,
    )

    assert course_model["body"]["structural_rationale"][0]["related_topic_ids"] == []
    assert (
        validate_course_model_semantics(
            course_model,
            course_outcomes=outcomes,
            research_dossier=dossier,
            approved_source_registry=registry_artifact,
        )
        == []
    )


def test_sprint2_pipeline_gate_with_mock_research(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "COURSES_DIR", tmp_path / "courses")
    subject_request = intake.subject_request_artifact(
        subject="Coffee making",
        description="A practical beginner course for better coffee at home.",
        course_id="coffee-demo",
    )

    run_pipeline(
        "coffee-demo",
        run.build_sprint2_pipeline(),
        {"subject_request": subject_request},
        approver=lambda _step, _produced: Decision(approved=True),
    )

    registry = orchestrator.load_artifact("coffee-demo", "approved_source_registry")
    course_model = orchestrator.load_artifact("coffee-demo", "course_model")
    blueprint = orchestrator.load_artifact("coffee-demo", "blueprint")

    assert registry is not None
    assert registry["body"]["decision"]["selected_ids"] == ["coffee_g1", "coffee_g2"]
    assert "coffee_g4" in registry["body"]["decision"]["rejected_ids"]
    assert course_model is not None
    assert blueprint is not None
    assert integrity.check_referential_integrity("coffee-demo") == []


def test_resume_reruns_stale_downstream_without_losing_upstream_approval(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(orchestrator, "COURSES_DIR", tmp_path / "courses")
    counts = {"one": 0, "two": 0}
    seed = make_artifact("resume-demo", "seed", "human", {"value": "seed"}, inputs=[])

    def step_one(inputs: dict, feedback: str | None) -> dict:
        counts["one"] += 1
        return {
            "one": make_artifact(
                "resume-demo",
                "one",
                "one",
                {"value": counts["one"]},
                inputs=["seed"],
            )
        }

    def step_two(inputs: dict, feedback: str | None) -> dict:
        counts["two"] += 1
        return {
            "two": make_artifact(
                "resume-demo",
                "two",
                "two",
                {"value": counts["two"]},
                inputs=["one"],
            )
        }

    pipeline = [
        Step("one", ["seed"], ["one"], step_one),
        Step("two", ["one"], ["two"], step_two),
    ]

    run_pipeline(
        "resume-demo",
        pipeline,
        {"seed": seed},
        approver=lambda _step, _produced: Decision(approved=True),
    )
    one = orchestrator.load_artifact("resume-demo", "one")
    assert one is not None
    one["updated_at"] = "2999-01-01T00:00:00+00:00"
    artifact_path("resume-demo", "one").write_text(json.dumps(one, indent=2))

    run_pipeline(
        "resume-demo",
        pipeline,
        {"seed": seed},
        approver=lambda _step, _produced: Decision(approved=True),
    )

    assert counts["one"] == 1
    assert counts["two"] == 2
    assert orchestrator.load_artifact("resume-demo", "one")["status"] == "approved"
