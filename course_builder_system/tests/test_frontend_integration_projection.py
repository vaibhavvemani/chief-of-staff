from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from api.services.artifact_repository import ArtifactRepository
from api.services.pipeline_catalog import PipelineCatalog
from api.services.workspace_projector import WorkspaceProjector

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_COURSE_ID = "coffee-live-main"
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


def _projector() -> WorkspaceProjector:
    return WorkspaceProjector(
        ArtifactRepository(repo_root=REPO_ROOT),
        PipelineCatalog(),
    )


def _source_ids(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"source_ids", "sources"} and isinstance(child, list):
                yield from (item for item in child if isinstance(item, str))
            elif key == "source_id" and isinstance(child, str):
                yield child
            else:
                yield from _source_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _source_ids(child)


def test_archived_live_blockers_override_historical_complete_summary() -> None:
    projector = _projector()
    stored_summary = projector.repository.require(LIVE_COURSE_ID, "run_summary")
    workspace = projector.project(LIVE_COURSE_ID)

    assert stored_summary["body"]["operator_status"] == "complete"
    assert workspace["operator_status"] == "requires_attention"
    assert workspace["attention"]["verification_totals"] == {
        "supported": 109,
        "partial": 14,
        "unsupported": 5,
        "ungrounded": 1,
        "unattributed": 3,
    }
    assert workspace["attention"]["blocking_total"] == 9
    stage_states = {stage["slug"]: stage["state"] for stage in workspace["stages"]}
    assert stage_states["content"] == "requires_attention"
    assert stage_states["package"] == "requires_attention"


def test_rejected_sources_do_not_leak_into_grounded_downstream_artifacts() -> None:
    repository = _projector().repository
    source_registry = repository.require(LIVE_COURSE_ID, "approved_source_registry")
    course_model = repository.require(LIVE_COURSE_ID, "course_model")
    blueprint = repository.require(LIVE_COURSE_ID, "blueprint")
    content_package = repository.require(LIVE_COURSE_ID, "content_package")

    decision = source_registry["body"]["decision"]
    rejected_ids = set(decision["rejected_ids"])
    approved_ids = {
        source["id"] for source in source_registry["body"]["source_registry"]
    }
    downstream_ids = set(_source_ids(course_model["body"]))
    downstream_ids.update(_source_ids(blueprint["body"]))
    downstream_ids.update(_source_ids(content_package["body"]))

    assert rejected_ids
    assert downstream_ids
    assert downstream_ids <= approved_ids
    assert downstream_ids.isdisjoint(rejected_ids)


def test_selected_assets_generated_assets_and_progress_units_reconcile() -> None:
    projector = _projector()
    repository = projector.repository
    blueprint = repository.require(LIVE_COURSE_ID, "blueprint")
    progress = repository.require(LIVE_COURSE_ID, "content_progress")["body"]

    selected_ids = {
        asset["id"]
        for plan in blueprint["body"]["subtopic_plans"]
        for asset in plan["asset_plan"]
        if asset["selection_status"] == "selected"
    }
    exposed_assets = projector.list_assets(LIVE_COURSE_ID)
    exposed_ids = {asset["id"] for asset in exposed_assets}
    progress_ids = {unit["asset_id"] for unit in progress["units"]}

    assert len(selected_ids) == 18
    assert exposed_ids == selected_ids == progress_ids
    assert progress["expected_asset_count"] == len(selected_ids)
    assert progress["completed_asset_count"] == len(selected_ids)
    assert progress["complete"] is True
    assert all(unit["status"] == "completed" for unit in progress["units"])


def test_targeted_content_asset_read_returns_only_requested_asset() -> None:
    projector = _projector()
    result = projector.asset(LIVE_COURSE_ID, "m1_s4_assess")

    assert result["id"] == "m1_s4_assess"
    assert result["subtopic_id"] == "m1_s4"
    assert result["asset"]["id"] == "m1_s4_assess"
    assert isinstance(result["asset"]["content"], str)
    assert result["asset"]["content"]
    assert result["verification"]["unsupported"] > 0
    assert result["requires_attention"] is True


def test_product_catalog_exposes_exactly_the_eight_workspace_stages() -> None:
    catalog = PipelineCatalog()

    assert tuple(stage.slug for stage in catalog.stages) == STAGE_SLUGS
    assert len({stage.slug for stage in catalog.stages}) == 8
