"""Sprint 1 interaction, intake, and outcomes tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agents import intake, outcomes
from interaction import ChoiceOption, ChoicePrompt, QuestionSpec, ScriptedResponder
from tests.schema_check import validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
MODEL_DIR = REPO_ROOT / "course_models"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("artifact_type", "fixture"),
    [
        ("subject_request", "coffee_demo.subject_request.json"),
        ("brief", "coffee_demo.brief.json"),
        ("course_outcomes", "coffee_demo.course_outcomes.json"),
        ("research_dossier", "coffee_demo.research_dossier.json"),
    ],
)
def test_sprint1_non_frm_fixtures_match_schema(artifact_type: str, fixture: str) -> None:
    artifact = _load_json(MODEL_DIR / fixture)
    schema = _load_json(SCHEMA_DIR / f"{artifact_type}.v0.2.schema.json")

    assert validate(artifact, schema) == []


def test_brief_schema_requires_assumptions_and_provenance() -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    schema = _load_json(SCHEMA_DIR / "brief.v0.2.schema.json")
    invalid = copy.deepcopy(brief)
    del invalid["body"]["provenance"]

    errors = validate(invalid, schema)

    assert errors
    assert any("provenance" in error for error in errors)


def test_typed_questions_validate_options_defaults_and_show_if() -> None:
    modality = QuestionSpec(
        id="modality",
        field="modality",
        prompt="Mode?",
        why="Testing.",
        answer_type="single_choice",
        options=("self_paced", "live"),
        default="self_paced",
    )
    live_only = QuestionSpec(
        id="live_time",
        field="live_teaching_constraints",
        prompt="Live time?",
        why="Testing.",
        answer_type="free_text",
        show_if={"modality": "live"},
    )

    assert modality.validate_answer("") == []
    assert modality.coerce_answer("") == "self_paced"
    assert modality.validate_answer("video") != []
    assert live_only.visible_for({"modality": "self_paced"}) is False
    assert live_only.visible_for({"modality": "live"}) is True


def test_choice_prompt_rejects_unknown_duplicate_and_too_few_selections() -> None:
    prompt = ChoicePrompt(
        id="sources",
        stage="research",
        target_artifact="research_dossier",
        question="Select sources",
        mode="multi",
        min_selections=1,
        options=(
            ChoiceOption(id="s1", label="One", description="First"),
            ChoiceOption(id="s2", label="Two", description="Second"),
        ),
    )

    assert prompt.validate_selection([]) != []
    assert prompt.validate_selection(["s1", "s1"]) != []
    assert prompt.validate_selection(["missing"]) != []
    assert prompt.decide(["s1"]).rejected_ids == ("s2",)


def test_scripted_intake_emits_schema_valid_brief_without_reasking_resolved_fields() -> None:
    subject_request = intake.subject_request_artifact(
        subject="Coffee making",
        description=None,
        constraints=["Use home equipment."],
        course_id="coffee-demo",
    )
    responder = ScriptedResponder(
        answers={
            "brief_audience": "Home brewers who want consistent cups.",
            "brief_prior_knowledge": "Can boil water and follow a recipe.",
            "brief_purpose": "Brew better coffee by adjusting one variable at a time.",
            "brief_level": "beginner",
            "brief_duration": "3 hours",
            "brief_modality": "self_paced",
            "brief_language": "English",
            "brief_in_scope": "grind size, water temperature, brew ratio",
            "brief_out_of_scope": "espresso repair, roasting",
            "brief_must_have_topics": "taste diagnosis",
            "brief_assessment_expectations": "short scenario checks",
        }
    )

    brief = intake.run_scripted_intake(subject_request, responder)
    questions_after = intake.visible_unresolved_questions(brief["body"])
    schema = _load_json(SCHEMA_DIR / "brief.v0.2.schema.json")

    assert validate(brief, schema) == []
    assert questions_after == []
    assert brief["body"]["constraints"] == ["Use home equipment."]
    assert brief["body"]["in_scope"] == [
        "grind size",
        "water temperature",
        "brew ratio",
    ]


def test_validated_followups_are_bounded_stage_safe_and_do_not_repeat_fields() -> None:
    proposed = [
        QuestionSpec(
            id="brief_followup_audience",
            field="audience",
            prompt="Repeat audience?",
            why="Should be rejected.",
            allow_agent_followup=True,
        ),
        QuestionSpec(
            id="brief_followup_purpose",
            field="purpose",
            prompt="Clarify purpose?",
            why="Allowed.",
            allow_agent_followup=True,
        ),
        QuestionSpec(
            id="other_stage_scope",
            field="prior_knowledge",
            prompt="Wrong stage id.",
            why="Rejected.",
            allow_agent_followup=True,
        ),
        QuestionSpec(
            id="brief_followup_level",
            field="level",
            prompt="Level?",
            why="Rejected because level is not agent-followup eligible.",
            allow_agent_followup=True,
        ),
    ]

    accepted = intake.validated_followups({"audience": "Beginners"}, proposed)

    assert [question.field for question in accepted] == ["purpose"]


def test_outcome_decisions_support_edit_add_reprioritize_and_block_empty() -> None:
    brief = _load_json(MODEL_DIR / "coffee_demo.brief.json")
    candidates = outcomes.draft_outcomes_from_brief(brief)

    approved = outcomes.apply_outcome_decision(
        candidates,
        ["co2", "co1"],
        edits={"co2": {"statement": "Apply a repeatable pour-over brewing workflow."}},
        additions=[
            {
                "id": "co5",
                "statement": "Create a personal brew log for future adjustments.",
                "cognitive_level": "create",
                "evidence": "Learner completes a usable brew log template.",
                "priority": "optional",
            }
        ],
        priority_order=["co5", "co1", "co2"],
    )

    assert [outcome["id"] for outcome in approved] == ["co5", "co1", "co2"]
    assert approved[-1]["statement"] == "Apply a repeatable pour-over brewing workflow."
    with pytest.raises(ValueError, match="research cannot start"):
        outcomes.apply_outcome_decision(candidates, [])
