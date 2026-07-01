"""Generality and bounded-context tests for the reusable generation path."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agents import student_content

GENERIC_PROMPTS = (
    "course_content.md",
    "learning_objectives.md",
    "summary.md",
    "case_study.md",
    "important_person.md",
    "did_you_know.md",
    "activities.md",
    "assessment.md",
    "resources.md",
)


def _coffee_inputs(tmp_path) -> dict:
    approved = tmp_path / "coffee_source.md"
    approved.write_text(
        "Curated evidence: water temperature and grind size affect extraction.",
        encoding="utf-8",
    )
    unrelated = tmp_path / "finance_source.md"
    unrelated.write_text(
        "UNRELATED SECRET CORPUS: derivatives and counterparty exposure.",
        encoding="utf-8",
    )
    course_model = {
        "course_id": "coffee-demo",
        "body": {
            "course_metadata": {
                "course_title": "Better Coffee at Home",
                "subject": "Coffee brewing",
                "audience_summary": "Curious home brewers",
                "level": "beginner",
                "language": "English",
                "jurisdiction": None,
                "course_outcome_ids": ["co1"],
            },
            "modules": [
                {
                    "id": "brew_m1",
                    "title": "Extraction Basics",
                    "context": {
                        "purpose": "Build a repeatable brewing foundation.",
                        "in_scope": ["grind", "water", "ratio"],
                        "out_of_scope": ["commercial roasting"],
                    },
                    "subtopics": [
                        {
                            "id": "brew_s1",
                            "title": "Dialling In a Pour-Over",
                            "context": {
                                "purpose": "Adjust variables based on taste.",
                                "in_scope": ["grind size", "water temperature"],
                                "out_of_scope": ["espresso pressure"],
                            },
                            "prerequisite_subtopic_ids": [],
                            "concepts": [],
                            "coverage_requirements": [
                                {
                                    "id": "brew_cr1",
                                    "statement": "Relate grind and temperature to extraction.",
                                    "concept_ids": [],
                                    "source_ids": ["g10"],
                                }
                            ],
                            "approved_source_ids": ["g10", "g11"],
                        },
                        {
                            "id": "brew_s2",
                            "title": "Milk Texture",
                            "context": {"purpose": "Introduce milk texture."},
                            "prerequisite_subtopic_ids": ["brew_s1"],
                            "concepts": [],
                            "coverage_requirements": [],
                            "approved_source_ids": ["g11"],
                        },
                    ],
                }
            ],
            "source_registry": [
                {
                    "id": "g10",
                    "title": "Coffee Brewing Control Notes",
                    "publisher": "Test Lab",
                    "source_type": "curated excerpt",
                    "locator": "https://example.test/coffee",
                    "content_ref": str(approved),
                },
                {
                    "id": "g11",
                    "title": "Unrelated Finance Notes",
                    "publisher": "Test Lab",
                    "source_type": "curated excerpt",
                    "locator": "https://example.test/finance",
                    "content_ref": str(unrelated),
                },
            ],
        },
    }
    blueprint = {
        "course_id": "coffee-demo",
        "body": {
            "subtopic_plans": [
                {
                    "subtopic_id": "brew_s1",
                    "depth_budget": {
                        "target_word_range": {"minimum": 5, "target": 8, "maximum": 20},
                        "expansion_policy": "targeted_by_coverage_gap",
                    },
                    "asset_plan": [
                        {
                            "id": "brew_s1_lesson",
                            "asset_type": "course_content",
                            "title": "Dialling In a Pour-Over",
                            "format": "markdown",
                            "selection_status": "selected",
                            "purpose": "Teach a practical adjustment loop.",
                            "source_ids": ["g10"],
                        },
                        {
                            "id": "brew_s1_quiz",
                            "asset_type": "assessment",
                            "title": "Taste Diagnosis Quiz",
                            "format": "markdown",
                            "selection_status": "rejected",
                            "purpose": "Optional knowledge check.",
                            "source_ids": ["g10"],
                        },
                    ],
                }
            ]
        },
    }
    return {
        "course_model": course_model,
        "blueprint": blueprint,
        "course_outcomes": {"body": {"outcomes": [{"id": "co1", "statement": "Brew."}]}},
        "subtopic_id": "brew_s1",
    }


def test_non_finance_context_is_dynamic_and_excludes_unassigned_sources(tmp_path) -> None:
    inputs = _coffee_inputs(tmp_path)
    selected = student_content.selected_asset_specs(inputs)
    assert [spec.asset_type for spec in selected] == ["course_content"]

    spec = student_content.resolve_asset_spec(selected[0], inputs)
    context = student_content._build_prompt_context(spec, inputs)
    prompt = student_content._render_prompt(spec, context, None, None)

    assert context["subject"] == "Coffee brewing"
    assert context["target_asset"]["id"] == "brew_s1_lesson"
    assert context["valid_source_ids"] == ["g10"]
    assert "water temperature and grind size" in prompt
    assert "UNRELATED SECRET CORPUS" not in prompt
    assert "Financial Risk Management" not in prompt


def test_depth_guard_retries_a_short_course_content_draft(tmp_path) -> None:
    inputs = _coffee_inputs(tmp_path)
    short = {"content": "Too short"}
    adequate = {"content": "Five useful words close the gap"}

    with patch.object(
        student_content,
        "generate_asset",
        side_effect=[short, adequate],
    ) as generate:
        result = student_content.generate_asset_to_depth(
            student_content.ASSET_SPECS["course_content"], inputs
        )

    assert result is adequate
    assert generate.call_count == 2
    assert "approved minimum is 5" in generate.call_args.kwargs["feedback"]


def test_depth_guard_fails_after_bounded_course_content_attempts(tmp_path) -> None:
    inputs = _coffee_inputs(tmp_path)
    short = {"content": "Still short"}

    with (
        patch.object(student_content, "generate_asset", return_value=short) as generate,
        pytest.raises(ValueError, match="still misses its approved depth budget"),
    ):
        student_content.generate_asset_to_depth(
            student_content.ASSET_SPECS["course_content"], inputs
        )

    assert generate.call_count == 3


def test_non_anchor_assets_do_not_inherit_course_content_word_floor(tmp_path) -> None:
    inputs = _coffee_inputs(tmp_path)
    requirements = student_content._asset_depth_requirements(
        student_content.ASSET_SPECS["summary"], inputs
    )
    assert "min_words" not in requirements


def test_reusable_prompts_contain_no_frm_fixture_facts() -> None:
    prompt_dir = student_content.REPO_ROOT / "prompts"
    banned = ("financial risk", "lehman", "frank knight", "chief risk officer", "cro role")
    for filename in GENERIC_PROMPTS:
        text = (prompt_dir / filename).read_text(encoding="utf-8").casefold()
        for phrase in banned:
            assert phrase not in text, f"{filename} leaks fixture phrase {phrase!r}"
