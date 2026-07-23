"""Student Content generation for Phase 1.

Course Content is the anchor asset. Other selected assets are generated from its
finished content, a compact Course Model slice, a Blueprint plan, and only the
approved sources assigned to the target subtopic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import llm
from source_store import prepare_source_excerpt

REPO_ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = REPO_ROOT / "courses"
DEFAULT_COURSE_MODEL_PATH = REPO_ROOT / "course_models" / "frm_demo.course_model.json"
DEFAULT_BLUEPRINT_PATH = REPO_ROOT / "course_models" / "frm_demo.blueprint.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "phase1" / "m1_s1"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "s2_3_course_content_asset.json"

GENERATION_SYSTEM = (
    "You are the Course Builder Student Content agent. Generate only grounded, "
    "schema-valid JSON for the requested asset."
)

EMPTY_VERIFICATION: dict[str, Any] = {
    "supported": 0,
    "partial": 0,
    "unsupported": 0,
    "ungrounded": 0,
    "unattributed_found": [],
    "checked_at": None,
}


# ---------------------------------------------------------------------------
# Asset specification registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssetSpec:
    """Per-asset identity and generation configuration."""

    asset_id: str  # ``{subtopic_id}`` template; resolved from the Course Model
    asset_type: str
    title: str
    format: str
    prompt_filename: str
    max_tokens: int
    has_solution: bool
    conditioned_on_course_content: bool


# Domain-agnostic asset catalog. Identity/title/format/token overrides and the
# selected subset come from Blueprint.subtopic_plans[].asset_plan.
ASSET_SPECS: dict[str, AssetSpec] = {
    "course_content": AssetSpec(
        asset_id="{subtopic_id}_cc",
        asset_type="course_content",
        title="Course Content",
        format="pptx",
        prompt_filename="course_content.md",
        max_tokens=12_000,
        has_solution=False,
        conditioned_on_course_content=False,
    ),
    "learning_objectives": AssetSpec(
        asset_id="{subtopic_id}_lo",
        asset_type="learning_objectives",
        title="Learning Objectives",
        format="docx",
        prompt_filename="learning_objectives.md",
        max_tokens=3_500,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "summary": AssetSpec(
        asset_id="{subtopic_id}_summary",
        asset_type="summary",
        title="Summary",
        format="docx",
        prompt_filename="summary.md",
        # Structured output carries both learner prose and a claim ledger; the
        # first live generic-path gate showed 4k can truncate valid summaries.
        max_tokens=7_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "case_study": AssetSpec(
        asset_id="{subtopic_id}_case",
        asset_type="case_study",
        title="Case Study",
        format="pptx",
        prompt_filename="case_study.md",
        max_tokens=8_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "assessment": AssetSpec(
        asset_id="{subtopic_id}_assess",
        asset_type="assessment",
        title="Assessment",
        format="pptx",
        # Assessment uniquely emits BOTH `content` (questions) and a full
        # `solution` answer key, so it needs more headroom than the other assets
        # (5_000 truncated a 10-question quiz + model answers during S2.6).
        prompt_filename="assessment.md",
        max_tokens=9_000,
        has_solution=True,
        conditioned_on_course_content=True,
    ),
    "important_person": AssetSpec(
        asset_id="{subtopic_id}_person",
        asset_type="important_person",
        title="Important Person",
        format="pptx",
        prompt_filename="important_person.md",
        max_tokens=6_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "did_you_know": AssetSpec(
        asset_id="{subtopic_id}_dyk",
        asset_type="did_you_know",
        title="Did You Know?",
        format="pptx",
        prompt_filename="did_you_know.md",
        max_tokens=6_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "activities": AssetSpec(
        asset_id="{subtopic_id}_activities",
        asset_type="activities",
        title="Activities",
        format="docx",
        prompt_filename="activities.md",
        max_tokens=7_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "resources": AssetSpec(
        asset_id="{subtopic_id}_resources",
        asset_type="resources",
        title="Additional Resources",
        format="docx",
        prompt_filename="resources.md",
        max_tokens=7_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
}

COURSE_CONTENT_SPEC = ASSET_SPECS["course_content"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def selected_asset_specs(inputs: dict[str, Any]) -> list[AssetSpec]:
    """Return the human-selected asset catalog entries in Blueprint order.

    A missing asset plan is accepted only for legacy Phase 1 fixtures and falls
    back to the full catalog. New Course Models must make the choice explicit.
    """
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")
    subtopic_id = _subtopic_id(inputs)
    plan = _find_blueprint_subtopic_plan(blueprint_body, subtopic_id)
    raw_assets = _raw_asset_plan(plan)
    if raw_assets is None:
        return list(ASSET_SPECS.values())

    selected: list[AssetSpec] = []
    seen: set[str] = set()
    for item in raw_assets:
        if not isinstance(item, dict):
            raise ValueError("Blueprint asset_plan entries must be objects")
        asset_type = item.get("asset_type", item.get("type"))
        if asset_type not in ASSET_SPECS:
            raise ValueError(f"Blueprint selects unknown asset type {asset_type!r}")
        selection_status = item.get("selection_status")
        if selection_status is not None and selection_status not in {
            "proposed",
            "selected",
            "rejected",
        }:
            raise ValueError(f"Blueprint asset {asset_type!r} has invalid selection_status")
        enabled = (
            selection_status == "selected"
            if selection_status is not None
            else item.get("selected", item.get("enabled", True))
        )
        if type(enabled) is not bool:
            raise ValueError(f"Blueprint asset {asset_type!r} selected flag must be boolean")
        if not enabled:
            continue
        if asset_type in seen:
            raise ValueError(f"Blueprint selects duplicate asset type {asset_type!r}")
        selected.append(ASSET_SPECS[asset_type])
        seen.add(asset_type)

    if "course_content" not in seen:
        raise ValueError("Blueprint asset_plan must select course_content as the anchor")
    return selected


def resolve_asset_spec(spec: AssetSpec, inputs: dict[str, Any]) -> AssetSpec:
    """Resolve generic catalog defaults with the target subtopic's Blueprint."""
    subtopic_id = _subtopic_id(inputs)
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")
    plan = _find_blueprint_subtopic_plan(blueprint_body, subtopic_id)
    configured = None
    for item in _raw_asset_plan(plan) or []:
        if isinstance(item, dict) and item.get("asset_type", item.get("type")) == spec.asset_type:
            configured = item
            break
    configured = configured or {}

    asset_id = configured.get("id") or spec.asset_id.format(subtopic_id=subtopic_id)
    title = configured.get("title") or spec.title
    asset_format = configured.get("format") or spec.format
    max_tokens = configured.get("max_tokens", spec.max_tokens)
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise ValueError(f"Blueprint asset {spec.asset_type!r} must have a valid id")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"Blueprint asset {spec.asset_type!r} must have a valid title")
    if not isinstance(asset_format, str) or not asset_format.strip():
        raise ValueError(f"Blueprint asset {spec.asset_type!r} must have a valid format")
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError(f"Blueprint asset {spec.asset_type!r} max_tokens must be positive")
    return replace(
        spec,
        asset_id=asset_id,
        title=title,
        format=asset_format,
        max_tokens=max_tokens,
    )


def ensure_asset_selected(spec: AssetSpec, inputs: dict[str, Any]) -> None:
    """Raise if the Blueprint did not select this asset for generation."""
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")
    plan = _find_blueprint_subtopic_plan(blueprint_body, _subtopic_id(inputs))
    raw_assets = _raw_asset_plan(plan)
    if raw_assets is None:
        return
    for item in raw_assets:
        if not isinstance(item, dict):
            continue
        if item.get("asset_type", item.get("type")) != spec.asset_type:
            continue
        if item.get("selection_status") == "selected" or (
            item.get("selection_status") is None and item.get("selected", item.get("enabled", True))
        ):
            return
        raise ValueError(f"Blueprint did not select asset type {spec.asset_type!r}")
    raise ValueError(f"Blueprint does not plan asset type {spec.asset_type!r}")


def routed_source_ids(spec: AssetSpec, inputs: dict[str, Any]) -> list[str]:
    """Return the approved source subset assigned to one asset."""
    ensure_asset_selected(spec, inputs)
    course_body = _artifact_body(inputs["course_model"], "course_model")
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")
    subtopic_id = _subtopic_id(inputs)
    _, focus_subtopic = _find_course_subtopic(course_body, subtopic_id)
    plan = _find_blueprint_subtopic_plan(blueprint_body, subtopic_id) or {}
    asset_plan = next(
        (
            item
            for item in _raw_asset_plan(plan) or []
            if isinstance(item, dict)
            and item.get("asset_type", item.get("type")) == spec.asset_type
        ),
        {},
    )
    approved = focus_subtopic.get("approved_source_ids")
    routed = asset_plan.get("source_ids", approved)
    if not isinstance(approved, list) or not all(isinstance(item, str) for item in approved):
        raise ValueError(f"Course Model {subtopic_id} approved_source_ids must be a string list")
    if not isinstance(routed, list) or not all(isinstance(item, str) for item in routed):
        raise ValueError(f"Blueprint asset {spec.asset_type!r} source_ids must be a string list")
    unapproved = sorted(set(routed) - set(approved))
    if unapproved:
        raise ValueError(
            f"Blueprint asset {spec.asset_type!r} routes sources not approved for "
            f"{subtopic_id}: {', '.join(unapproved)}"
        )
    return routed


def generate_asset(
    spec: AssetSpec,
    inputs: dict[str, Any],
    course_content: dict[str, Any] | None = None,
    feedback: str | None = None,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Generate one v0.2 asset according to *spec*.

    For assets with ``spec.conditioned_on_course_content=True`` the caller
    must supply the already-generated Course Content dict as *course_content*.
    For the anchor asset itself, pass ``course_content=None``.

    Returns the validated, normalised asset dict.
    """
    spec = resolve_asset_spec(spec, inputs)
    ensure_asset_selected(spec, inputs)
    context = _build_prompt_context(spec, inputs)
    prompt = _render_prompt(spec, context, course_content, feedback)
    schema = _build_asset_schema(spec)

    result = llm.call(
        [{"role": "user", "content": prompt}],
        system=GENERATION_SYSTEM,
        model=model,
        max_tokens=spec.max_tokens,
        schema=schema,
        use_cache=use_cache,
        call_role="content_generation",
    )

    asset = result.parsed
    if asset is None:
        asset = json.loads(result.text)
    if not isinstance(asset, dict):
        raise ValueError(f"{spec.asset_type} generation returned a non-object JSON value")

    return _validate_and_normalize_asset(spec, asset, set(context["valid_source_ids"]))


def generate_asset_to_depth(
    spec: AssetSpec,
    inputs: dict[str, Any],
    course_content: dict[str, Any] | None = None,
    feedback: str | None = None,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Generate with a bounded, Blueprint-driven mechanical depth check.

    Word counts are guardrails, not the quality definition. Semantic coverage
    remains the verifier/evaluator's job; this loop only catches clearly short
    drafts or missing explicitly required sections.
    """
    requirements = _asset_depth_requirements(spec, inputs)
    attempts = requirements.get("max_generation_attempts", 1)
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("max_generation_attempts must be an integer from 1 to 3")

    asset = generate_asset(
        spec,
        inputs,
        course_content=course_content,
        feedback=feedback,
        model=model,
        use_cache=use_cache,
    )
    for _ in range(1, attempts):
        shortfalls = _depth_shortfalls(asset, requirements)
        if not shortfalls:
            break
        revision_feedback = (
            "The previous draft missed its approved depth budget:\n- "
            + "\n- ".join(shortfalls)
            + "\nRegenerate a focused, grounded draft that closes these gaps without padding."
        )
        if feedback:
            revision_feedback = f"{feedback}\n\n{revision_feedback}"
        asset = generate_asset(
            spec,
            inputs,
            course_content=course_content,
            feedback=revision_feedback,
            model=model,
            use_cache=use_cache,
        )
    final_shortfalls = _depth_shortfalls(asset, requirements)
    if final_shortfalls:
        raise ValueError(
            f"{spec.asset_type} still misses its approved depth budget after "
            f"{attempts} attempt(s):\n- " + "\n- ".join(final_shortfalls)
        )
    return asset


def generate_course_content(
    inputs: dict[str, Any],
    feedback: str | None = None,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Thin wrapper kept for backward compatibility with S2.3 callers.

    Delegates to :func:`generate_asset` with the Course Content spec.
    The returned shape is identical to the pre-S2.4 implementation.
    """
    return generate_asset(
        COURSE_CONTENT_SPEC,
        inputs,
        course_content=None,
        feedback=feedback,
        model=model,
        use_cache=use_cache,
    )


def load_generation_inputs(
    course_id: str,
    course_model_path: Path = DEFAULT_COURSE_MODEL_PATH,
    blueprint_path: Path | None = None,
    subtopic_id: str = "m1_s1",
) -> dict[str, Any]:
    """Load CLI inputs without mutating any course artifacts."""
    course_dir = COURSES_DIR / course_id
    if blueprint_path is None:
        candidate = course_dir / "blueprint.json"
        if candidate.exists():
            candidate_artifact = _load_json(candidate)
            blueprint_path = (
                candidate
                if candidate_artifact.get("schema_version") == "0.2"
                else DEFAULT_BLUEPRINT_PATH
            )
        else:
            blueprint_path = DEFAULT_BLUEPRINT_PATH
    return {
        "course_model": _load_json(course_model_path),
        "blueprint": _load_json(blueprint_path),
        "subtopic_id": subtopic_id,
    }


# ---------------------------------------------------------------------------
# Prompt context construction
# ---------------------------------------------------------------------------


def _build_prompt_context(spec: AssetSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    course_model = inputs["course_model"]
    course_body = _artifact_body(course_model, "course_model")
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")

    subtopic_id = _subtopic_id(inputs)
    module, focus_subtopic = _find_course_subtopic(course_body, subtopic_id)
    allocation = _find_blueprint_allocation(blueprint_body, subtopic_id)
    subtopic_plan = _find_blueprint_subtopic_plan(blueprint_body, subtopic_id) or {}
    asset_plan = next(
        (
            item
            for item in _raw_asset_plan(subtopic_plan) or []
            if isinstance(item, dict)
            and item.get("asset_type", item.get("type")) == spec.asset_type
        ),
        {},
    )
    source_registry = _load_registered_sources(course_body, routed_source_ids(spec, inputs))

    sibling_subtopics = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "context": item.get("context"),
            "depth": item.get("depth"),
        }
        for item in module.get("subtopics", [])
        if item.get("id") != subtopic_id
    ]

    return {
        "course_id": course_model.get("course_id"),
        "subject": course_body.get("course_metadata", {}).get(
            "subject", course_body.get("subject")
        ),
        "course_title": course_body.get("course_metadata", {}).get(
            "course_title", course_body.get("course_title", course_body.get("subject"))
        ),
        "course_outcomes": _course_outcomes(inputs, course_body),
        "audience": course_body.get("course_metadata", {}).get(
            "audience_summary", course_body.get("audience")
        ),
        "module": {
            "id": module.get("id"),
            "title": module.get("title"),
            "context": module.get("context"),
        },
        "target_asset": {
            "id": spec.asset_id,
            "type": spec.asset_type,
            "title": spec.title,
            "format": spec.format,
        },
        "focus_subtopic": focus_subtopic,
        "coverage_requirements": focus_subtopic.get("coverage_requirements", []),
        "neighbor_subtopics": sibling_subtopics,
        "blueprint_allocation": allocation,
        "depth_budget": subtopic_plan.get("depth_budget", {}),
        "asset_instructions": asset_plan.get(
            "instructions", [asset_plan["purpose"]] if asset_plan.get("purpose") else []
        ),
        "source_registry": [
            {
                "id": source["id"],
                "name": source["name"],
                "category": source["category"],
                "url": source.get("url"),
                "file": source.get("file"),
            }
            for source in source_registry.values()
        ],
        "valid_source_ids": sorted(source_registry),
        "sources": list(source_registry.values()),
    }


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


def _render_prompt(
    spec: AssetSpec,
    context: dict[str, Any],
    course_content: dict[str, Any] | None,
    feedback: str | None,
) -> str:
    prompt_path = REPO_ROOT / "prompts" / spec.prompt_filename
    template = prompt_path.read_text(encoding="utf-8")

    prompt_context = {key: value for key, value in context.items() if key != "sources"}
    source_texts = _format_source_texts(context["sources"])
    feedback_section = _format_feedback(feedback)

    rendered = (
        template.replace(
            "{{CONTEXT_JSON}}",
            json.dumps(prompt_context, ensure_ascii=False, indent=2),
        )
        .replace("{{SOURCE_TEXTS}}", source_texts)
        .replace("{{FEEDBACK_SECTION}}", feedback_section)
    )

    if spec.conditioned_on_course_content:
        cc_text = course_content.get("content", "") if course_content else ""
        rendered = rendered.replace("{{COURSE_CONTENT}}", cc_text)

    return rendered


def _format_source_texts(sources: list[dict[str, Any]]) -> str:
    blocks = []
    for source in sources:
        blocks.append(
            "\n".join(
                [
                    f"### Source {source['id']}: {source['name']}",
                    f"- Category: {source.get('category')}",
                    f"- URL: {source.get('url')}",
                    f"- File: {source.get('file')}",
                    "",
                    "```text",
                    source["text"],
                    "```",
                ]
            )
        )
    return "\n\n".join(blocks)


def _format_feedback(feedback: str | None) -> str:
    if not feedback:
        return "## Revision Feedback\n\nNone. Generate the baseline first draft."
    return f"## Revision Feedback\n\nApply this feedback while preserving grounding:\n\n{feedback}"


# ---------------------------------------------------------------------------
# API-facing JSON schema
# ---------------------------------------------------------------------------


def _build_asset_schema(spec: AssetSpec) -> dict[str, Any]:
    """Return the Anthropic structured-output schema for *spec*.

    The schema is kept broad (Anthropic rejects ``uniqueItems``/``maxItems``);
    the real v0.2 contract is enforced by ``_validate_and_normalize_asset``.
    The ``solution`` property is added only when ``spec.has_solution`` is True.
    """
    required_fields = [
        "id",
        "type",
        "title",
        "format",
        "content",
        "claims",
        "sources",
        "verification",
        "file",
        "status",
    ]
    properties: dict[str, Any] = {
        "id": {"type": "string"},
        "type": {"type": "string"},
        "title": {"type": "string"},
        "format": {"type": "string"},
        "content": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "text",
                    "source_id",
                    "support",
                    "supporting_excerpt",
                    "note",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "source_id": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ]
                    },
                    "support": {"type": "null"},
                    "supporting_excerpt": {"type": "null"},
                    "note": {"type": "null"},
                },
            },
        },
        "sources": {
            "type": "array",
            "items": {"type": "string"},
        },
        "verification": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "supported",
                "partial",
                "unsupported",
                "ungrounded",
                "unattributed_found",
                "checked_at",
            ],
            "properties": {
                "supported": {"type": "integer"},
                "partial": {"type": "integer"},
                "unsupported": {"type": "integer"},
                "ungrounded": {"type": "integer"},
                "unattributed_found": {"type": "array", "items": {"type": "string"}},
                "checked_at": {"type": "null"},
            },
        },
        "file": {"type": "null"},
        "status": {"type": "string"},
    }

    if spec.has_solution:
        required_fields.append("solution")
        properties["solution"] = {"type": "string"}

    return {
        "type": "object",
        "additionalProperties": False,
        "required": required_fields,
        "properties": properties,
    }


# ---------------------------------------------------------------------------
# Validation and normalisation
# ---------------------------------------------------------------------------


def _validate_and_normalize_asset(
    spec: AssetSpec,
    asset: dict[str, Any],
    valid_source_ids: set[str],
) -> dict[str, Any]:
    errors: list[str] = []

    # Identity fields must match the spec exactly.
    expected_fields = {
        "id": spec.asset_id,
        "type": spec.asset_type,
        "title": spec.title,
        "format": spec.format,
        "file": None,
        "status": "done",
    }
    for field, expected in expected_fields.items():
        if asset.get(field) != expected:
            errors.append(f"{field} must be {expected!r}; got {asset.get(field)!r}")

    if not isinstance(asset.get("content"), str) or not asset.get("content", "").strip():
        errors.append("content must be a non-empty string")

    # solution: required and non-empty for assessment; must be absent for others.
    if spec.has_solution:
        solution = asset.get("solution")
        if not isinstance(solution, str) or not solution.strip():
            errors.append("solution must be a non-empty string for assessment assets")
    else:
        if "solution" in asset:
            errors.append(f"solution must not be present on {spec.asset_type!r} assets")

    claims = asset.get("claims")
    if not isinstance(claims, list):
        errors.append("claims must be a list")
        claims = []

    seen_claim_ids: set[str] = set()
    derived_sources: list[str] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] must be an object")
            continue

        claim_id = claim.get("id")
        if not claim_id:
            errors.append(f"claims[{index}] is missing id")
        elif claim_id in seen_claim_ids:
            errors.append(f"duplicate claim id '{claim_id}'")
        else:
            seen_claim_ids.add(claim_id)

        if not isinstance(claim.get("text"), str) or not claim.get("text", "").strip():
            errors.append(f"claim '{claim_id or index}' text must be non-empty")

        for field in ("support", "supporting_excerpt", "note"):
            if claim.get(field) is not None:
                errors.append(f"claim '{claim_id or index}' {field} must be null before S3")

        source_id = claim.get("source_id")
        if source_id is None:
            continue
        if not isinstance(source_id, str):
            errors.append(f"claim '{claim_id or index}' source_id must be a string or null")
            continue
        if source_id not in valid_source_ids:
            errors.append(f"claim '{claim_id or index}' source_id '{source_id}' is not registered")
            continue
        if source_id not in derived_sources:
            derived_sources.append(source_id)

    # `sources` is the derived union of non-null claim source_ids (Plan E). We
    # derive it authoritatively from the claims above and let it be the source of
    # truth (it is what the normalized asset returns below). The writer's echo of
    # this redundant field is advisory only: models routinely over-list it (e.g.
    # naming every available source) or under-list it, and that bookkeeping slip
    # must not fail an otherwise-valid asset. The separate verifier (S3) — not
    # this field — is what scrutinizes attribution integrity.

    if asset.get("verification") != EMPTY_VERIFICATION:
        errors.append(f"verification must be the empty pre-S3 state: {EMPTY_VERIFICATION!r}")

    if errors:
        raise ValueError(f"Invalid {spec.asset_type} asset:\n- " + "\n- ".join(errors))

    normalised: dict[str, Any] = {
        "id": spec.asset_id,
        "type": spec.asset_type,
        "title": spec.title,
        "format": spec.format,
        "content": asset["content"],
        "claims": claims,
        "sources": derived_sources,
        "verification": EMPTY_VERIFICATION.copy(),
        "file": None,
        "status": "done",
    }
    if spec.has_solution:
        normalised["solution"] = asset["solution"]
    return normalised


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required input JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_body(artifact: dict[str, Any], name: str) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError(f"{name} must be an artifact envelope or JSON object body")
    return body


def _subtopic_id(inputs: dict[str, Any]) -> str:
    explicit = inputs.get("subtopic_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    course_body = _artifact_body(inputs["course_model"], "course_model")
    focus = course_body.get("focus_subtopic")
    if isinstance(focus, str) and focus:
        return focus
    raise ValueError("generation inputs must identify a subtopic_id")


def _course_outcomes(
    inputs: dict[str, Any],
    course_body: dict[str, Any],
) -> list[Any]:
    artifact = inputs.get("course_outcomes")
    if isinstance(artifact, dict):
        body = _artifact_body(artifact, "course_outcomes")
        outcomes = body.get("outcomes", [])
        if isinstance(outcomes, list):
            return outcomes
    outcomes = course_body.get("course_outcomes", [])
    return outcomes if isinstance(outcomes, list) else []


def _find_course_subtopic(
    course_body: dict[str, Any],
    subtopic_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in course_body.get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") == subtopic_id:
                return module, subtopic
    raise ValueError(f"Course Model does not contain subtopic '{subtopic_id}'")


def _find_blueprint_allocation(
    blueprint_body: dict[str, Any],
    subtopic_id: str,
) -> dict[str, Any] | None:
    for allocation in blueprint_body.get("allocations", []):
        if allocation.get("node_id") == subtopic_id:
            return allocation
    return None


def _find_blueprint_subtopic_plan(
    blueprint_body: dict[str, Any],
    subtopic_id: str,
) -> dict[str, Any] | None:
    for plan in blueprint_body.get("subtopic_plans", []):
        if plan.get("subtopic_id") == subtopic_id:
            return plan
    return None


def _raw_asset_plan(plan: dict[str, Any] | None) -> list[Any] | None:
    if plan is None:
        return None
    raw = plan.get("asset_plan", plan.get("assets"))
    if raw is not None and not isinstance(raw, list):
        raise ValueError("Blueprint subtopic asset_plan must be a list")
    return raw


def _asset_depth_requirements(spec: AssetSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")
    plan = _find_blueprint_subtopic_plan(blueprint_body, _subtopic_id(inputs)) or {}
    # The subtopic-level word/learning budget governs the anchor lesson. Other
    # assets opt into their own mechanical limits through their asset-plan
    # entry; a summary must not inherit a 1,600-word Course Content minimum.
    requirements = dict(plan.get("depth_budget", {})) if spec.asset_type == "course_content" else {}
    word_range = requirements.get("target_word_range")
    if isinstance(word_range, dict):
        requirements.setdefault("min_words", word_range.get("minimum"))
        requirements.setdefault("max_words", word_range.get("maximum"))
    if requirements.get("expansion_policy") == "targeted_by_coverage_gap":
        requirements.setdefault(
            "max_generation_attempts",
            3 if spec.asset_type == "course_content" else 1,
        )
    for item in _raw_asset_plan(plan) or []:
        if not isinstance(item, dict):
            continue
        if item.get("asset_type", item.get("type")) != spec.asset_type:
            continue
        requirements.update(item.get("depth_budget", {}))
        for field in ("min_words", "max_words", "required_sections", "max_generation_attempts"):
            if field in item:
                requirements[field] = item[field]
        break
    return requirements


def _depth_shortfalls(asset: dict[str, Any], requirements: dict[str, Any]) -> list[str]:
    content = asset.get("content", "")
    words = content.split()
    shortfalls = []
    min_words = requirements.get("min_words")
    if min_words is not None:
        if type(min_words) is not int or min_words < 0:
            raise ValueError("depth_budget.min_words must be a non-negative integer")
        if len(words) < min_words:
            shortfalls.append(f"draft has {len(words)} words; approved minimum is {min_words}")
    required_sections = requirements.get("required_sections", [])
    if not isinstance(required_sections, list) or not all(
        isinstance(section, str) and section.strip() for section in required_sections
    ):
        raise ValueError("depth_budget.required_sections must be a list of non-empty strings")
    lowered = content.casefold()
    missing = [section for section in required_sections if section.casefold() not in lowered]
    if missing:
        shortfalls.append("missing required sections: " + ", ".join(missing))
    return shortfalls


def _load_registered_sources(
    course_body: dict[str, Any],
    approved_source_ids: Any = None,
) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    categories = course_body.get("grounding_sources", [])
    if not categories and isinstance(course_body.get("source_registry"), list):
        categories = [{"category": "APPROVED", "items": course_body["source_registry"]}]
    for category in categories:
        category_name = category.get("category")
        for item in category.get("items", []):
            source_id = item.get("id")
            if not source_id:
                raise ValueError("Encountered grounding source without an id")
            if source_id in sources:
                raise ValueError(f"Duplicate grounding source id '{source_id}'")

            source_file = item.get("file", item.get("content_ref"))
            if not source_file:
                raise ValueError(f"Grounding source '{source_id}' is missing file")
            source_path = Path(source_file)
            if not source_path.is_absolute():
                source_path = REPO_ROOT / source_path
            if not source_path.exists():
                raise FileNotFoundError(
                    f"Grounding source '{source_id}' file not found: {source_path}"
                )

            sources[source_id] = {
                **item,
                "name": item.get("name", item.get("title", source_id)),
                "category": category_name or item.get("source_type"),
                "url": item.get("url", item.get("locator")),
                "file": source_file,
                "text": prepare_source_excerpt(source_path.read_text(encoding="utf-8")),
            }
    if not sources:
        raise ValueError("Course Model has no registered grounding sources")

    if approved_source_ids is None:
        return sources
    if not isinstance(approved_source_ids, list) or not all(
        isinstance(source_id, str) for source_id in approved_source_ids
    ):
        raise ValueError("approved_source_ids must be a list of source-id strings")
    unknown = sorted(set(approved_source_ids) - set(sources))
    if unknown:
        raise ValueError("approved_source_ids are not registered: " + ", ".join(unknown))
    return {source_id: sources[source_id] for source_id in approved_source_ids}


def _write_asset(path: Path, asset: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_ASSET_OUTPUT_FILENAMES: dict[str, str] = {
    "course_content": "s2_3_course_content_asset.json",
    "learning_objectives": "s2_4_learning_objectives_asset.json",
    "summary": "s2_4_summary_asset.json",
    "case_study": "s2_4_case_study_asset.json",
    "assessment": "s2_4_assessment_asset.json",
    "important_person": "s3_5_important_person_asset.json",
    "did_you_know": "s3_5_did_you_know_asset.json",
    "activities": "s3_5_activities_asset.json",
    "resources": "s3_5_resources_asset.json",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a selected student-content asset.")
    parser.add_argument("--course-id", default="frm-demo")
    parser.add_argument("--subtopic-id", default="m1_s1")
    parser.add_argument(
        "--asset",
        choices=list(ASSET_SPECS),
        default="course_content",
        help="Which asset to generate (default: course_content).",
    )
    parser.add_argument(
        "--course-model",
        type=Path,
        default=DEFAULT_COURSE_MODEL_PATH,
        help="Path to the approved compact Course Model artifact.",
    )
    parser.add_argument(
        "--blueprint",
        type=Path,
        default=None,
        help="Path to the approved Blueprint (defaults to the course folder).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Where to write the generated asset JSON. "
            "Defaults to outputs/phase1/m1_s1/<asset-filename>."
        ),
    )
    parser.add_argument(
        "--course-content-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=(
            "Path to the already-generated Course Content asset JSON. "
            "Required when generating any conditioned asset (all except course_content). "
            f"Defaults to {DEFAULT_OUTPUT_PATH}."
        ),
    )
    parser.add_argument("--model", default=llm.DEFAULT_MODEL)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--feedback", default=None)
    args = parser.parse_args(argv)

    spec = ASSET_SPECS[args.asset]

    output_path: Path = args.output or (DEFAULT_OUTPUT_DIR / _ASSET_OUTPUT_FILENAMES[args.asset])

    inputs = load_generation_inputs(
        course_id=args.course_id,
        course_model_path=args.course_model,
        blueprint_path=args.blueprint,
        subtopic_id=args.subtopic_id,
    )

    course_content: dict[str, Any] | None = None
    if spec.conditioned_on_course_content:
        cc_path: Path = args.course_content_path
        if not cc_path.exists():
            print(
                f"ERROR: Course Content asset not found at {cc_path}. "
                "Generate it first with --asset course_content."
            )
            return 1
        course_content = _load_json(cc_path)

    asset = generate_asset_to_depth(
        spec,
        inputs,
        course_content=course_content,
        feedback=args.feedback,
        model=args.model,
        use_cache=not args.no_cache,
    )
    _write_asset(output_path, asset)
    print(f"Wrote {spec.asset_type} asset to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
