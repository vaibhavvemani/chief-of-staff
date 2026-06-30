"""
S2.7 Contract tests for the v0.2 Content Package.

Tests
-----
1. test_schema_validator_positive_gold      - gold benchmark validates clean
2. test_schema_validator_negatives         - validator catches 5 specific violations
3. test_assembled_package_is_schema_valid_v02 - assembled artifact (mocked LLM) passes schema
4. test_all_nine_assets_present            - correct asset ids/types/solution presence
5. test_claims_resolve_and_integrity_passes - integrity.py returns [] for saved artifacts
6. test_full_pipeline_plumbing_llm_mocked  - full pipeline dry-run, schema + integrity clean

LLM is NEVER called: generate_asset is monkeypatched throughout.
No live ANTHROPIC_API_KEY is needed.  The real courses/frm-demo/ is never touched.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path (conftest.py also does this; belt +
# suspenders so the file is importable standalone too).
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import integrity  # noqa: E402
import orchestrator  # noqa: E402
import steps  # noqa: E402
from agents import student_content  # noqa: E402
from orchestrator import Decision, Step, make_artifact, run_pipeline, save_artifact  # noqa: E402
from tests.schema_check import validate_content_package  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
GOLD_PATH = REPO_ROOT / "benchmark" / "m1_s1.gold.content_package.json"

# ---------------------------------------------------------------------------
# Fixture assets returned by the mocked generate_asset
# ---------------------------------------------------------------------------
# The asset shape mirrors what the real generate_asset returns after
# _validate_and_normalize_asset runs. Every field required by the v0.2 schema
# is present; sources[] == the non-null claim source_id union so integrity
# passes.  `solution` is ONLY present when spec.has_solution.

# Several core and light assets include one claim citing a registered source so
# that "claims resolve to grounding ids" is genuinely exercised by
# test_claims_resolve_and_integrity_passes and
# test_full_pipeline_plumbing_llm_mocked.

_EMPTY_VERIFICATION = {
    "supported": 0,
    "partial": 0,
    "unsupported": 0,
    "ungrounded": 0,
    "unattributed_found": [],
    "checked_at": None,
}


def _make_fixture_asset(spec: student_content.AssetSpec) -> dict:
    """Build a minimal, schema-valid v0.2 asset dict for *spec*.

    Representative factual assets include one claim citing a compatible source
    so the test suite genuinely exercises the grounding-id resolution path.
    Other assets have empty claims/sources (also valid: empty union == empty
    sources list, so integrity passes).
    """
    source_by_type = {
        "course_content": "g5",
        "case_study": "g5",
        "important_person": "g1",
        "did_you_know": "g5",
        "resources": "g1",
    }
    source_id = source_by_type.get(spec.asset_type)
    if source_id:
        claims = [
            {
                "id": f"{spec.asset_id}_c1",
                "text": "Grounded fixture claim.",
                "source_id": source_id,
                "support": None,
                "supporting_excerpt": None,
                "note": None,
            }
        ]
        sources = [source_id]
    else:
        claims = []
        sources = []

    asset: dict = {
        "id": spec.asset_id,
        "type": spec.asset_type,
        "title": spec.title,
        "format": spec.format,
        "content": f"<{spec.asset_type} body for testing>",
        "claims": claims,
        "sources": sources,
        "verification": _EMPTY_VERIFICATION,
        "file": None,
        "status": "done",
    }
    if spec.has_solution:
        asset["solution"] = "<teacher answer key>"
    return asset


def _fixture_generate_asset(
    spec: student_content.AssetSpec,
    inputs: dict,
    course_content: dict | None = None,
    feedback: str | None = None,
    model: str = "mock",
    use_cache: bool = True,
) -> dict:
    """Drop-in replacement for student_content.generate_asset (no LLM call)."""
    if spec.conditioned_on_course_content:
        assert course_content is not None
        assert course_content["id"] == "m1_s1_cc"
    else:
        assert course_content is None
    return _make_fixture_asset(spec)


def _fixture_verify_content_package(
    content_package: dict,
    domain_model: dict,
    **kwargs,
) -> dict:
    """Drop-in package verifier for plumbing tests (no LLM call)."""
    verified = copy.deepcopy(content_package)
    body = verified.get("body", verified)
    for subtopic in body["subtopics"]:
        for asset in subtopic["assets"]:
            supported = 0
            ungrounded = 0
            for claim in asset["claims"]:
                if claim["source_id"] is None:
                    claim["support"] = None
                    claim["supporting_excerpt"] = None
                    claim["note"] = "Ungrounded fixture claim."
                    ungrounded += 1
                else:
                    claim["support"] = "supported"
                    claim["supporting_excerpt"] = "Fixture evidence."
                    claim["note"] = "Supported fixture claim."
                    supported += 1
            asset["verification"] = {
                "supported": supported,
                "partial": 0,
                "unsupported": 0,
                "ungrounded": ungrounded,
                "unattributed_found": [],
                "checked_at": "2026-06-30T00:00:00+00:00",
            }
    return verified


LIGHT_ASSET_EXPECTATIONS = {
    "important_person": (
        "m1_s1_person",
        "Frank Knight — The Foundation of Risk Theory",
        "pptx",
        "s3_5_important_person_asset.json",
    ),
    "did_you_know": (
        "m1_s1_dyk",
        "The CRO Role Barely Existed Before the 1990s",
        "pptx",
        "s3_5_did_you_know_asset.json",
    ),
    "activities": ("m1_s1_activities", "Activities", "docx", "s3_5_activities_asset.json"),
    "resources": (
        "m1_s1_resources",
        "Additional Resources",
        "docx",
        "s3_5_resources_asset.json",
    ),
}


@pytest.mark.parametrize(("name", "expected"), LIGHT_ASSET_EXPECTATIONS.items())
def test_light_asset_specs_and_prompt_contract(name, expected):
    """The light-four registry and prompts preserve the v0.2 generation contract."""
    expected_id, expected_title, expected_format, expected_filename = expected
    spec = student_content.ASSET_SPECS[name]

    assert spec.asset_id == expected_id
    assert spec.asset_type == name
    assert spec.title == expected_title
    assert spec.format == expected_format
    assert spec.conditioned_on_course_content is True
    assert spec.has_solution is False
    assert spec.max_tokens > 0
    assert student_content._ASSET_OUTPUT_FILENAMES[name] == expected_filename

    prompt = (REPO_ROOT / "prompts" / spec.prompt_filename).read_text(encoding="utf-8")
    for placeholder in (
        "{{COURSE_CONTENT}}",
        "{{CONTEXT_JSON}}",
        "{{SOURCE_TEXTS}}",
        "{{FEEDBACK_SECTION}}",
    ):
        assert placeholder in prompt
    assert f"- `id`: `{expected_id}`" in prompt
    assert f"- `type`: `{name}`" in prompt
    assert "Do not include a `solution` field." in prompt
    assert "Every significant factual claim must appear in `claims[]`." in prompt
    assert "solution" not in student_content._build_asset_schema(spec)["properties"]


# ---------------------------------------------------------------------------
# Helper: build a fully-assembled content_package artifact using stub steps
# (structure_step, blueprint_step) and the mocked generate_asset.
# ---------------------------------------------------------------------------


def _build_content_package_artifact() -> dict:
    """Run structure_step + blueprint_step (pure stubs, no LLM) then call
    student_content_step with generate_asset mocked.

    Returns the content_package artifact dict.
    """
    # Brief (seed artifact)
    brief = make_artifact(
        "test-course",
        artifact_type="brief",
        produced_by_step="human",
        body={
            "subject": "Financial Risk Management",
            "audience": "PG",
            "level": "intermediate",
            "goals": "test goals",
            "scope": "test scope",
        },
        inputs=[],
    )

    # structure_step (no LLM, reads from domain/m1_s1_domain_model.json)
    struct_out = steps.structure_step({"brief": brief}, None)
    toc = struct_out["toc"]
    domain_model = struct_out["domain_model"]

    # blueprint_step (pure stub)
    bp_out = steps.blueprint_step({"toc": toc, "domain_model": domain_model}, None)
    blueprint = bp_out["blueprint"]

    # student_content_step with generate_asset mocked
    with (
        patch("steps.student_content.generate_asset", side_effect=_fixture_generate_asset),
        patch(
            "steps.verification.verify_content_package",
            side_effect=_fixture_verify_content_package,
        ),
    ):
        sc_out = steps.student_content_step(
            {"toc": toc, "blueprint": blueprint, "domain_model": domain_model},
            None,
        )
    return sc_out["content_package"]


# ===========================================================================
# Test 1: positive gold
# ===========================================================================


def test_schema_validator_positive_gold():
    """The gold benchmark must validate clean against the v0.2 schema.

    The gold envelope must have produced_by_step='student_content',
    schema_version='0.2', and inputs containing 'toc'.  If any of these is
    wrong the test is xfail (it would indicate an S2.1 migration gap to fix).
    """
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))

    # Check envelope preconditions.
    envelope_ok = (
        gold.get("produced_by_step") == "student_content"
        and gold.get("schema_version") == "0.2"
        and gold.get("artifact_type") == "content_package"
        and "toc" in (gold.get("inputs") or [])
    )
    if not envelope_ok:
        pytest.xfail(
            "GOLD ENVELOPE INVALID: produced_by_step="
            f"{gold.get('produced_by_step')!r}, schema_version="
            f"{gold.get('schema_version')!r}, artifact_type="
            f"{gold.get('artifact_type')!r}, inputs={gold.get('inputs')!r}. "
            "This indicates an S2.1 migration gap — fix the gold file."
        )

    errors = validate_content_package(gold)
    assert errors == [], "Gold benchmark has schema errors:\n" + "\n".join(errors)


# ===========================================================================
# Test 2: negative tests — the validator is NOT a no-op
# ===========================================================================


def test_schema_validator_negatives():
    """Prove the validator catches five distinct v0.2 violations.

    Each mutation takes the assembled package, applies one bad change, and
    asserts the validator returns a non-empty error list.  If the validator
    were a no-op these assertions would all fail.
    """
    good = _build_content_package_artifact()
    assert validate_content_package(good) == [], "Assembled package must be valid before mutation"

    # (a) produced_by_step set to a wrong value (violates const)
    bad_a = copy.deepcopy(good)
    bad_a["produced_by_step"] = "wrong_step"
    errs_a = validate_content_package(bad_a)
    assert errs_a, "Validator must catch wrong produced_by_step (const violation)"

    # (b) required envelope key removed
    bad_b = copy.deepcopy(good)
    del bad_b["revision"]
    errs_b = validate_content_package(bad_b)
    assert errs_b, "Validator must catch missing required key 'revision'"

    # (c) an asset type not in the enum
    bad_c = copy.deepcopy(good)
    bad_c["body"]["subtopics"][0]["assets"][0]["type"] = "not_a_real_type"
    errs_c = validate_content_package(bad_c)
    assert errs_c, "Validator must catch an asset type not in the enum"

    # (d) a claim source_id = "x9" violates the ^g[0-9]+$ pattern
    bad_d = copy.deepcopy(good)
    assets = bad_d["body"]["subtopics"][0]["assets"]
    # Find an asset with at least one claim (course_content has one)
    for asset in assets:
        if asset.get("claims"):
            asset["claims"][0]["source_id"] = "x9"
            # Keep sources consistent with the (now-invalid) claim for a clean
            # test that only the pattern check fires.
            asset["sources"] = ["x9"]
            break
    errs_d = validate_content_package(bad_d)
    assert errs_d, "Validator must catch source_id 'x9' violating ^g[0-9]+$ pattern"

    # (e) extra unexpected key on an asset (violates additionalProperties:false)
    bad_e = copy.deepcopy(good)
    bad_e["body"]["subtopics"][0]["assets"][0]["__extra__"] = "oops"
    errs_e = validate_content_package(bad_e)
    assert errs_e, "Validator must catch extra key on asset (additionalProperties:false)"


# ===========================================================================
# Test 3: assembled package is schema-valid v0.2
# ===========================================================================


def test_assembled_package_is_schema_valid_v02():
    """Build inputs from real stub steps, mock generate_asset, run
    student_content_step, and assert the returned artifact passes the v0.2 schema.
    """
    artifact = _build_content_package_artifact()
    errors = validate_content_package(artifact)
    assert errors == [], "Assembled content_package has schema errors:\n" + "\n".join(errors)


# ===========================================================================
# Test 4: all nine assets present and correctly structured
# ===========================================================================


def test_all_nine_assets_present():
    """Verify the assembled body has the right vocabulary, subtopic, and assets."""
    artifact = _build_content_package_artifact()
    body = artifact["body"]

    # Full 9-type vocabulary
    expected_vocab = [
        "learning_objectives",
        "course_content",
        "summary",
        "case_study",
        "important_person",
        "did_you_know",
        "assessment",
        "activities",
        "resources",
    ]
    assert body["asset_vocabulary"] == expected_vocab, (
        f"asset_vocabulary mismatch: {body['asset_vocabulary']}"
    )

    # Exactly one subtopic: m1_s1
    subtopics = body["subtopics"]
    assert len(subtopics) == 1, f"Expected 1 subtopic, got {len(subtopics)}"
    assert subtopics[0]["subtopic_id"] == "m1_s1"

    assets = subtopics[0]["assets"]
    # The anchor is generated first, followed by the remaining core and light
    # assets, all conditioned on that anchor.
    expected_ids_types = [
        ("m1_s1_cc", "course_content"),
        ("m1_s1_lo", "learning_objectives"),
        ("m1_s1_summary", "summary"),
        ("m1_s1_case", "case_study"),
        ("m1_s1_assess", "assessment"),
        ("m1_s1_person", "important_person"),
        ("m1_s1_dyk", "did_you_know"),
        ("m1_s1_activities", "activities"),
        ("m1_s1_resources", "resources"),
    ]
    assert len(assets) == len(expected_ids_types), (
        f"Expected {len(expected_ids_types)} assets, got {len(assets)}: {[a['id'] for a in assets]}"
    )
    for asset, (exp_id, exp_type) in zip(assets, expected_ids_types, strict=True):
        assert asset["id"] == exp_id, f"Asset id mismatch: {asset['id']!r} != {exp_id!r}"
        assert asset["type"] == exp_type, f"Asset {exp_id}: type {asset['type']!r} != {exp_type!r}"

    # Assessment must have a non-empty solution; others must NOT have solution
    for asset in assets:
        if asset["id"] == "m1_s1_assess":
            assert "solution" in asset and asset["solution"], (
                "Assessment asset must have a non-empty 'solution' field"
            )
        else:
            assert "solution" not in asset, (
                f"Non-assessment asset {asset['id']!r} must not have 'solution'"
            )


# ===========================================================================
# Test 5: claims resolve and integrity passes
# ===========================================================================


def test_claims_resolve_and_integrity_passes(tmp_path):
    """Save all artifacts (toc, domain_model, blueprint, content_package) to
    a tmp directory and assert integrity.check_referential_integrity returns [].

    The fixtures include claims citing g5, exercising the grounding-id
    resolution and source-union checks in integrity.py.
    """
    # Build the artifact set
    brief = make_artifact(
        "test-integrity",
        artifact_type="brief",
        produced_by_step="human",
        body={
            "subject": "Financial Risk Management",
            "audience": "PG",
            "level": "intermediate",
            "goals": "g",
            "scope": "s",
        },
        inputs=[],
    )
    struct_out = steps.structure_step({"brief": brief}, None)
    toc = struct_out["toc"]
    domain_model = struct_out["domain_model"]
    bp_out = steps.blueprint_step({"toc": toc, "domain_model": domain_model}, None)
    blueprint = bp_out["blueprint"]

    with (
        patch("steps.student_content.generate_asset", side_effect=_fixture_generate_asset),
        patch(
            "steps.verification.verify_content_package",
            side_effect=_fixture_verify_content_package,
        ),
    ):
        sc_out = steps.student_content_step(
            {"toc": toc, "blueprint": blueprint, "domain_model": domain_model},
            None,
        )
    content_package = sc_out["content_package"]

    # Redirect orchestrator to tmp_path so we never touch courses/frm-demo/
    courses_tmp = tmp_path / "courses"

    # Fix course_id on all artifacts to "test-integrity"
    for art in (toc, domain_model, blueprint, content_package):
        art["course_id"] = "test-integrity"
        art["status"] = "approved"

    with patch.object(orchestrator, "COURSES_DIR", courses_tmp):
        # integrity.py imports load_artifact from orchestrator at module load
        # time, so we also need to patch orchestrator.COURSES_DIR inside
        # the integrity module's reference.
        _load = lambda cid, atype: _patched_load(courses_tmp, cid, atype)  # noqa: E731
        with patch.object(integrity, "load_artifact", wraps=_load):
            # Save via the real save_artifact (patched COURSES_DIR)
            for art in (toc, domain_model, blueprint, content_package):
                save_artifact(art)

            problems = integrity.check_referential_integrity("test-integrity")

    assert problems == [], "integrity.check_referential_integrity returned errors:\n" + "\n".join(
        problems
    )


def _patched_load(courses_dir: Path, course_id: str, artifact_type: str) -> dict | None:
    """Load an artifact from the patched courses_dir."""
    path = courses_dir / course_id / f"{artifact_type}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# Test 6: full pipeline plumbing, LLM mocked
# ===========================================================================


def test_full_pipeline_plumbing_llm_mocked(tmp_path):
    """Dry-run the full pipeline with:
      - orchestrator.COURSES_DIR -> tmp_path
      - llm.call -> raises (proves no live API call escapes)
      - steps.student_content.generate_asset -> fixture assets

    After run_pipeline completes, load the on-disk content_package and assert:
      - schema-valid v0.2
      - integrity.check_referential_integrity returns []
    """
    import llm  # noqa: PLC0415

    courses_tmp = tmp_path / "courses"
    course_id = "plumbing-test"

    brief = make_artifact(
        course_id,
        artifact_type="brief",
        produced_by_step="human",
        body={
            "subject": "Financial Risk Management",
            "audience": "PG",
            "level": "intermediate",
            "goals": "understand risk",
            "scope": "module 1",
        },
        inputs=[],
    )

    pipeline = [
        Step(
            name="structure",
            consumes=["brief"],
            produces=["domain_model", "toc"],
            run=steps.structure_step,
        ),
        Step(
            name="blueprint",
            consumes=["toc", "domain_model"],
            produces=["blueprint"],
            run=steps.blueprint_step,
        ),
        Step(
            name="student_content",
            consumes=["toc", "blueprint", "domain_model"],
            produces=["content_package"],
            run=steps.student_content_step,
        ),
    ]

    auto_approver = lambda step_name, produced: Decision(approved=True)  # noqa: E731

    def llm_must_not_be_called(*args, **kwargs):
        raise AssertionError(
            "llm.call was invoked — the pipeline made a live LLM call during tests!"
        )

    with (
        patch.object(orchestrator, "COURSES_DIR", courses_tmp),
        patch.object(llm, "call", side_effect=llm_must_not_be_called),
        patch("steps.student_content.generate_asset", side_effect=_fixture_generate_asset),
        patch(
            "steps.verification.verify_content_package",
            side_effect=_fixture_verify_content_package,
        ),
    ):
        run_pipeline(
            course_id=course_id,
            pipeline=pipeline,
            seed_artifacts={"brief": brief},
            approver=auto_approver,
        )

        # Verify schema validity
        cp_path = courses_tmp / course_id / "content_package.json"
        assert cp_path.exists(), "content_package.json was not written to disk"
        on_disk = json.loads(cp_path.read_text(encoding="utf-8"))
        schema_errors = validate_content_package(on_disk)
        assert schema_errors == [], "On-disk content_package has v0.2 schema errors:\n" + "\n".join(
            schema_errors
        )

        # Verify referential integrity
        _load = lambda cid, atype: _patched_load(courses_tmp, cid, atype)  # noqa: E731
        with patch.object(integrity, "load_artifact", wraps=_load):
            problems = integrity.check_referential_integrity(course_id)

    assert problems == [], "integrity.check_referential_integrity returned errors:\n" + "\n".join(
        problems
    )
