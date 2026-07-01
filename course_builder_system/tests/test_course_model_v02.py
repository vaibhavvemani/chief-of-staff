"""Contract and semantic tests for the domain-neutral v0.2 planning artifacts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from course_model_integrity import validate_course_model_semantics
from tests.schema_check import validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
MODEL_DIR = REPO_ROOT / "course_models"

ARTIFACTS = {
    "course_outcomes": "frm_demo.course_outcomes.json",
    "research_dossier": "frm_demo.research_dossier.json",
    "course_model": "frm_demo.course_model.json",
    "blueprint": "frm_demo.blueprint.json",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("artifact_type", ARTIFACTS)
def test_v02_planning_fixture_matches_schema(artifact_type: str):
    artifact = _load_json(MODEL_DIR / ARTIFACTS[artifact_type])
    schema = _load_json(SCHEMA_DIR / f"{artifact_type}.v0.2.schema.json")

    assert validate(artifact, schema) == []


def test_combined_course_model_cross_artifact_integrity():
    artifacts = {
        artifact_type: _load_json(MODEL_DIR / filename)
        for artifact_type, filename in ARTIFACTS.items()
    }

    assert validate_course_model_semantics(
        artifacts["course_model"],
        course_outcomes=artifacts["course_outcomes"],
        research_dossier=artifacts["research_dossier"],
        blueprint=artifacts["blueprint"],
    ) == []


def test_course_model_is_compact_and_contains_no_source_bodies():
    path = MODEL_DIR / ARTIFACTS["course_model"]
    course_model = _load_json(path)

    assert path.stat().st_size < 32_000
    assert validate_course_model_semantics(course_model) == []
    for source in course_model["body"]["source_registry"]:
        assert set(source) == {
            "id",
            "title",
            "publisher",
            "source_type",
            "locator",
            "content_ref",
        }
        assert (REPO_ROOT / source["content_ref"]).is_file()


def test_course_model_schema_is_not_tied_to_financial_risk():
    course_model = _load_json(MODEL_DIR / ARTIFACTS["course_model"])
    schema = _load_json(SCHEMA_DIR / "course_model.v0.2.schema.json")
    coffee_model = copy.deepcopy(course_model)
    coffee_model["course_id"] = "coffee-demo"
    metadata = coffee_model["body"]["course_metadata"]
    metadata["course_title"] = "Making Better Coffee at Home"
    metadata["subject"] = "Coffee making"
    metadata["audience_summary"] = "Curious beginners with a kettle and a grinder."
    metadata["level"] = "beginner"

    assert validate(coffee_model, schema) == []


def test_schema_rejects_wrong_artifact_identity_and_extra_fields():
    course_model = _load_json(MODEL_DIR / ARTIFACTS["course_model"])
    schema = _load_json(SCHEMA_DIR / "course_model.v0.2.schema.json")
    invalid = copy.deepcopy(course_model)
    invalid["artifact_type"] = "domain_model"
    invalid["body"]["source_text"] = "A source body must not be embedded here."

    errors = validate(invalid, schema)
    assert errors
    assert any("const" in error for error in errors)
    assert any("Additional property" in error for error in errors)


def test_semantics_reject_unresolved_sources_dependencies_and_bad_depth_range():
    course_model = _load_json(MODEL_DIR / ARTIFACTS["course_model"])
    blueprint = _load_json(MODEL_DIR / ARTIFACTS["blueprint"])
    invalid_model = copy.deepcopy(course_model)
    invalid_blueprint = copy.deepcopy(blueprint)

    focus = invalid_model["body"]["modules"][0]["subtopics"][0]
    focus["concepts"][0]["depends_on"] = ["missing_concept"]
    focus["coverage_requirements"][0]["source_ids"] = ["unapproved_source"]
    invalid_blueprint["body"]["subtopic_plans"][0]["depth_budget"]["target_word_range"] = {
        "minimum": 2500,
        "target": 2000,
        "maximum": 1500,
    }

    errors = validate_course_model_semantics(
        invalid_model,
        blueprint=invalid_blueprint,
    )
    assert any("unknown dependency" in error for error in errors)
    assert any("unapproved source" in error for error in errors)
    assert any("minimum <= target <= maximum" in error for error in errors)


def test_research_dossier_exposes_all_human_source_decisions():
    dossier = _load_json(MODEL_DIR / ARTIFACTS["research_dossier"])
    statuses = {candidate["status"] for candidate in dossier["body"]["source_candidates"]}

    assert statuses == {"proposed", "approved", "rejected"}
