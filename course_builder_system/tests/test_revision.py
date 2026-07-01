from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from agents import revision, student_content
from steps import student_content_step


def _generation_inputs() -> dict:
    return student_content.load_generation_inputs("frm-demo")


def _asset(key: str, *, flagged: bool = False) -> dict:
    spec = student_content.resolve_asset_spec(
        student_content.ASSET_SPECS[key], _generation_inputs()
    )
    claim = {
        "id": "c1",
        "text": "A factual claim.",
        "source_id": None if flagged else "g1",
        "support": None if flagged else "supported",
        "supporting_excerpt": None if flagged else "evidence",
        "note": "Ungrounded" if flagged else "Supported",
    }
    return {
        "id": spec.asset_id,
        "type": spec.asset_type,
        "title": spec.title,
        "format": spec.format,
        "content": f"Original {spec.asset_type}",
        "claims": [claim],
        "sources": [] if flagged else ["g1"],
        "verification": {
            "supported": 0 if flagged else 1,
            "partial": 0,
            "unsupported": 0,
            "ungrounded": 1 if flagged else 0,
            "unattributed_found": [],
            "checked_at": "2026-06-30T00:00:00+00:00",
        },
        "file": None,
        "status": "done",
    }


def _package(*assets: dict) -> dict:
    return {"asset_vocabulary": [], "subtopics": [{"subtopic_id": "m1_s1", "assets": list(assets)}]}


def test_parse_revision_request_requires_an_explicit_target() -> None:
    with pytest.raises(ValueError, match="target the revision"):
        revision.parse_revision_request("make it better", [_asset("course_content")])


def test_parse_verifier_request_selects_only_flagged_assets() -> None:
    request = revision.parse_revision_request(
        "verifier: keep the prose concise",
        [_asset("course_content"), _asset("summary", flagged=True)],
    )

    assert request.asset_keys == ("summary",)
    assert request.feedback == "keep the prose concise"
    assert request.include_verifier_flags is True


def test_revise_content_package_preserves_unselected_assets() -> None:
    cc = _asset("course_content")
    summary = _asset("summary", flagged=True)
    package = _package(cc, summary)
    generated_summary = deepcopy(summary)
    generated_summary["content"] = "Revised summary"
    generated_summary["claims"] = []
    generated_summary["sources"] = []
    generated_summary["verification"] = {
        "supported": 0,
        "partial": 0,
        "unsupported": 0,
        "ungrounded": 0,
        "unattributed_found": [],
        "checked_at": None,
    }
    verified_summary = deepcopy(generated_summary)
    verified_summary["verification"]["checked_at"] = "2026-06-30T01:00:00+00:00"

    with (
        patch(
            "agents.revision.student_content.generate_asset_to_depth",
            return_value=generated_summary,
        ) as generate,
        patch("agents.revision.verification.verify_asset", return_value=verified_summary) as verify,
    ):
        revised = revision.revise_content_package(
            package,
            generation_inputs=_generation_inputs(),
            course_model=_generation_inputs()["course_model"],
            raw_feedback="verifier",
        )

    revised_assets = revised["subtopics"][0]["assets"]
    assert revised_assets[0] == cc
    assert revised_assets[1]["content"] == "Revised summary"
    assert package["subtopics"][0]["assets"][1]["content"] == "Original summary"
    assert generate.call_count == 1
    assert generate.call_args.args[0].asset_type == "summary"
    assert generate.call_args.args[0].asset_id == "m1_s1_summary"
    assert generate.call_args.kwargs["course_content"] == cc
    assert "Verifier findings" in generate.call_args.kwargs["feedback"]
    verify.assert_called_once()


def test_json_request_can_combine_human_and_verifier_targets() -> None:
    request = revision.parse_revision_request(
        '{"asset": "course_content", "feedback": "deepen examples", "verifier": true}',
        [_asset("course_content"), _asset("summary", flagged=True)],
    )

    assert request.asset_keys == ("course_content", "summary")
    assert request.feedback == "deepen examples"


def test_student_content_step_routes_rejection_to_targeted_revision() -> None:
    body = _package(_asset("course_content"), _asset("summary", flagged=True))
    existing = {"body": body}
    inputs = {
        **_generation_inputs(),
        "course_outcomes": {"body": {"outcomes": []}},
    }

    with (
        patch("steps.load_artifact", return_value=existing),
        patch("steps.revision.revise_content_package", return_value=body) as revise,
        patch(
            "steps.student_content.generate_asset_to_depth",
            side_effect=AssertionError("full regeneration should not run"),
        ),
    ):
        result = student_content_step(inputs, "verifier")

    assert result["content_package"]["body"] == body
    revise.assert_called_once()
    assert revise.call_args.args[3] == "verifier"
