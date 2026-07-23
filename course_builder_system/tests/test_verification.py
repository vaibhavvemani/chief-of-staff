"""Focused S3.1 tests for adversarial claim verification."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agents import verification
from orchestrator import make_artifact
from tests.schema_check import validate_content_package

CHECKED_AT = "2026-06-30T12:00:00+00:00"
EMPTY_VERIFICATION = {
    "supported": 0,
    "partial": 0,
    "unsupported": 0,
    "ungrounded": 0,
    "unattributed_found": [],
    "checked_at": None,
}


@pytest.fixture
def source_setup(tmp_path: Path) -> tuple[dict, dict[str, str]]:
    excerpts = {
        "supported": "Liquidity is the ability to meet obligations when due.",
        "partial": "Stress tests are part of sound liquidity risk management.",
    }
    source_path = tmp_path / "g1.md"
    source_path.write_text(
        f"# Test Source\n\n{excerpts['supported']}\n\n{excerpts['partial']}\n",
        encoding="utf-8",
    )
    domain_model = {
        "body": {
            "grounding_sources": [
                {
                    "category": "TEST",
                    "items": [
                        {
                            "id": "g1",
                            "name": "Test Source",
                            "file": str(source_path),
                        }
                    ],
                }
            ]
        }
    }
    return domain_model, excerpts


def _claim(claim_id: str, source_id: str | None = "g1") -> dict:
    return {
        "id": claim_id,
        "text": f"Claim text for {claim_id}.",
        "source_id": source_id,
        "support": None,
        "supporting_excerpt": None,
        "note": None,
    }


def _asset(*claims: dict, asset_id: str = "m1_s1_test") -> dict:
    sources = []
    for claim in claims:
        source_id = claim["source_id"]
        if source_id is not None and source_id not in sources:
            sources.append(source_id)
    return {
        "id": asset_id,
        "type": "course_content",
        "title": "Test Asset",
        "format": "markdown",
        "content": "Learner-facing content must remain unchanged.",
        "claims": list(claims),
        "sources": sources,
        "verification": copy.deepcopy(EMPTY_VERIFICATION),
        "file": None,
        "status": "done",
    }


def _response(verdicts: list[dict], *, ungrounded: int = 0) -> dict:
    return {
        "claim_verdicts": verdicts,
        "verification": {
            "supported": sum(item["support"] == "supported" for item in verdicts),
            "partial": sum(item["support"] == "partial" for item in verdicts),
            "unsupported": sum(item["support"] == "unsupported" for item in verdicts),
            "ungrounded": ungrounded,
            "unattributed_found": [],
        },
    }


def _llm_result(response: dict | None, text: str = "") -> SimpleNamespace:
    return SimpleNamespace(parsed=response, text=text or json.dumps(response))


def test_verification_schema_is_accepted_by_anthropic_transformer():
    transformed = verification.llm.anthropic.transform_schema(
        verification._verification_response_schema()
    )

    support = transformed["properties"]["claim_verdicts"]["items"]["properties"]["support"]
    assert support == {
        "type": "string",
        "enum": ["supported", "partial", "unsupported"],
    }


def test_verify_asset_accepts_registered_url_metadata_as_evidence(source_setup):
    domain_model, _excerpts = source_setup
    source = domain_model["body"]["grounding_sources"][0]["items"][0]
    source["url"] = "https://example.test/approved-guide"
    asset = _asset(
        {
            **_claim("source-url"),
            "text": "The approved guide is available at https://example.test/approved-guide.",
        }
    )
    response = _response(
        [
            {
                "claim_id": "source-url",
                "support": "supported",
                "supporting_excerpt": "URL: https://example.test/approved-guide",
                "note": "The registered source metadata supplies the exact URL.",
            }
        ]
    )

    with patch.object(
        verification.llm,
        "call",
        return_value=_llm_result(response),
    ) as mock_call:
        verified = verification.verify_asset(
            asset,
            domain_model,
            checked_at=CHECKED_AT,
        )

    assert verified["claims"][0]["support"] == "supported"
    assert "URL: https://example.test/approved-guide" in mock_call.call_args.args[0][0][
        "content"
    ]


def test_verify_asset_rejects_metadata_excerpt_for_substantive_claim(source_setup):
    domain_model, _excerpts = source_setup
    source = domain_model["body"]["grounding_sources"][0]["items"][0]
    source["url"] = "https://example.test/approved-guide"
    asset = _asset(
        {
            **_claim("substantive"),
            "text": (
                "The approved guide at https://example.test/approved-guide says "
                "plants should be watered twice daily."
            ),
        }
    )
    response = _response(
        [
            {
                "claim_id": "substantive",
                "support": "supported",
                "supporting_excerpt": "URL: https://example.test/approved-guide",
                "note": "The registered metadata contains the URL.",
            }
        ]
    )

    with patch.object(
        verification.llm,
        "call",
        return_value=_llm_result(response),
    ) as call:
        verified = verification.verify_asset(
            asset,
            domain_model,
            checked_at=CHECKED_AT,
        )

    assert call.call_count == 2
    assert verified["claims"][0]["support"] == "unsupported"
    assert verified["claims"][0]["supporting_excerpt"] is None


def test_verify_asset_rejects_prescriptive_title_as_body_evidence(source_setup):
    domain_model, _excerpts = source_setup
    source = domain_model["body"]["grounding_sources"][0]["items"][0]
    source["name"] = "Plants should be watered twice daily."
    asset = _asset(
        {
            **_claim("prescriptive-title"),
            "text": "Plants should be watered twice daily.",
        }
    )
    response = _response(
        [
            {
                "claim_id": "prescriptive-title",
                "support": "supported",
                "supporting_excerpt": "Title: Plants should be watered twice daily.",
                "note": "The registered metadata contains the exact title.",
            }
        ]
    )

    with patch.object(
        verification.llm,
        "call",
        return_value=_llm_result(response),
    ) as call:
        verified = verification.verify_asset(
            asset,
            domain_model,
            checked_at=CHECKED_AT,
        )

    assert call.call_count == 2
    assert verified["claims"][0]["support"] == "unsupported"
    assert verified["claims"][0]["supporting_excerpt"] is None


def test_verify_asset_annotates_all_verdicts_and_ungrounded(source_setup):
    domain_model, excerpts = source_setup
    original = _asset(
        _claim("supported"),
        _claim("partial"),
        _claim("unsupported"),
        _claim("ungrounded", None),
    )
    response = _response(
        [
            {
                "claim_id": "supported",
                "support": "supported",
                "supporting_excerpt": excerpts["supported"],
                "note": "The source directly states the claim.",
            },
            {
                "claim_id": "partial",
                "support": "partial",
                "supporting_excerpt": excerpts["partial"],
                "note": "The source supports only the narrower statement.",
            },
            {
                "claim_id": "unsupported",
                "support": "unsupported",
                "supporting_excerpt": None,
                "note": "The cited source does not establish this claim.",
            },
        ],
        ungrounded=1,
    )
    response["verification"]["unattributed_found"] = [
        "A significant uncatalogued date appears in the asset."
    ]

    with patch.object(
        verification.llm,
        "call",
        return_value=_llm_result(response),
    ) as mock_call:
        verified = verification.verify_asset(
            original,
            domain_model,
            checked_at=CHECKED_AT,
        )

    by_id = {claim["id"]: claim for claim in verified["claims"]}
    assert by_id["supported"]["support"] == "supported"
    assert by_id["partial"]["support"] == "partial"
    assert by_id["unsupported"]["support"] == "unsupported"
    assert by_id["unsupported"]["supporting_excerpt"] is None
    assert by_id["ungrounded"]["support"] is None
    assert by_id["ungrounded"]["supporting_excerpt"] is None
    assert by_id["ungrounded"]["note"] == verification.UNGROUNDED_NOTE
    assert verified["verification"] == {
        "supported": 1,
        "partial": 1,
        "unsupported": 1,
        "ungrounded": 1,
        "unattributed_found": ["A significant uncatalogued date appears in the asset."],
        "checked_at": CHECKED_AT,
    }
    assert verified["content"] == original["content"]
    assert verified["sources"] == original["sources"]
    assert original["verification"]["checked_at"] is None
    assert mock_call.call_count == 1
    assert "Test Source" in mock_call.call_args.args[0][0]["content"]


@pytest.mark.parametrize(
    ("verdicts", "defect"),
    [
        ([], "cover every attributed claim exactly once"),
        (
            [
                {
                    "claim_id": "c1",
                    "support": "unsupported",
                    "supporting_excerpt": None,
                    "note": "No support.",
                },
                {
                    "claim_id": "c1",
                    "support": "unsupported",
                    "supporting_excerpt": None,
                    "note": "Duplicate.",
                },
            ],
            "duplicate verdict",
        ),
        (
            [
                {
                    "claim_id": "unknown",
                    "support": "unsupported",
                    "supporting_excerpt": None,
                    "note": "Unknown.",
                }
            ],
            "unknown claim_id",
        ),
    ],
)
def test_verifier_conservatively_repairs_claim_id_coverage_after_retry(
    source_setup,
    verdicts,
    defect,
):
    domain_model, _ = source_setup
    response = _response(verdicts)
    # Keep the model-provided summary consistent so coverage is the failure.
    with patch.object(
        verification.llm,
        "call",
        return_value=_llm_result(response),
    ) as call:
        verified = verification.verify_asset(
            _asset(_claim("c1")),
            domain_model,
            checked_at=CHECKED_AT,
        )
    assert defect
    assert call.call_count == 2
    assert verified["claims"][0]["support"] == "unsupported"
    assert verified["claims"][0]["note"]


def test_verifier_rejects_inconsistent_summary_counts(source_setup):
    domain_model, _ = source_setup
    response = _response(
        [
            {
                "claim_id": "c1",
                "support": "unsupported",
                "supporting_excerpt": None,
                "note": "No evidence in the source.",
            }
        ]
    )
    response["verification"]["unsupported"] = 0

    with (
        patch.object(
            verification.llm,
            "call",
            return_value=_llm_result(response),
        ),
        pytest.raises(ValueError, match="does not reconcile"),
    ):
        verification.verify_asset(
            _asset(_claim("c1")),
            domain_model,
            checked_at=CHECKED_AT,
        )


@pytest.mark.parametrize(
    ("support", "excerpt"),
    [
        ("supported", "A paraphrase not present in the source."),
        ("partial", None),
        ("unsupported", "Should be null."),
    ],
)
def test_verifier_conservatively_downgrades_invalid_evidence_after_retry(
    source_setup,
    support,
    excerpt,
):
    domain_model, _ = source_setup
    response = _response(
        [
            {
                "claim_id": "c1",
                "support": support,
                "supporting_excerpt": excerpt,
                "note": "Evidence explanation.",
            }
        ]
    )
    with patch.object(
        verification.llm,
        "call",
        return_value=_llm_result(response),
    ) as call:
        verified = verification.verify_asset(
            _asset(_claim("c1")),
            domain_model,
            checked_at=CHECKED_AT,
        )

    assert call.call_count == 2
    assert verified["claims"][0]["support"] == "unsupported"
    assert verified["claims"][0]["supporting_excerpt"] is None
    assert "Deterministic fallback" in verified["claims"][0]["note"]


def test_verifier_retries_once_after_wrong_source_excerpt(source_setup):
    domain_model, excerpts = source_setup
    invalid = _response(
        [
            {
                "claim_id": "c1",
                "support": "supported",
                "supporting_excerpt": "Evidence copied from a different source.",
                "note": "Wrong source on first attempt.",
            }
        ]
    )
    corrected = _response(
        [
            {
                "claim_id": "c1",
                "support": "supported",
                "supporting_excerpt": excerpts["supported"],
                "note": "Exact evidence from the cited source.",
            }
        ]
    )

    with patch.object(
        verification.llm,
        "call",
        side_effect=[_llm_result(invalid), _llm_result(corrected)],
    ) as call:
        verified = verification.verify_asset(
            _asset(_claim("c1")),
            domain_model,
            checked_at=CHECKED_AT,
        )

    assert call.call_count == 2
    assert "failed deterministic validation" in call.call_args.args[0][0]["content"]
    assert verified["claims"][0]["support"] == "supported"


def test_verifier_rejects_unknown_input_source_before_calling_llm(source_setup):
    domain_model, _ = source_setup
    asset = _asset(_claim("c1", "g9"))
    with (
        patch.object(verification.llm, "call") as mock_call,
        pytest.raises(ValueError, match="unknown source_id"),
    ):
        verification.verify_asset(asset, domain_model, checked_at=CHECKED_AT)
    mock_call.assert_not_called()


def test_verifier_rejects_malformed_json_response(source_setup):
    domain_model, _ = source_setup
    with (
        patch.object(
            verification.llm,
            "call",
            return_value=_llm_result(None, text="not-json"),
        ),
        pytest.raises(ValueError, match="invalid JSON"),
    ):
        verification.verify_asset(
            _asset(_claim("c1")),
            domain_model,
            checked_at=CHECKED_AT,
        )


def test_verify_content_package_calls_per_asset_and_remains_schema_valid(source_setup):
    domain_model, _ = source_setup
    asset_one = _asset(asset_id="m1_s1_a")
    asset_two = _asset(asset_id="m1_s1_b")
    asset_two["type"] = "summary"
    package = make_artifact(
        "test-course",
        "content_package",
        "student_content",
        body={
            "asset_vocabulary": ["course_content", "summary"],
            "subtopics": [
                {
                    "subtopic_id": "m1_s1",
                    "assets": [asset_one, asset_two],
                }
            ],
        },
        inputs=["course_model", "blueprint", "course_outcomes"],
        schema_version="0.2",
    )
    empty_response = _response([])

    with patch.object(
        verification.llm,
        "call",
        side_effect=[_llm_result(empty_response), _llm_result(empty_response)],
    ) as mock_call:
        verified = verification.verify_content_package(
            package,
            domain_model,
            checked_at=CHECKED_AT,
        )

    assert mock_call.call_count == 2
    assert all(
        asset["verification"]["checked_at"] == CHECKED_AT
        for asset in verified["body"]["subtopics"][0]["assets"]
    )
    assert validate_content_package(verified) == []
