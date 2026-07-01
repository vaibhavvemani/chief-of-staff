"""Cross-artifact semantic checks for the v0.2 planning contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _find_cycle(nodes: set[str], dependencies: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in visiting:
            return path[path.index(node) :] + [node]
        if node in visited:
            return None
        visiting.add(node)
        for dependency in dependencies.get(node, []):
            if dependency in nodes:
                cycle = visit(dependency, [*path, dependency])
                if cycle:
                    return cycle
        visiting.remove(node)
        visited.add(node)
        return None

    for node in nodes:
        cycle = visit(node, [node])
        if cycle:
            return cycle
    return None


def _find_banned_source_text_fields(value: Any, path: str = "$") -> list[str]:
    """Ensure planning artifacts contain pointers to source bodies, not bodies."""
    banned = {"content", "excerpt", "full_text", "raw_text", "source_text"}
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in banned:
                errors.append(f"{child_path} embeds source/content text; store only content_ref")
            errors.extend(_find_banned_source_text_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_find_banned_source_text_fields(child, f"{path}[{index}]"))
    return errors


def validate_course_model_semantics(
    course_model: dict,
    *,
    course_outcomes: dict | None = None,
    research_dossier: dict | None = None,
    blueprint: dict | None = None,
) -> list[str]:
    """Validate references, dependency graphs, source approval, and plans.

    JSON Schema checks shape and primitive types. This function handles the
    relationships JSON Schema cannot express clearly without making the
    artifact contracts difficult to evolve.
    """
    errors: list[str] = []
    body = course_model.get("body", {})
    modules = body.get("modules", [])
    sources = body.get("source_registry", [])

    module_ids = [module.get("id") for module in modules]
    module_id_set = {value for value in module_ids if isinstance(value, str)}
    for duplicate in sorted(_duplicates(module_ids)):
        errors.append(f"Duplicate module id: {duplicate}")

    module_dependencies: dict[str, list[str]] = {}
    subtopics: list[dict] = []
    for module in modules:
        module_id = module.get("id")
        prerequisites = module.get("prerequisite_module_ids", [])
        module_dependencies[module_id] = prerequisites
        for prerequisite in prerequisites:
            if prerequisite not in module_id_set:
                errors.append(f"Module {module_id} has unknown prerequisite {prerequisite}")
            if prerequisite == module_id:
                errors.append(f"Module {module_id} cannot depend on itself")
        subtopics.extend(module.get("subtopics", []))

    module_cycle = _find_cycle(module_id_set, module_dependencies)
    if module_cycle:
        errors.append(f"Module dependency cycle: {' -> '.join(module_cycle)}")

    subtopic_ids = [subtopic.get("id") for subtopic in subtopics]
    subtopic_id_set = {value for value in subtopic_ids if isinstance(value, str)}
    for duplicate in sorted(_duplicates(subtopic_ids)):
        errors.append(f"Duplicate subtopic id: {duplicate}")

    source_ids = [source.get("id") for source in sources]
    source_id_set = {value for value in source_ids if isinstance(value, str)}
    for duplicate in sorted(_duplicates(source_ids)):
        errors.append(f"Duplicate source id: {duplicate}")

    concept_ids: list[str] = []
    concept_dependencies: dict[str, list[str]] = {}
    all_concepts: list[tuple[str, dict]] = []
    subtopic_dependencies: dict[str, list[str]] = {}
    for subtopic in subtopics:
        subtopic_id = subtopic.get("id")
        prerequisites = subtopic.get("prerequisite_subtopic_ids", [])
        subtopic_dependencies[subtopic_id] = prerequisites
        for prerequisite in prerequisites:
            if prerequisite not in subtopic_id_set:
                errors.append(f"Subtopic {subtopic_id} has unknown prerequisite {prerequisite}")
            if prerequisite == subtopic_id:
                errors.append(f"Subtopic {subtopic_id} cannot depend on itself")
        approved_ids = set(subtopic.get("approved_source_ids", []))
        unknown_approved = approved_ids - source_id_set
        for source_id in sorted(unknown_approved):
            errors.append(f"Subtopic {subtopic_id} approves unknown source {source_id}")

        local_concept_ids = {concept.get("id") for concept in subtopic.get("concepts", [])}
        for concept in subtopic.get("concepts", []):
            concept_id = concept.get("id")
            concept_ids.append(concept_id)
            concept_dependencies[concept_id] = concept.get("depends_on", [])
            all_concepts.append((subtopic_id, concept))
            for source_id in concept.get("source_ids", []):
                if source_id not in approved_ids:
                    errors.append(
                        f"Concept {concept_id} uses source {source_id} "
                        f"not approved for {subtopic_id}"
                    )

        coverage_ids = [item.get("id") for item in subtopic.get("coverage_requirements", [])]
        for duplicate in sorted(_duplicates(coverage_ids)):
            errors.append(f"Duplicate coverage requirement id in {subtopic_id}: {duplicate}")
        for requirement in subtopic.get("coverage_requirements", []):
            requirement_id = requirement.get("id")
            for concept_id in requirement.get("concept_ids", []):
                if concept_id not in local_concept_ids:
                    errors.append(
                        f"Coverage requirement {requirement_id} references "
                        f"unknown concept {concept_id}"
                    )
            for source_id in requirement.get("source_ids", []):
                if source_id not in approved_ids:
                    errors.append(
                        f"Coverage requirement {requirement_id} uses unapproved source {source_id}"
                    )

    for duplicate in sorted(_duplicates(concept_ids)):
        errors.append(f"Duplicate concept id: {duplicate}")
    concept_id_set = set(concept_ids)
    for subtopic_id, concept in all_concepts:
        concept_id = concept.get("id")
        for dependency in concept.get("depends_on", []):
            if dependency not in concept_id_set:
                errors.append(f"Concept {concept_id} has unknown dependency {dependency}")
            if dependency == concept_id:
                errors.append(f"Concept {concept_id} cannot depend on itself")
        if not concept.get("summary"):
            errors.append(f"Concept {concept_id} in {subtopic_id} must have a compact summary")

    subtopic_cycle = _find_cycle(subtopic_id_set, subtopic_dependencies)
    if subtopic_cycle:
        errors.append(f"Subtopic dependency cycle: {' -> '.join(subtopic_cycle)}")
    concept_cycle = _find_cycle(concept_id_set, concept_dependencies)
    if concept_cycle:
        errors.append(f"Concept dependency cycle: {' -> '.join(concept_cycle)}")

    errors.extend(_find_banned_source_text_fields(body))

    if course_outcomes is not None:
        if course_outcomes.get("course_id") != course_model.get("course_id"):
            errors.append("Course outcomes and course model course_id values differ")
        outcome_ids = {
            outcome.get("id") for outcome in course_outcomes.get("body", {}).get("outcomes", [])
        }
        for outcome_id in body.get("course_metadata", {}).get("course_outcome_ids", []):
            if outcome_id not in outcome_ids:
                errors.append(f"Course model references unknown course outcome {outcome_id}")

    if research_dossier is not None:
        if research_dossier.get("course_id") != course_model.get("course_id"):
            errors.append("Research dossier and course model course_id values differ")
        approved_candidate_ids = {
            candidate.get("id")
            for candidate in research_dossier.get("body", {}).get("source_candidates", [])
            if candidate.get("status") == "approved"
        }
        for source_id in sorted(source_id_set - approved_candidate_ids):
            errors.append(
                f"Course model source {source_id} is not approved in the research dossier"
            )
        for candidate in research_dossier.get("body", {}).get("source_candidates", []):
            for node_id in candidate.get("assigned_node_ids", []):
                if node_id not in module_id_set | subtopic_id_set:
                    errors.append(
                        f"Source candidate {candidate.get('id')} has unknown node {node_id}"
                    )

    if blueprint is not None:
        errors.extend(
            _validate_blueprint_semantics(
                blueprint,
                course_model,
                subtopic_id_set=subtopic_id_set,
                concept_id_set=concept_id_set,
            )
        )

    return errors


def _validate_blueprint_semantics(
    blueprint: dict,
    course_model: dict,
    *,
    subtopic_id_set: set[str],
    concept_id_set: set[str],
) -> list[str]:
    errors: list[str] = []
    if blueprint.get("course_id") != course_model.get("course_id"):
        errors.append("Blueprint and course model course_id values differ")

    plans = blueprint.get("body", {}).get("subtopic_plans", [])
    plan_ids = [plan.get("subtopic_id") for plan in plans]
    for duplicate in sorted(_duplicates(plan_ids)):
        errors.append(f"Duplicate Blueprint plan for subtopic {duplicate}")

    asset_ids: list[str] = []
    subtopic_approvals = {
        subtopic.get("id"): set(subtopic.get("approved_source_ids", []))
        for module in course_model.get("body", {}).get("modules", [])
        for subtopic in module.get("subtopics", [])
    }
    for plan in plans:
        subtopic_id = plan.get("subtopic_id")
        if subtopic_id not in subtopic_id_set:
            errors.append(f"Blueprint references unknown subtopic {subtopic_id}")
        budget = plan.get("depth_budget", {})
        word_range = budget.get("target_word_range", {})
        minimum = word_range.get("minimum", 0)
        target = word_range.get("target", 0)
        maximum = word_range.get("maximum", 0)
        if not minimum <= target <= maximum:
            errors.append(
                f"Blueprint word range for {subtopic_id} must satisfy minimum <= target <= maximum"
            )
        for concept_id in budget.get("required_concept_ids", []):
            if concept_id not in concept_id_set:
                errors.append(f"Blueprint {subtopic_id} requires unknown concept {concept_id}")
        assets = plan.get("asset_plan", [])
        if not any(asset.get("selection_status") == "selected" for asset in assets):
            errors.append(f"Blueprint {subtopic_id} must select at least one asset")
        if not any(
            asset.get("asset_type") == "course_content"
            and asset.get("selection_status") == "selected"
            for asset in assets
        ):
            errors.append(
                f"Blueprint {subtopic_id} must select course_content as its anchor"
            )
        asset_types = [asset.get("asset_type") for asset in assets]
        for duplicate in sorted(_duplicates(asset_types)):
            errors.append(
                f"Duplicate Blueprint asset type for {subtopic_id}: {duplicate}"
            )
        for asset in assets:
            for source_id in asset.get("source_ids", []):
                if source_id not in subtopic_approvals.get(subtopic_id, set()):
                    errors.append(
                        f"Blueprint asset {asset.get('id')} routes source {source_id} "
                        f"not approved for {subtopic_id}"
                    )
        asset_ids.extend(asset.get("id") for asset in assets)

    for duplicate in sorted(_duplicates(asset_ids)):
        errors.append(f"Duplicate Blueprint asset id: {duplicate}")
    return errors
