from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "WorkspacePage.tsx"
)
STAGE_VIEWS_SOURCE = (
    ROOT / "frontend" / "src" / "features" / "workspace" / "StageViews.tsx"
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

    assert "revision instruction" in source
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
