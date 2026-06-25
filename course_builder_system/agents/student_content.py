"""Student Content generation for Phase 1.

S2.3 implements the Course Content asset; S2.4 adds Learning Objectives,
Summary, Case Study, and Assessment — all conditioned on the Course Content
anchor. S2.5 will decide how this plugs into `student_content_step`.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import llm

REPO_ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = REPO_ROOT / "courses"
DEFAULT_DOMAIN_MODEL_PATH = REPO_ROOT / "domain" / "m1_s1_domain_model.json"
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

    asset_id: str
    asset_type: str
    title: str
    format: str
    prompt_filename: str
    max_tokens: int
    has_solution: bool
    conditioned_on_course_content: bool


# Registry of the five core-5 specs, keyed by a short name used in the CLI.
ASSET_SPECS: dict[str, AssetSpec] = {
    "course_content": AssetSpec(
        asset_id="m1_s1_cc",
        asset_type="course_content",
        title="Nature of Financial Risk",
        format="pptx",
        prompt_filename="course_content.md",
        max_tokens=12_000,
        has_solution=False,
        conditioned_on_course_content=False,
    ),
    "learning_objectives": AssetSpec(
        asset_id="m1_s1_lo",
        asset_type="learning_objectives",
        title="Learning Objectives",
        format="docx",
        prompt_filename="learning_objectives.md",
        max_tokens=3_500,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "summary": AssetSpec(
        asset_id="m1_s1_summary",
        asset_type="summary",
        title="Summary",
        format="docx",
        prompt_filename="summary.md",
        max_tokens=4_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "case_study": AssetSpec(
        asset_id="m1_s1_case",
        asset_type="case_study",
        title="The Lehman Brothers Collapse",
        format="pptx",
        prompt_filename="case_study.md",
        max_tokens=6_000,
        has_solution=False,
        conditioned_on_course_content=True,
    ),
    "assessment": AssetSpec(
        asset_id="m1_s1_assess",
        asset_type="assessment",
        title="Assessment Quiz: Nature of Financial Risk",
        format="pptx",
        prompt_filename="assessment.md",
        max_tokens=5_000,
        has_solution=True,
        conditioned_on_course_content=True,
    ),
}

COURSE_CONTENT_SPEC = ASSET_SPECS["course_content"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    )

    asset = result.parsed
    if asset is None:
        asset = json.loads(result.text)
    if not isinstance(asset, dict):
        raise ValueError(f"{spec.asset_type} generation returned a non-object JSON value")

    return _validate_and_normalize_asset(spec, asset, set(context["valid_source_ids"]))


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
    domain_model_path: Path = DEFAULT_DOMAIN_MODEL_PATH,
    subtopic_id: str = "m1_s1",
) -> dict[str, Any]:
    """Load CLI inputs without mutating any course artifacts."""
    course_dir = COURSES_DIR / course_id
    return {
        "toc": _load_json(course_dir / "toc.json"),
        "blueprint": _load_json(course_dir / "blueprint.json"),
        "domain_model": _load_json(domain_model_path),
        "subtopic_id": subtopic_id,
    }


# ---------------------------------------------------------------------------
# Prompt context construction
# ---------------------------------------------------------------------------


def _build_prompt_context(spec: AssetSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    domain_body = _artifact_body(inputs["domain_model"], "domain_model")
    toc_body = _artifact_body(inputs["toc"], "toc")
    blueprint_body = _artifact_body(inputs["blueprint"], "blueprint")

    subtopic_id = inputs.get("subtopic_id") or domain_body.get("focus_subtopic") or "m1_s1"
    focus_subtopic = _find_domain_subtopic(domain_body, subtopic_id)
    toc_subtopic = _find_toc_subtopic(toc_body, subtopic_id)
    source_registry = _load_registered_sources(domain_body)
    allocation = _find_blueprint_allocation(blueprint_body, subtopic_id)

    sibling_subtopics = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "depth": item.get("depth"),
        }
        for item in domain_body.get("subtopics", [])
        if item.get("id") != subtopic_id
    ]

    return {
        "course_id": inputs["toc"].get("course_id"),
        "subject": domain_body.get("subject") or toc_body.get("subject"),
        "module": domain_body.get("module"),
        "target_asset": {
            "id": spec.asset_id,
            "type": spec.asset_type,
            "title": spec.title,
            "format": spec.format,
        },
        "focus_subtopic": focus_subtopic,
        "toc_subtopic": toc_subtopic,
        "thin_neighbor_subtopics": sibling_subtopics,
        "blueprint_allocation": allocation,
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

    asset_sources = asset.get("sources")
    if asset_sources != derived_sources:
        errors.append(
            "sources must match non-null claim source_id union; "
            f"expected {derived_sources}, got {asset_sources!r}"
        )

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


def _find_domain_subtopic(domain_body: dict[str, Any], subtopic_id: str) -> dict[str, Any]:
    for subtopic in domain_body.get("subtopics", []):
        if subtopic.get("id") == subtopic_id:
            return subtopic
    raise ValueError(f"Domain Model does not contain subtopic '{subtopic_id}'")


def _find_toc_subtopic(toc_body: dict[str, Any], subtopic_id: str) -> dict[str, Any]:
    for module in toc_body.get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") == subtopic_id:
                return {
                    "module_id": module.get("id"),
                    "module_title": module.get("title"),
                    **subtopic,
                }
    raise ValueError(f"TOC does not contain subtopic '{subtopic_id}'")


def _find_blueprint_allocation(
    blueprint_body: dict[str, Any],
    subtopic_id: str,
) -> dict[str, Any] | None:
    for allocation in blueprint_body.get("allocations", []):
        if allocation.get("node_id") == subtopic_id:
            return allocation
    return None


def _load_registered_sources(domain_body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for category in domain_body.get("grounding_sources", []):
        category_name = category.get("category")
        for item in category.get("items", []):
            source_id = item.get("id")
            if not source_id:
                raise ValueError("Encountered grounding source without an id")
            if source_id in sources:
                raise ValueError(f"Duplicate grounding source id '{source_id}'")

            source_file = item.get("file")
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
                "category": category_name,
                "text": source_path.read_text(encoding="utf-8"),
            }
    if not sources:
        raise ValueError("Domain Model has no registered grounding sources")
    return sources


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
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate one or more m1_s1 student-content assets."
    )
    parser.add_argument("--course-id", default="frm-demo")
    parser.add_argument("--subtopic-id", default="m1_s1")
    parser.add_argument(
        "--asset",
        choices=list(ASSET_SPECS),
        default="course_content",
        help="Which asset to generate (default: course_content).",
    )
    parser.add_argument(
        "--domain-model",
        type=Path,
        default=DEFAULT_DOMAIN_MODEL_PATH,
        help="Path to the Sprint 1 deep Domain Model artifact.",
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
            "Required when generating a conditioned asset (lo/summary/case/assessment). "
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
        domain_model_path=args.domain_model,
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

    asset = generate_asset(
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
