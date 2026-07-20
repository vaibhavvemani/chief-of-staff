from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "WorkspacePage.tsx"
)
STAGE_VIEWS_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "StageViews.tsx"
)
COURSE_MODEL_EDITOR_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "CourseModelEditor.tsx"
)
BLUEPRINT_EDITOR_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "BlueprintEditor.tsx"
)
LESSON_PLAN_EDITOR_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "LessonPlanEditor.tsx"
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

    assert "scoped content revision" in source
    assert "briefeditdialog" in source
    assert "section-edit-button" in source
    assert "start scoped revision" in source
    assert "impactconfirmationdialog" in source
    assert "expectedchecksum" in source
    assert "targettype" in source
    assert "targetids" in source
    assert "content/reviews" not in source  # transport stays in the API client
    assert "requeststagechanges" not in source
    for forbidden in (
        "ask the agent anything",
        "chat interface",
        "chat-input",
        "message composer",
        "send message",
        "conversation history",
    ):
        assert forbidden not in source


def test_new_courses_start_live_with_sparse_guided_intake() -> None:
    source = NEW_COURSE_SOURCE.read_text(encoding="utf-8")

    assert 'useState<"deterministic" | "live">("live")' in source
    assert "Defaults stay unconfirmed until the next step" in source
    assert "accept each one explicitly or replace it" in source
    assert "briefAnswers" not in source
    assert "?mode=${mode}" in source


def test_stage_approval_advances_into_a_focused_agent_run_flow() -> None:
    source = WORKSPACE_SOURCE.read_text(encoding="utf-8")

    assert "nextStageAfter" not in source
    assert 'action.id === "continue" || action.id === "go_to_blocker"' in source
    assert "action.targetStage" in source
    assert "navigate(`/courses/${courseId}/${action.targetStage}?mode=${runMode}`)" in source
    assert "AgentRunScreen" in source
    assert "The agent is building {stageName(stage)}" in source
    assert "workspace.activeJob" in source
    assert "refetchInterval: activeJobId ? 1500 : false" in source


def test_research_requires_an_explicit_saved_source_selection() -> None:
    workspace = WORKSPACE_SOURCE.read_text(encoding="utf-8")
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert 'actionEnabled("source_decision")' in workspace
    assert 'candidate.id === "source_decision" && candidate.enabled' in workspace
    assert "approvalBlocked" not in workspace
    assert "Human checkpoint" in stage_views
    assert "Choose grounding sources" in stage_views
    assert "Save a selection before approving this stage" in stage_views


def test_course_model_uses_a_structured_hierarchy_and_detail_contract() -> None:
    editor = COURSE_MODEL_EDITOR_SOURCE.read_text(encoding="utf-8")

    assert 'className="model-workspace"' in editor
    assert 'className="model-tree"' in editor
    assert 'className="model-detail"' in editor
    assert 'className="course-model-edit-grid"' in editor
    assert 'aria-label="Editable Course Model hierarchy"' in editor
    assert 'className="operation-ledger"' in editor
    assert "Preview impact" in editor
    assert "Save Course Model draft" in editor


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


def test_blueprint_editor_exposes_typed_defaults_exceptions_and_reconciliation() -> None:
    editor = BLUEPRINT_EDITOR_SOURCE.read_text(encoding="utf-8")

    assert 'aria-label="Course default assets"' in editor
    assert 'aria-label="Blueprint subtopic exceptions"' in editor
    assert "Course Content anchor waiver" in editor
    assert "minimum ≤ target ≤ maximum" in editor
    assert "Added assets" in editor
    assert "Removed assets" in editor
    assert "Existing content that becomes stale" in editor
    assert "Save Blueprint draft" in editor
    assert 'role="dialog"' in editor


def test_student_content_has_pre_generation_and_structured_review_states() -> None:
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert 'className="content-empty-state"' in stage_views
    assert "No learner assets have been generated yet" in stage_views
    assert "Run Student Content" in stage_views
    assert "function verificationBreakdown(" in stage_views
    assert "function evidenceReviewTotal(" in stage_views
    assert 'className="content-toolbar"' in stage_views
    assert 'className="claim-list"' in stage_views
    assert "No blocking verification findings" in stage_views


def test_lesson_plan_uses_reviewable_sequence_and_real_coverage_state() -> None:
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")
    editor = LESSON_PLAN_EDITOR_SOURCE.read_text(encoding="utf-8")

    assert "lesson-plan-view" in stage_views
    assert "connected {sessionCount === 1 ? \"session\" : \"sessions\"}" in stage_views
    assert "teaching-sequence" in stage_views
    assert "const exactCoverage" in stage_views
    assert "Coverage needs review" in stage_views
    assert "Edit Lesson Plan" in stage_views
    assert 'aria-label="Maximum session hours"' in editor
    assert 'aria-label="Default delivery mode"' in editor
    assert "Session placement" in editor
    assert "move_segment" in editor
    assert "reorder_session" in editor
    assert "Affected-session preview" in editor
    assert "each exactly once" in editor
    assert "Save Lesson Plan draft" in editor
    assert 'role="dialog"' in editor
    assert "Use <strong>Request changes</strong> below" not in stage_views


def test_package_has_a_prebuild_state_and_selects_the_first_rendered_file() -> None:
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")
    api_client = (ROOT / "frontend" / "src" / "api" / "client.ts").read_text(
        encoding="utf-8"
    )

    assert "function flattenOutputFiles(" in stage_views
    assert "No rendered package yet" in stage_views
    assert "Use <strong>Run Package</strong>" in stage_views
    assert "setSelectedPath(markdownFiles[0].path)" in stage_views
    assert "selectedPath={selected?.path}" in stage_views
    assert "getOutputMarkdown" in stage_views
    assert "<ReactMarkdown skipHtml>" in stage_views
    assert 'integrityPassed: artifacts.has("render_manifest")' in api_client


def test_workspace_actions_and_reopen_are_backend_projected() -> None:
    workspace = WORKSPACE_SOURCE.read_text(encoding="utf-8")
    api_client = (ROOT / "frontend" / "src" / "api" / "client.ts").read_text(
        encoding="utf-8"
    )

    assert "currentSummary?.actions ?? []" in workspace
    assert "visibleActions.map((action)" in workspace
    assert "previewStageImpact" in workspace
    assert "impactChecksum: impactPreview.impactChecksum" in workspace
    assert "impact_acknowledged: true" in api_client
    assert "expected_impact_checksum" in api_client
    assert "/stages/${stage}/revisions" in api_client
    assert "/request-changes" not in api_client


def test_affected_workflow_has_only_registered_mutations() -> None:
    workspace = WORKSPACE_SOURCE.read_text(encoding="utf-8")
    stage_views = STAGE_VIEWS_SOURCE.read_text(encoding="utf-8")

    assert "Find better evidence" in stage_views
    assert 'candidate.id === "source_repair" && candidate.enabled' in workspace
    assert "requestSourceRepair" in workspace
    assert "confirmSourceRepairRoute" in workspace
    assert "requestStageChanges" not in workspace
    assert "Diagnostics by stage" in workspace
    assert "workspace.diagnostics.stages" in workspace
    assert "credentials, learner content" in workspace
    assert "getOutputMarkdown" in stage_views
    assert "Use <strong>Request changes</strong>" not in stage_views
