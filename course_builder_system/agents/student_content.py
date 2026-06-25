"""Student Content generation for Phase 1.

S2.2 implements only the Course Content asset for the `m1_s1` proof point.
S2.5 will decide how this plugs into `student_content_step`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import llm

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "prompts" / "course_content.md"
COURSES_DIR = REPO_ROOT / "courses"
DEFAULT_DOMAIN_MODEL_PATH = REPO_ROOT / "domain" / "m1_s1_domain_model.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "outputs" / "phase1" / "m1_s1" / "s2_3_course_content_asset.json"

COURSE_CONTENT_ID = "m1_s1_cc"
COURSE_CONTENT_TYPE = "course_content"
COURSE_CONTENT_TITLE = "Nature of Financial Risk"
COURSE_CONTENT_FORMAT = "pptx"
COURSE_CONTENT_MAX_TOKENS = 12_000

COURSE_CONTENT_SYSTEM = (
    "You are the Course Builder Student Content agent. Generate only grounded, "
    "schema-valid JSON for the requested Course Content asset."
)

EMPTY_VERIFICATION = {
    "supported": 0,
    "partial": 0,
    "unsupported": 0,
    "ungrounded": 0,
    "unattributed_found": [],
    "checked_at": None,
}


def generate_course_content(
    inputs: dict[str, Any],
    feedback: str | None = None,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Generate one v0.2 Course Content asset.

    `inputs` should contain artifact envelopes for `toc`, `blueprint`, and the
    Sprint 1 deep `domain_model`. The optional `subtopic_id` entry selects the
    target subtopic and defaults to the Domain Model's `focus_subtopic`.
    """
    context = _build_prompt_context(inputs)
    prompt = _render_prompt(context, feedback)
    schema = _course_content_asset_schema()

    result = llm.call(
        [{"role": "user", "content": prompt}],
        system=COURSE_CONTENT_SYSTEM,
        model=model,
        max_tokens=COURSE_CONTENT_MAX_TOKENS,
        schema=schema,
        use_cache=use_cache,
    )

    asset = result.parsed
    if asset is None:
        asset = json.loads(result.text)
    if not isinstance(asset, dict):
        raise ValueError("Course Content generation returned a non-object JSON value")

    return _validate_and_normalize_asset(asset, set(context["valid_source_ids"]))


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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required input JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_body(artifact: dict[str, Any], name: str) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError(f"{name} must be an artifact envelope or JSON object body")
    return body


def _build_prompt_context(inputs: dict[str, Any]) -> dict[str, Any]:
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

    context = {
        "course_id": inputs["toc"].get("course_id"),
        "subject": domain_body.get("subject") or toc_body.get("subject"),
        "module": domain_body.get("module"),
        "target_asset": {
            "id": COURSE_CONTENT_ID,
            "type": COURSE_CONTENT_TYPE,
            "title": COURSE_CONTENT_TITLE,
            "format": COURSE_CONTENT_FORMAT,
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
    return context


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


def _render_prompt(context: dict[str, Any], feedback: str | None) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt_context = {key: value for key, value in context.items() if key != "sources"}
    source_texts = _format_source_texts(context["sources"])
    feedback_section = _format_feedback(feedback)

    return (
        template.replace(
            "{{CONTEXT_JSON}}",
            json.dumps(prompt_context, ensure_ascii=False, indent=2),
        )
        .replace("{{SOURCE_TEXTS}}", source_texts)
        .replace("{{FEEDBACK_SECTION}}", feedback_section)
    )


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


def _course_content_asset_schema() -> dict[str, Any]:
    # Anthropic's structured-output schema subset rejects several standard
    # JSON Schema validation keywords (for example uniqueItems/maxItems).
    # Keep the API-facing schema broad, then enforce the real v0.2 contract in
    # `_validate_and_normalize_asset`.
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
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
        ],
        "properties": {
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
        },
    }


def _validate_and_normalize_asset(
    asset: dict[str, Any],
    valid_source_ids: set[str],
) -> dict[str, Any]:
    errors: list[str] = []

    expected_fields = {
        "id": COURSE_CONTENT_ID,
        "type": COURSE_CONTENT_TYPE,
        "title": COURSE_CONTENT_TITLE,
        "format": COURSE_CONTENT_FORMAT,
        "file": None,
        "status": "done",
    }
    for field, expected in expected_fields.items():
        if asset.get(field) != expected:
            errors.append(f"{field} must be {expected!r}; got {asset.get(field)!r}")

    if not isinstance(asset.get("content"), str) or not asset.get("content", "").strip():
        errors.append("content must be a non-empty string")

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
            errors.append(
                f"claim '{claim_id or index}' source_id '{source_id}' is not registered"
            )
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
        errors.append(
            f"verification must be the empty pre-S3 state: {EMPTY_VERIFICATION!r}"
        )

    if errors:
        raise ValueError("Invalid Course Content asset:\n- " + "\n- ".join(errors))

    return {
        "id": COURSE_CONTENT_ID,
        "type": COURSE_CONTENT_TYPE,
        "title": COURSE_CONTENT_TITLE,
        "format": COURSE_CONTENT_FORMAT,
        "content": asset["content"],
        "claims": claims,
        "sources": derived_sources,
        "verification": EMPTY_VERIFICATION.copy(),
        "file": None,
        "status": "done",
    }


def _write_asset(path: Path, asset: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the m1_s1 Course Content asset.")
    parser.add_argument("--course-id", default="frm-demo")
    parser.add_argument("--subtopic-id", default="m1_s1")
    parser.add_argument(
        "--domain-model",
        type=Path,
        default=DEFAULT_DOMAIN_MODEL_PATH,
        help="Path to the Sprint 1 deep Domain Model artifact.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the generated Course Content asset JSON.",
    )
    parser.add_argument("--model", default=llm.DEFAULT_MODEL)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--feedback", default=None)
    args = parser.parse_args(argv)

    inputs = load_generation_inputs(
        course_id=args.course_id,
        domain_model_path=args.domain_model,
        subtopic_id=args.subtopic_id,
    )
    asset = generate_course_content(
        inputs,
        feedback=args.feedback,
        model=args.model,
        use_cache=not args.no_cache,
    )
    _write_asset(args.output, asset)
    print(f"Wrote Course Content asset to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
