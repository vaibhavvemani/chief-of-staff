from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "WorkspacePage.tsx"
)
STAGE_VIEWS_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "StageViews.tsx"
)
NEW_COURSE_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "courses" / "NewCoursePage.tsx"
)
STAGE_SLUGS = (
    "brief",
    "outcomes",
    "research",
    "course-model",
    "blueprint",
    "content",
    "lesson-plan",
    "package",
)


def test_ui_implements_the_eight_stage_artifact_workspace() -> None:
    workspace = WORKSPACE_SOURCE.read_text(encoding="utf-8")
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert "workspace.stages.map" in workspace
    assert 'className="workflow-rail"' in workspace
    assert 'className="stage-canvas"' in workspace
    assert 'className="context-inspector"' in workspace
    assert 'className="decision-bar"' in workspace
    assert "ActivityDrawer" in workspace
    for slug in STAGE_SLUGS:
        assert f'case "{slug}"' in stage_views


def test_ui_uses_scoped_artifact_decisions_instead_of_a_generic_chat_surface() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (WORKSPACE_SOURCE, STAGE_VIEWS_SOURCE)
    ).lower()

    assert "guided revision" in source
    assert "briefeditdialog" in source
    assert "section-edit-button" in source
    assert "request scoped revision" in source
    assert "likely downstream impact" in source
    assert "content/reviews" not in source  # transport stays in the API client
    for forbidden in (
        "ask the agent anything",
        "chat interface",
        "chat-input",
        "message composer",
        "send message",
        "conversation history",
    ):
        assert forbidden not in source


def test_new_courses_start_live_with_visible_editable_defaults() -> None:
    source = NEW_COURSE_SOURCE.read_text(encoding="utf-8")

    assert 'useState<"deterministic" | "live">("live")' in source
    assert "3 hours of self-paced learning" in source
    assert 'level: "beginner"' in source
    assert 'modality: "self_paced"' in source
    assert 'language: "English"' in source
    assert "briefAnswers" in source
    assert "?mode=${mode}" in source


def test_stage_approval_advances_into_a_focused_agent_run_flow() -> None:
    source = WORKSPACE_SOURCE.read_text(encoding="utf-8")

    assert "nextStageAfter" in source
    assert "Continue to ${stageName(nextStage)}" in source
    assert "navigate(`/courses/${courseId}/${nextStage}?mode=${runMode}`)" in source
    assert "AgentRunScreen" in source
    assert "The agent is building {stageName(stage)}" in source
    assert "workspace.activeJob" in source
    assert "refetchInterval: activeJobId ? 1500 : false" in source


def test_research_requires_an_explicit_saved_source_selection() -> None:
    workspace = WORKSPACE_SOURCE.read_text(encoding="utf-8")
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert (
        'approvalBlocked={stage === "research" && !workspace.research.registrySaved}'
        in workspace
    )
    assert "Save source selection first" in workspace
    assert "Human checkpoint" in stage_views
    assert "Choose grounding sources" in stage_views
    assert "Save a selection before approving this stage" in stage_views


def test_course_model_uses_a_structured_hierarchy_and_detail_contract() -> None:
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert 'className="model-workspace"' in stage_views
    assert 'className="module-copy"' in stage_views
    assert 'className="tree-item-copy"' in stage_views
    assert '<dl className="model-metadata">' in stage_views
    assert 'className="model-scope-grid"' in stage_views
    assert 'className="model-record-list"' in stage_views
    assert 'className="model-integrity-note"' in stage_views


def test_blueprint_uses_readable_asset_plans_and_explicit_override_context() -> None:
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert 'function blueprintOverrides(' in stage_views
    assert 'className="blueprint-filter"' in stage_views
    assert 'className="blueprint-matrix"' in stage_views
    assert 'className="blueprint-plan-row"' in stage_views
    assert 'className="plan-budget"' in stage_views
    assert 'className="asset-plan-grid"' in stage_views
    assert "Required anchor" in stage_views
    assert "Not selected" in stage_views
