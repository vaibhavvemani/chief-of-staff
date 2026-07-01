"""Focused tests for the Phase 1 score/blind/ratify/trend workflow."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import llm
from evals import compare


def _asset(asset_type: str, *, verified: bool = True, label: str = "version") -> dict:
    ids = {
        "course_content": "m1_s1_cc",
        "learning_objectives": "m1_s1_lo",
        "summary": "m1_s1_summary",
        "case_study": "m1_s1_case",
        "assessment": "m1_s1_assess",
    }
    support = "supported" if verified else None
    asset = {
        "id": ids[asset_type],
        "type": asset_type,
        "title": asset_type.replace("_", " ").title(),
        "format": (
            "pptx" if asset_type in {"course_content", "case_study", "assessment"} else "docx"
        ),
        "content": f"## {label}\n\nComplete {asset_type} content.",
        "claims": [
            {
                "id": f"{ids[asset_type]}_c1",
                "text": "A supported factual claim.",
                "source_id": "g1",
                "support": support,
                "supporting_excerpt": "source evidence" if verified else None,
                "note": None,
            }
        ],
        "sources": ["g1"],
        "verification": {
            "supported": 1 if verified else 0,
            "partial": 0,
            "unsupported": 0,
            "ungrounded": 0,
            "unattributed_found": [],
            "checked_at": "2026-06-30T00:00:00+00:00" if verified else None,
        },
        "file": None,
        "status": "done",
    }
    if asset_type == "assessment":
        asset["solution"] = "Teacher answer key"
    return asset


def _package(*, verified: bool = True, label: str = "version") -> dict:
    return {
        "course_id": "test",
        "artifact_type": "content_package",
        "produced_by_step": "student_content",
        "schema_version": "0.2",
        "status": "approved",
        "revision": 0,
        "revision_note": None,
        "inputs": ["toc", "blueprint", "domain_model"],
        "updated_at": "2026-06-30T00:00:00+00:00",
        "body": {
            "asset_vocabulary": list(compare.ASSET_ORDER),
            "subtopics": [
                {
                    "subtopic_id": "m1_s1",
                    "assets": [
                        _asset(asset_type, verified=verified, label=label)
                        for asset_type in compare.CORE_ASSET_TYPES
                    ],
                }
            ],
        },
    }


def _write_packages(tmp_path: Path, *, verified: bool = True) -> tuple[Path, Path]:
    agent_path = tmp_path / "agent.json"
    gold_path = tmp_path / "gold.json"
    agent_path.write_text(json.dumps(_package(verified=verified, label="candidate one")))
    gold_path.write_text(json.dumps(_package(verified=True, label="candidate two")))
    return agent_path, gold_path


def _complete_packet(packet: dict, *, score: int = 6, minutes: float = 5) -> dict:
    completed = copy.deepcopy(packet)
    completed["human_review"].update(
        {
            "reviewer": "Blind Reviewer",
            "started_at": "2026-06-30T10:00:00+00:00",
            "completed_at": "2026-06-30T10:50:00+00:00",
            "ratified": True,
        }
    )
    for row in completed["assets"]:
        for candidate in row["candidates"].values():
            candidate["rating"] = {
                "scores": {dimension: score for dimension in compare.DIMENSIONS},
                "review_minutes": minutes,
                "edit_extent": "light",
                "notes": "Minor wording only.",
                "ratified": True,
            }
    return completed


def test_scorecard_has_deterministic_evidence_and_never_auto_passes(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)

    with patch("evals.compare.llm.call", side_effect=AssertionError("network call")):
        scorecard = compare.build_scorecard(agent_path, gold_path)

    assert scorecard["gate"]["status"] == "pending_human_review"
    assert scorecard["gate"]["passed"] is False
    assert scorecard["human_review"] is None
    assert scorecard["inputs"]["agent_sha256"]
    assert "prompt_git_sha" in scorecard
    assert scorecard["verifier_stats"]["supported"] == 5

    course_content = next(
        row for row in scorecard["assets"] if row["asset_type"] == "course_content"
    )
    dimensions = course_content["dimensions"]
    assert dimensions["factual_accuracy"]["score"] == 10
    assert dimensions["source_attribution"]["score"] == 10
    assert dimensions["asset_completeness"]["score"] == 10
    assert dimensions["factual_accuracy"]["evidence"]["summary_consistent"] is True
    assert dimensions["coverage"]["score"] is None
    assert dimensions["pedagogical_clarity"]["status"] == "pending_human"
    assert dimensions["review_time"]["score"] is None


def test_unverified_claims_score_as_explicit_mechanical_blockers(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path, verified=False)
    scorecard = compare.build_scorecard(agent_path, gold_path)

    assert len(scorecard["gate"]["provisional_mechanical_blockers"]) == 10
    for row in scorecard["assets"]:
        assert row["dimensions"]["factual_accuracy"]["score"] == 1
        assert row["dimensions"]["source_attribution"]["score"] == 1
        assert row["dimensions"]["factual_accuracy"]["evidence"]["checked_at"] is None


def test_ungrounded_claim_with_null_support_is_not_a_pending_verdict(tmp_path):
    agent = _package(verified=True, label="candidate one")
    course_content = agent["body"]["subtopics"][0]["assets"][0]
    course_content["claims"].append(
        {
            "id": "m1_s1_cc_c2",
            "text": "A deliberately ungrounded claim.",
            "source_id": None,
            "support": None,
            "supporting_excerpt": None,
            "note": "No source was supplied.",
        }
    )
    course_content["verification"]["ungrounded"] = 1
    agent_path = tmp_path / "agent.json"
    gold_path = tmp_path / "gold.json"
    agent_path.write_text(json.dumps(agent))
    gold_path.write_text(json.dumps(_package(verified=True, label="candidate two")))

    scorecard = compare.build_scorecard(agent_path, gold_path)
    row = next(asset for asset in scorecard["assets"] if asset["asset_type"] == "course_content")
    evidence = row["dimensions"]["factual_accuracy"]["evidence"]

    assert evidence["pending_verdicts"] == 0
    assert evidence["ungrounded"] == 1
    assert evidence["summary_consistent"] is True
    assert row["dimensions"]["factual_accuracy"]["score"] < 10


def test_optional_llm_judge_is_only_a_validated_proposal(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)
    assessments = [
        {
            "asset_type": asset_type,
            "coverage": {"score": 7, "comparison": "exceeds", "evidence": "More depth."},
            "house_style": {"score": 6, "comparison": "matches", "evidence": "Same tone."},
        }
        for asset_type in compare.CORE_ASSET_TYPES
    ]
    result = llm.LLMResult(
        text=json.dumps({"assessments": assessments}),
        raw={},
        usage={},
        model="mock-judge",
        prompt_hash="judge-hash",
        cache_hit=False,
        parsed={"assessments": assessments},
    )

    with patch("evals.compare.llm.call", return_value=result) as mocked:
        scorecard = compare.build_scorecard(agent_path, gold_path, use_llm_judge=True)

    mocked.assert_called_once()
    assert scorecard["llm_judge"]["prompt_hash"] == "judge-hash"
    assert scorecard["assets"][0]["dimensions"]["coverage"] == {
        "score": 7,
        "status": "llm_proposal_pending_human_ratification",
        "method": "LLM head-to-head proposal; manual asset anchors score 6",
        "evidence": {"comparison": "exceeds", "rationale": "More depth."},
    }
    assert scorecard["gate"]["status"] == "pending_human_review"


def test_llm_judge_and_blind_packet_receive_approved_scope(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)
    course_model_path = tmp_path / "course_model.json"
    course_model_path.write_text(
        json.dumps(
            {
                "body": {
                    "course_metadata": {
                        "course_title": "Test Course",
                        "subject": "Testing",
                        "audience_summary": "Reviewers",
                        "level": "intermediate",
                    },
                    "modules": [
                        {
                            "id": "m1",
                            "title": "Module",
                            "context": {"purpose": "Teach tests."},
                            "subtopics": [
                                {
                                    "id": "m1_s1",
                                    "title": "Scope",
                                    "context": {
                                        "purpose": "Approved scope.",
                                        "in_scope": ["included"],
                                        "out_of_scope": ["excluded"],
                                    },
                                    "concepts": [],
                                    "coverage_requirements": [],
                                }
                            ],
                        }
                    ],
                }
            }
        )
    )
    assessments = [
        {
            "asset_type": asset_type,
            "coverage": {"score": 6, "comparison": "matches", "evidence": "In scope."},
            "house_style": {"score": 6, "comparison": "matches", "evidence": "Matches."},
        }
        for asset_type in compare.CORE_ASSET_TYPES
    ]
    result = llm.LLMResult(
        text="",
        raw={},
        usage={},
        model="mock-judge",
        prompt_hash="scope-hash",
        cache_hit=False,
        parsed={"assessments": assessments},
    )

    with patch("evals.compare.llm.call", return_value=result) as mocked:
        scorecard = compare.build_scorecard(
            agent_path,
            gold_path,
            use_llm_judge=True,
            course_model_path=course_model_path,
        )
    prompt = mocked.call_args.args[0][0]["content"]
    assert '"out_of_scope": [' in prompt
    assert '"excluded"' in prompt
    assert scorecard["inputs"]["course_model_sha256"]

    packet, mapping = compare.build_blind_packet(
        agent_path,
        gold_path,
        course_model_path=course_model_path,
    )
    assert packet["evaluation_context"]["subtopic"]["context"]["out_of_scope"] == [
        "excluded"
    ]
    assert mapping["inputs"]["course_model_sha256"]


def test_blind_packet_is_deterministic_and_keeps_mapping_separate(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)
    packet_one, mapping_one = compare.build_blind_packet(agent_path, gold_path)
    packet_two, mapping_two = compare.build_blind_packet(agent_path, gold_path)

    assert mapping_one == mapping_two
    assert packet_one["packet_id"] == packet_two["packet_id"]
    assert packet_one["mapping_commitment"] == mapping_one["mapping_commitment"]
    assert "assignments" not in packet_one
    assert set(mapping_one["assignments"]) == set(compare.CORE_ASSET_TYPES)
    for row in packet_one["assets"]:
        assert set(row["candidates"]) == {"A", "B"}
        assert set(row["candidates"]["A"]["rating"]["scores"]) == set(compare.DIMENSIONS)
        assert "id" not in row["candidates"]["A"]["asset"]


def test_ratification_enforces_core_scores_time_and_light_edits(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)
    scorecard = compare.build_scorecard(agent_path, gold_path)
    packet, mapping = compare.build_blind_packet(agent_path, gold_path)
    completed = _complete_packet(packet, score=6, minutes=5)

    final = compare.ratify_scorecard(scorecard, completed, mapping)

    assert final["gate"]["passed"] is True
    assert final["gate"]["status"] == "passed"
    assert final["human_review"]["core_agent_review_minutes"] == 25
    assert all(
        row["dimensions"]["pedagogical_clarity"]["status"] == "human_ratified"
        for row in final["assets"]
        if row["required_for_gate"]
    )

    low_score = _complete_packet(packet, score=6, minutes=5)
    first = low_score["assets"][0]
    agent_label = next(
        label
        for label, origin in mapping["assignments"][first["asset_type"]].items()
        if origin == "agent"
    )
    first["candidates"][agent_label]["rating"]["scores"]["coverage"] = 5
    failed_score = compare.ratify_scorecard(scorecard, low_score, mapping)
    assert failed_score["gate"]["passed"] is False
    assert "below 6" in " ".join(failed_score["gate"]["reasons"])

    slow = _complete_packet(packet, score=6, minutes=13)
    failed_time = compare.ratify_scorecard(scorecard, slow, mapping)
    assert failed_time["gate"]["passed"] is False
    assert ">60" in " ".join(failed_time["gate"]["reasons"])


def test_ratification_rejects_incomplete_or_tampered_review(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)
    scorecard = compare.build_scorecard(agent_path, gold_path)
    packet, mapping = compare.build_blind_packet(agent_path, gold_path)

    with pytest.raises(ValueError, match="ratified"):
        compare.ratify_scorecard(scorecard, packet, mapping)

    completed = _complete_packet(packet)
    tampered = copy.deepcopy(mapping)
    prior = tampered["assignments"]["course_content"]["A"]
    tampered["assignments"]["course_content"]["A"] = (
        "agent" if prior == "gold" else "gold"
    )
    with pytest.raises(ValueError, match="commitment"):
        compare.ratify_scorecard(scorecard, completed, tampered)


def test_trend_orders_runs_and_preserves_gate_outcomes(tmp_path):
    agent_path, gold_path = _write_packages(tmp_path)
    first = compare.build_scorecard(agent_path, gold_path)
    second = copy.deepcopy(first)
    first["timestamp"] = "2026-06-29T00:00:00+00:00"
    first["run_id"] = "first"
    second["timestamp"] = "2026-06-30T00:00:00+00:00"
    second["run_id"] = "second"
    second["gate"] = {"status": "passed", "passed": True}

    trend = compare.trend_scorecards([second, first])

    assert [row["run_id"] for row in trend["runs"]] == ["first", "second"]
    assert trend["runs"][1]["gate_passed"] is True
    assert trend["runs"][0]["core_mechanical_average"] == 10
