from __future__ import annotations

import copy
from pathlib import Path

import pytest

import acceptance
import course_renderer
import integrity
import orchestrator
import run
import steps
from agents import blueprint as blueprint_agent
from agents import course_model as course_model_agent
from agents import intake, research, student_content, whole_course
from course_model_integrity import validate_course_model_semantics
from orchestrator import Decision, PipelineCancelled, Step, run_pipeline
from research_adapter import CompetitorOutline, MockResearchProvider, SearchResult
from source_selection import (
    apply_source_capture_decision,
    approved_source_registry,
    recommended_source_ids,
)
from source_store import SourceStore
from tests.schema_check import validate_content_package


def _subject_request(course_id: str = "acceptance-coffee") -> dict:
    return intake.subject_request_artifact(
        subject="Coffee making",
        description="A practical beginner course for better home brewing.",
        constraints=["Keep the course compact for acceptance."],
        course_id=course_id,
    )


def _wrapped_pipeline(pipeline: list[Step], counts: dict[str, int]) -> list[Step]:
    wrapped = []
    for step in pipeline:

        def run_step(inputs: dict, feedback: str | None, *, current: Step = step) -> dict:
            counts[current.name] = counts.get(current.name, 0) + 1
            return current.run(inputs, feedback)

        wrapped.append(
            Step(
                name=step.name,
                consumes=step.consumes,
                produces=step.produces,
                run=run_step,
            )
        )
    return wrapped


def _load(course_id: str, artifact_type: str) -> dict:
    artifact = orchestrator.load_artifact(course_id, artifact_type)
    assert artifact is not None
    return artifact


def _find_asset(content_body: dict, *, asset_type: str) -> dict:
    for subtopic in content_body["subtopics"]:
        for asset in subtopic["assets"]:
            if asset["type"] == asset_type:
                return asset
    raise AssertionError(f"missing asset type {asset_type}")


def _changed_asset_ids(before: dict, after: dict) -> list[str]:
    changed = []
    before_assets = {
        asset["id"]: asset
        for subtopic in before["subtopics"]
        for asset in subtopic["assets"]
    }
    for subtopic in after["subtopics"]:
        for asset in subtopic["assets"]:
            if before_assets[asset["id"]] != asset:
                changed.append(asset["id"])
    return changed


def test_primary_acceptance_demo_produces_complete_course_folder_and_summary(
    tmp_path,
    monkeypatch,
) -> None:
    course_id = "acceptance-coffee"
    courses_dir = tmp_path / "courses"
    output_root = tmp_path / "rendered"
    monkeypatch.setattr(orchestrator, "COURSES_DIR", courses_dir)

    run_pipeline(
        course_id,
        run.build_sprint4_acceptance_pipeline(output_root=output_root),
        {"subject_request": _subject_request(course_id)},
        approver=run.auto_approver,
    )

    assert integrity.check_referential_integrity(course_id) == []
    content_package = _load(course_id, "content_package")
    content_progress = _load(course_id, "content_progress")
    render_manifest = _load(course_id, "render_manifest")
    run_summary = _load(course_id, "run_summary")

    assert validate_content_package(content_package) == []
    assert content_progress["body"]["complete"] is True
    assert run_summary["body"]["operator_status"] == "complete"
    assert run_summary["body"]["resume"]["safe_to_rerun"] is True
    assert run_summary["body"]["output_paths"]["lesson_plan"].endswith("lesson_plan.md")

    paths = render_manifest["body"]["paths"]
    for key in ("index", "course_overview", "source_index", "lesson_plan"):
        assert Path(paths[key]).is_file()
    asset_count = sum(
        len(subtopic["assets"]) for subtopic in content_package["body"]["subtopics"]
    )
    assert len(paths["assets"]) == asset_count
    assert all(Path(path).suffix == ".md" for path in paths["assets"].values())

    stale = output_root / course_id / "stale_asset.md"
    stale.write_text("stale", encoding="utf-8")
    rerendered = course_renderer.render_course_folder(
        course_id=course_id,
        course_model=_load(course_id, "course_model"),
        blueprint=_load(course_id, "blueprint"),
        content_package=content_package,
        lesson_plan=_load(course_id, "lesson_plan"),
        output_root=output_root,
    )
    assert stale.exists() is False
    assert rerendered == paths


def test_resume_after_cancel_and_targeted_revision_are_operator_safe(
    tmp_path,
    monkeypatch,
) -> None:
    course_id = "resume-acceptance"
    courses_dir = tmp_path / "courses"
    output_root = tmp_path / "rendered"
    monkeypatch.setattr(orchestrator, "COURSES_DIR", courses_dir)

    def cancel_at_structure(step_name: str, produced: dict) -> Decision:
        if step_name == "structure":
            raise PipelineCancelled(step_name)
        return Decision(approved=True)

    with pytest.raises(PipelineCancelled):
        run_pipeline(
            course_id,
            run.build_sprint4_acceptance_pipeline(output_root=output_root),
            {"subject_request": _subject_request(course_id)},
            approver=cancel_at_structure,
        )

    assert _load(course_id, "approved_source_registry")["status"] == "approved"
    assert _load(course_id, "course_model")["status"] == "draft"

    counts: dict[str, int] = {}
    run_pipeline(
        course_id,
        _wrapped_pipeline(
            run.build_sprint4_acceptance_pipeline(output_root=output_root),
            counts,
        ),
        {"subject_request": _subject_request(course_id)},
        approver=run.auto_approver,
    )

    assert "intake" not in counts
    assert "course_outcomes" not in counts
    assert "research" not in counts
    assert "source_selection" not in counts
    assert counts["structure"] == 1
    assert integrity.check_referential_integrity(course_id) == []

    original = copy.deepcopy(_load(course_id, "content_package")["body"])
    target = _find_asset(original, asset_type="summary")
    revise_step = steps.make_student_content_step(
        asset_generator=acceptance.deterministic_generate_asset,
        package_verifier=acceptance.deterministic_verify_content_package,
        asset_verifier=acceptance.deterministic_verify_asset,
    )
    revised_outputs = revise_step(
        {
            "course_model": _load(course_id, "course_model"),
            "blueprint": _load(course_id, "blueprint"),
            "course_outcomes": _load(course_id, "course_outcomes"),
        },
        f"{target['id']}: tighten the acceptance summary",
    )

    revised = revised_outputs["content_package"]["body"]
    assert _changed_asset_ids(original, revised) == [target["id"]]
    assert "Revision applied" in _find_asset(revised, asset_type="summary")["content"]
    assert revised_outputs["content_progress"]["body"]["complete"] is True


def test_second_topic_domain_neutral_smoke_uses_same_contracts(tmp_path) -> None:
    request = intake.subject_request_artifact(
        subject="Indoor herb gardening",
        description="Teach apartment renters to grow practical kitchen herbs indoors.",
        constraints=["Avoid outdoor garden beds."],
        course_id="herb-smoke",
    )
    brief = intake.build_brief_artifact(
        request,
        {
            "audience": "Apartment renters with no gardening experience.",
            "prior_knowledge": "No plant-care experience assumed.",
            "purpose": "Grow and maintain kitchen herbs using indoor containers.",
            "in_scope": "light, watering, containers, pruning, pest prevention",
            "out_of_scope": "outdoor beds, commercial production",
            "must_have_topics": "basil, mint, parsley, small-space setup",
        },
    )
    outcomes = steps.course_outcomes_step({"brief": brief}, None)["course_outcomes"]
    dossier = research.build_research_dossier_artifact(
        brief,
        outcomes,
        provider=_herb_provider(),
    )
    selected = recommended_source_ids(dossier)
    decided = apply_source_capture_decision(
        dossier,
        selected,
        provider=_herb_provider(),
        store=SourceStore(tmp_path / "sources"),
    )
    registry = orchestrator.make_artifact(
        "herb-smoke",
        "approved_source_registry",
        "source_selection",
        {
            "source_registry": approved_source_registry(decided),
            "decision": {"selected_ids": list(selected), "rejected_ids": []},
        },
        inputs=["research_dossier"],
        schema_version="0.2",
    )
    course_model = course_model_agent.build_course_model_artifact(
        brief,
        outcomes,
        dossier,
        approved_source_registry=registry,
    )
    blueprint = blueprint_agent.build_blueprint_artifact(course_model)
    inputs = {
        "course_model": course_model,
        "blueprint": blueprint,
        "course_outcomes": outcomes,
    }
    targets = whole_course.planned_subtopic_ids(inputs)[:2]
    content_body, progress = whole_course.generate_content_package_body(
        inputs,
        target_subtopic_ids=targets,
        asset_generator=acceptance.deterministic_generate_asset,
    )
    content_body = acceptance.deterministic_verify_content_package(
        content_body,
        course_model,
        blueprint=blueprint,
    )
    lesson_plan = steps.lesson_plan_step(
        {
            "content_package": orchestrator.make_artifact(
                "herb-smoke",
                "content_package",
                "student_content",
                content_body,
                inputs=["course_model", "blueprint", "course_outcomes"],
                schema_version="0.2",
            ),
            "blueprint": blueprint,
            "course_model": course_model,
        },
        None,
    )["lesson_plan"]

    assert progress["complete"] is True
    assert 4 <= len(whole_course.planned_subtopic_ids(inputs)) <= 8
    whole_course.assert_exact_selected_assets(
        content_body,
        inputs,
        target_subtopic_ids=targets,
    )
    assert (
        validate_course_model_semantics(
            course_model,
            course_outcomes=outcomes,
            research_dossier=dossier,
            approved_source_registry=registry,
            blueprint=blueprint,
        )
        == []
    )
    covered = [
        cover["subtopic_id"]
        for session in lesson_plan["body"]["sessions"]
        for cover in session["covers"]
    ]
    assert covered == targets


def test_final_negative_paths_block_leakage_invalid_ids_and_evidence_gaps(
    tmp_path,
    monkeypatch,
) -> None:
    course_id = "negative-acceptance"
    monkeypatch.setattr(orchestrator, "COURSES_DIR", tmp_path / "courses")
    run_pipeline(
        course_id,
        run.build_sprint4_acceptance_pipeline(output_root=tmp_path / "rendered"),
        {"subject_request": _subject_request(course_id)},
        approver=run.auto_approver,
    )

    course_model = _load(course_id, "course_model")
    blueprint = _load(course_id, "blueprint")
    dossier = _load(course_id, "research_dossier")
    registry = _load(course_id, "approved_source_registry")
    outcomes = _load(course_id, "course_outcomes")
    content_package = _load(course_id, "content_package")

    leaked = copy.deepcopy(course_model)
    leaked["body"]["source_registry"].append(
        {
            "id": "comp_homebrew",
            "title": "Competitor outline masquerading as a source",
            "publisher": "example.test",
            "source_type": "competitor outline",
            "locator": "https://example.test/home-coffee",
            "content_ref": "courses/negative-acceptance/sources/comp_homebrew.md",
        }
    )
    leaked["body"]["modules"][0]["subtopics"][0]["approved_source_ids"].append("comp_homebrew")
    assert any(
        "not approved for downstream use" in error
        for error in validate_course_model_semantics(
            leaked,
            course_outcomes=outcomes,
            research_dossier=dossier,
            approved_source_registry=registry,
            blueprint=blueprint,
        )
    )

    invalid = copy.deepcopy(content_package)
    invalid["body"]["subtopics"][0]["assets"][0]["sources"] = ["Bad Source!"]
    assert validate_content_package(invalid) != []

    inputs = {"course_model": course_model, "blueprint": blueprint, "course_outcomes": outcomes}
    gap_blueprint = copy.deepcopy(blueprint)
    gap_blueprint["body"]["subtopic_plans"][0]["asset_plan"][0]["source_ids"] = []
    gap_inputs = {**inputs, "blueprint": gap_blueprint}
    body, progress = whole_course.generate_content_package_body(
        gap_inputs,
        target_subtopic_ids=[whole_course.planned_subtopic_ids(inputs)[0]],
        asset_generator=acceptance.deterministic_generate_asset,
    )
    assert any(unit["status"] == "evidence_gap" for unit in progress["units"])
    assert all(
        asset["id"] != gap_blueprint["body"]["subtopic_plans"][0]["asset_plan"][0]["id"]
        for subtopic in body["subtopics"]
        for asset in subtopic["assets"]
    )

    proposed = next(
        asset
        for asset in blueprint["body"]["subtopic_plans"][0]["asset_plan"]
        if asset["selection_status"] != "selected"
    )
    scoped = {**inputs, "subtopic_id": whole_course.planned_subtopic_ids(inputs)[0]}
    with pytest.raises(ValueError, match="did not select"):
        student_content.generate_asset(student_content.ASSET_SPECS[proposed["asset_type"]], scoped)


def _herb_provider() -> MockResearchProvider:
    results = [
        SearchResult(
            id="comp_windowsill",
            title="Windowsill Herb Curriculum",
            locator="https://herb.test/windowsill",
            snippet="Course outline covering light, containers, watering, pruning, and pests.",
        ),
        SearchResult(
            id="comp_apartment",
            title="Apartment Herb Workshop",
            locator="https://herb.test/apartment",
            snippet="Class outline for containers, basil, mint, watering, and harvesting.",
        ),
        SearchResult(
            id="comp_kitchen",
            title="Kitchen Herb Starter Outline",
            locator="https://herb.test/kitchen",
            snippet="Beginner curriculum for indoor light, soil, pruning, and pest checks.",
        ),
        SearchResult(
            id="herb_g1",
            title="Indoor Herb Care Reference",
            locator="https://herb.test/care",
            snippet="Evidence on light, watering, containers, pruning, and harvesting herbs.",
        ),
        SearchResult(
            id="herb_g2",
            title="Container Herb Troubleshooting",
            locator="https://herb.test/troubleshooting",
            snippet="Evidence on common indoor herb problems, pests, and watering corrections.",
        ),
    ]
    outlines = {
        "comp_windowsill": CompetitorOutline(
            id="comp_windowsill",
            provider="Herb School",
            offering="Windowsill Herb Curriculum",
            locator="https://herb.test/windowsill",
            audience="Indoor beginners.",
            level="beginner",
            duration="2 hours",
            delivery_format="self-paced",
            assessment_approach="plant-care checklist",
            outline_status="usable",
            outline_labels=("Light", "Containers", "Watering", "Pruning", "Pests"),
        ),
        "comp_apartment": CompetitorOutline(
            id="comp_apartment",
            provider="Apartment Growers",
            offering="Apartment Herb Workshop",
            locator="https://herb.test/apartment",
            audience="Apartment renters.",
            level="beginner",
            duration="half day",
            delivery_format="workshop",
            assessment_approach="setup demonstration",
            outline_status="usable",
            outline_labels=("Containers", "Basil", "Mint", "Watering", "Harvesting"),
        ),
        "comp_kitchen": CompetitorOutline(
            id="comp_kitchen",
            provider="Kitchen Garden Lab",
            offering="Kitchen Herb Starter Outline",
            locator="https://herb.test/kitchen",
            audience="Home cooks.",
            level="beginner",
            duration="3 hours",
            delivery_format="self-paced",
            assessment_approach="care plan",
            outline_status="usable",
            outline_labels=("Indoor light", "Soil", "Pruning", "Pest checks"),
        ),
    }
    pages = {
        "https://herb.test/care": (
            "Indoor herbs need adequate light, drainage, steady watering, pruning, "
            "and harvesting to stay productive."
        ),
        "https://herb.test/troubleshooting": (
            "Yellow leaves, leggy growth, pests, and wilting can often be traced "
            "to light, watering, container, or airflow problems."
        ),
    }
    return MockResearchProvider(search_results=results, pages=pages, outlines=outlines)
