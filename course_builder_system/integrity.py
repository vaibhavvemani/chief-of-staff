"""Course Builder cross-artifact referential-integrity checks.

The compact Course Model is the source of truth for hierarchy, compact concept
context, and the human-approved source registry. Blueprint, Content Package,
and Lesson Plan artifacts reference its ids instead of repeating that data.
Legacy TOC/Domain Model artifacts remain readable so historical runs can still
be inspected during the Phase 1 migration.

It reads only what is on disk via the orchestrator's loader, so it needs no
changes to orchestrator.py. The engine stays oblivious to body shapes; this
contract check lives outside it on purpose.

Checks performed:
  - Blueprint.allocations[].node_id        -> a TOC module OR subtopic id
  - Blueprint.dependencies[].module_id     -> a TOC module id
  - Blueprint.dependencies[].prerequisites -> TOC module ids
  - Blueprint.speakers[].placed_at         -> a TOC module OR subtopic id
  - Content Package.subtopics[].subtopic_id-> a TOC subtopic id
  - Content Package asset.sources[]        -> a Domain Model grounding-source id
  - Content Package v0.2 claims[].source_id-> a Domain Model grounding-source id
  - Content Package v0.2 asset.sources[]   -> non-null claims[].source_id union
  - Lesson Plan.sessions[].covers[].subtopic_id -> a TOC subtopic id
  - Domain Model.concepts[].depends_on     -> a Domain Model concept id
"""

from __future__ import annotations

from agents import lesson_plan as lesson_plan_agent
from course_model_integrity import validate_course_model_semantics
from orchestrator import load_artifact


def _course_model_ids(
    course_model_body: dict,
) -> tuple[set[str], set[str], set[str], dict[str, set[str]]]:
    """Return module, subtopic, source, and per-subtopic approved source ids."""
    modules: set[str] = set()
    subtopics: set[str] = set()
    approvals: dict[str, set[str]] = {}
    for module in course_model_body.get("modules", []):
        module_id = module.get("id")
        if isinstance(module_id, str):
            modules.add(module_id)
        for subtopic in module.get("subtopics", []):
            subtopic_id = subtopic.get("id")
            if isinstance(subtopic_id, str):
                subtopics.add(subtopic_id)
                approvals[subtopic_id] = set(subtopic.get("approved_source_ids", []))
    sources = {
        source["id"]
        for source in course_model_body.get("source_registry", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    return modules, subtopics, sources, approvals


def _check_course_model_integrity(course_id: str, course_model: dict) -> list[str]:
    """Validate the v0.2 Course Model graph and all downstream references."""
    outcomes = load_artifact(course_id, "course_outcomes")
    research = load_artifact(course_id, "research_dossier")
    source_registry = load_artifact(course_id, "approved_source_registry")
    blueprint = load_artifact(course_id, "blueprint")
    problems = validate_course_model_semantics(
        course_model,
        course_outcomes=outcomes,
        research_dossier=research,
        approved_source_registry=source_registry,
        blueprint=blueprint,
    )

    _, subtopic_ids, source_ids, approvals = _course_model_ids(course_model["body"])
    asset_routes: dict[tuple[str, str], set[str]] = {}
    selected_assets_by_subtopic: dict[str, set[str]] = {}
    if blueprint is not None:
        for plan in blueprint.get("body", {}).get("subtopic_plans", []):
            subtopic_id = plan.get("subtopic_id")
            for configured in plan.get("asset_plan", []):
                routed = set(configured.get("source_ids", []))
                for identity in (configured.get("id"), configured.get("asset_type")):
                    if isinstance(subtopic_id, str) and isinstance(identity, str):
                        asset_routes[(subtopic_id, identity)] = routed
                if (
                    isinstance(subtopic_id, str)
                    and isinstance(configured.get("id"), str)
                    and configured.get("selection_status") == "selected"
                ):
                    selected_assets_by_subtopic.setdefault(subtopic_id, set()).add(configured["id"])

    content_package = load_artifact(course_id, "content_package")
    if content_package is not None:
        is_v02 = content_package.get("schema_version") == "0.2"
        actual_content_subtopics = {
            subtopic.get("subtopic_id")
            for subtopic in content_package["body"].get("subtopics", [])
            if isinstance(subtopic.get("subtopic_id"), str)
        }
        if blueprint is not None:
            for subtopic_id in sorted(set(selected_assets_by_subtopic) - actual_content_subtopics):
                problems.append(
                    f"content_package: selected Blueprint subtopic '{subtopic_id}' is missing"
                )
        for subtopic in content_package["body"].get("subtopics", []):
            subtopic_id = subtopic.get("subtopic_id")
            if subtopic_id not in subtopic_ids:
                problems.append(
                    f"content_package: subtopic_id '{subtopic_id}' is not a Course Model subtopic"
                )
            if blueprint is not None:
                actual_asset_ids = {
                    asset.get("id")
                    for asset in subtopic.get("assets", [])
                    if isinstance(asset.get("id"), str)
                }
                expected_asset_ids = selected_assets_by_subtopic.get(subtopic_id, set())
                for asset_id in sorted(actual_asset_ids - expected_asset_ids):
                    problems.append(
                        f"content_package: asset '{asset_id}' was not selected by the Blueprint"
                    )
                for asset_id in sorted(expected_asset_ids - actual_asset_ids):
                    problems.append(
                        f"content_package: selected Blueprint asset '{asset_id}' is missing"
                    )
            approved_sources = approvals.get(subtopic_id, set())
            for asset in subtopic.get("assets", []):
                asset_sources = set(asset.get("sources", []))
                routed_sources = asset_routes.get(
                    (subtopic_id, asset.get("id")),
                    asset_routes.get((subtopic_id, asset.get("type")), approved_sources),
                )
                for source_id in sorted(asset_sources):
                    if source_id not in source_ids:
                        problems.append(
                            f"content_package: asset '{asset.get('id')}' source "
                            f"'{source_id}' is not registered in the Course Model"
                        )
                    elif source_id not in approved_sources:
                        problems.append(
                            f"content_package: asset '{asset.get('id')}' source "
                            f"'{source_id}' is not approved for '{subtopic_id}'"
                        )
                    elif source_id not in routed_sources:
                        problems.append(
                            f"content_package: asset '{asset.get('id')}' source "
                            f"'{source_id}' is not routed to that asset by the Blueprint"
                        )
                if not is_v02:
                    continue
                if "claims" not in asset:
                    problems.append(
                        f"content_package: v0.2 asset '{asset.get('id')}' is missing claims[]"
                    )
                    continue
                claim_sources: set[str] = set()
                for claim in asset.get("claims", []):
                    source_id = claim.get("source_id")
                    if source_id is None:
                        continue
                    claim_sources.add(source_id)
                    if source_id not in source_ids:
                        problems.append(
                            f"content_package: asset '{asset.get('id')}' claim "
                            f"'{claim.get('id')}' source_id '{source_id}' is not registered"
                        )
                    elif source_id not in approved_sources:
                        problems.append(
                            f"content_package: asset '{asset.get('id')}' claim "
                            f"'{claim.get('id')}' source_id '{source_id}' is not approved "
                            f"for '{subtopic_id}'"
                        )
                    elif source_id not in routed_sources:
                        problems.append(
                            f"content_package: asset '{asset.get('id')}' claim "
                            f"'{claim.get('id')}' source_id '{source_id}' is not routed "
                            "to that asset by the Blueprint"
                        )
                if asset_sources != claim_sources:
                    problems.append(
                        f"content_package: asset '{asset.get('id')}' sources "
                        f"{_source_list_label(asset_sources)} do not match claim source union "
                        f"{_source_list_label(claim_sources)}"
                    )

    lesson_plan = load_artifact(course_id, "lesson_plan")
    if lesson_plan is not None:
        expected_lesson_subtopics = []
        if content_package is not None and "session_constraints" in lesson_plan.get("body", {}):
            expected_lesson_subtopics = [
                subtopic.get("subtopic_id")
                for subtopic in content_package["body"].get("subtopics", [])
                if isinstance(subtopic.get("subtopic_id"), str)
            ]
            problems.extend(
                f"lesson_plan: {problem}"
                for problem in lesson_plan_agent.validate_lesson_plan_body(
                    lesson_plan["body"],
                    expected_subtopic_ids=expected_lesson_subtopics,
                )
            )
        for session in lesson_plan["body"].get("sessions", []):
            for coverage in session.get("covers", []):
                subtopic_id = coverage.get("subtopic_id")
                if subtopic_id not in subtopic_ids:
                    problems.append(
                        f"lesson_plan: session '{session.get('id')}' covers "
                        f"'{subtopic_id}' which is not a Course Model subtopic"
                    )
    return problems


def _toc_ids(toc_body: dict) -> tuple[set[str], set[str]]:
    """Return (module_ids, subtopic_ids) declared by the TOC."""
    modules: set[str] = set()
    subtopics: set[str] = set()
    for m in toc_body.get("modules", []):
        modules.add(m["id"])
        for s in m.get("subtopics", []):
            subtopics.add(s["id"])
    return modules, subtopics


def _source_list_label(source_ids: set[str]) -> str:
    return "[" + ", ".join(sorted(source_ids)) + "]"


def check_referential_integrity(course_id: str) -> list[str]:
    """Validate cross-artifact references for one course.

    Returns a list of human-readable problems; an empty list means every
    reference resolves. Artifacts not yet on disk are simply skipped, so this
    is safe to run mid-pipeline (after the TOC exists) or at the end.
    """
    course_model = load_artifact(course_id, "course_model")
    if course_model is not None:
        return _check_course_model_integrity(course_id, course_model)

    problems: list[str] = []

    toc = load_artifact(course_id, "toc")
    if toc is None:
        return [f"no TOC on disk for course '{course_id}' - cannot check references"]

    module_ids, subtopic_ids = _toc_ids(toc["body"])
    all_nodes = module_ids | subtopic_ids

    # Domain Model: build grounding/concept id universes; check concept graph.
    grounding_ids: set[str] = set()
    concept_ids: set[str] = set()
    dm = load_artifact(course_id, "domain_model")
    if dm is not None:
        for category in dm["body"].get("grounding_sources", []):
            for item in category.get("items", []):
                grounding_ids.add(item["id"])
        # Concepts can live at the body top level (Phase-0 shape) OR nested
        # under each subtopic (the hand-authored deep DM). Gather both so the
        # depends_on graph is checked regardless of which shape is on disk.
        all_concepts = list(dm["body"].get("concepts", []))
        for st in dm["body"].get("subtopics", []):
            all_concepts.extend(st.get("concepts", []))
        concept_ids = {c["id"] for c in all_concepts}
        for c in all_concepts:
            for dep in c.get("depends_on", []):
                if dep not in concept_ids:
                    problems.append(
                        f"domain_model: concept '{c['id']}' depends_on missing concept '{dep}'"
                    )

    # Blueprint references.
    bp = load_artifact(course_id, "blueprint")
    if bp is not None:
        for a in bp["body"].get("allocations", []):
            if a["node_id"] not in all_nodes:
                problems.append(f"blueprint: allocation node_id '{a['node_id']}' is not a TOC node")
        for dep in bp["body"].get("dependencies", []):
            if dep["module_id"] not in module_ids:
                problems.append(
                    f"blueprint: dependency module_id '{dep['module_id']}' is not a TOC module"
                )
            for pr in dep.get("prerequisites", []):
                if pr not in module_ids:
                    problems.append(f"blueprint: prerequisite '{pr}' is not a TOC module")
        for sp in bp["body"].get("speakers", []):
            if sp.get("placed_at") not in all_nodes:
                problems.append(
                    f"blueprint: speaker '{sp.get('id')}' placed_at "
                    f"'{sp.get('placed_at')}' is not a TOC node"
                )

    # Content Package references.
    cp = load_artifact(course_id, "content_package")
    if cp is not None:
        content_package_v02 = cp.get("schema_version") == "0.2"
        for st in cp["body"].get("subtopics", []):
            if st["subtopic_id"] not in subtopic_ids:
                problems.append(
                    f"content_package: subtopic_id '{st['subtopic_id']}' is not a TOC subtopic"
                )
            for asset in st.get("assets", []):
                asset_sources = set(asset.get("sources", []))
                for src in asset.get("sources", []):
                    if src not in grounding_ids:
                        problems.append(
                            f"content_package: asset '{asset['id']}' source "
                            f"'{src}' is not a Domain Model grounding id"
                        )
                if not content_package_v02:
                    continue

                if "claims" not in asset:
                    problems.append(
                        f"content_package: v0.2 asset '{asset['id']}' is missing claims[]"
                    )
                    continue

                claim_sources: set[str] = set()
                for claim in asset.get("claims", []):
                    src = claim.get("source_id")
                    if src is None:
                        continue
                    claim_sources.add(src)
                    if src not in grounding_ids:
                        problems.append(
                            f"content_package: asset '{asset['id']}' claim "
                            f"'{claim.get('id')}' source_id '{src}' is not a "
                            "Domain Model grounding id"
                        )

                if asset_sources != claim_sources:
                    problems.append(
                        f"content_package: asset '{asset['id']}' sources "
                        f"{_source_list_label(asset_sources)} do not match "
                        f"claim source union {_source_list_label(claim_sources)}"
                    )

    # Lesson Plan references.
    lp = load_artifact(course_id, "lesson_plan")
    if lp is not None:
        for sess in lp["body"].get("sessions", []):
            for cov in sess.get("covers", []):
                if cov["subtopic_id"] not in subtopic_ids:
                    problems.append(
                        f"lesson_plan: session '{sess.get('id')}' covers "
                        f"'{cov['subtopic_id']}' which is not a TOC subtopic"
                    )

    return problems


def report(course_id: str) -> bool:
    """Run the check and print a one-line verdict (plus any problems).

    Returns True if every reference resolves, False otherwise.
    """
    problems = check_referential_integrity(course_id)
    if problems:
        print(f"\n[integrity] FAIL - {len(problems)} dangling reference(s) in '{course_id}':")
        for p in problems:
            print(f"  - {p}")
        return False
    print(f"\n[integrity] OK - all cross-artifact references resolve for '{course_id}'")
    return True


if __name__ == "__main__":
    import sys

    cid = sys.argv[1] if len(sys.argv) > 1 else "frm-demo"
    ok = report(cid)
    raise SystemExit(0 if ok else 1)
