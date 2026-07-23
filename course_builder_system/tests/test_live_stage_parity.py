from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import acceptance
import api.services.artifact_repository as repository_module
import llm
import steps
from agents import intake
from agents.live_stages import LiveStageImplementations, _PlannedResearchProvider
from agents.source_repair import LiveSourceRepairProvider, RepairResearchScope
from api.main import create_app
from api.services.content_repair_service import ContentRepairService
from implementation_registry import (
    REQUIRED_STEP_NAMES,
    StageImplementationRegistry,
    build_default_implementation_registry,
)
from orchestrator import course_dir
from research_adapter import CompetitorOutline, MockResearchProvider, SearchResult
from schema_validation import validate_json_schema
from source_store import SourceStore

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_TOPICS = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "live_stage_eval_topics.json").read_text(
        encoding="utf-8"
    )
)


class EvalStructuredProvider:
    provider_name = "eval-provider"
    model_name = "eval-structured-v1"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def ready(self) -> bool:
        return True

    def generate(
        self,
        *,
        stage: str,
        system: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        max_tokens: int,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "stage": stage,
                "system": system,
                "payload": deepcopy(payload),
                "schema": deepcopy(schema),
                "max_tokens": max_tokens,
                "use_cache": use_cache,
            }
        )

        def validated(value: dict[str, Any]) -> dict[str, Any]:
            issues = validate_json_schema(value, schema)
            assert not issues, issues
            return value

        if stage == "brief":
            if "gaps" in payload:
                allowed = payload["allowed_fields"][: payload["maximum_questions"]]
                return validated({
                    "questions": [
                        {
                            "field": field,
                            "prompt": f"What boundary should {field.replace('_', ' ')} use?",
                            "rationale": "This resolves one current Brief ambiguity.",
                        }
                        for field in allowed
                    ]
                })
            subject = payload["subject_request"]["subject"]
            constraints = payload["subject_request"].get("constraints", [])
            must_have_topics = [
                item.removeprefix("Must include: ").rstrip(".")
                for item in constraints
                if item.startswith("Must include: ")
            ] or ["setup", "routine practice", "troubleshooting"]
            audience = next(
                (
                    item.removeprefix("Audience: ").rstrip(".")
                    for item in constraints
                    if item.startswith("Audience: ")
                ),
                "Independent adult beginners",
            )
            excluded = next(
                (
                    item.removeprefix("Exclude: ").rstrip(".")
                    for item in constraints
                    if item.startswith("Exclude: ")
                ),
                "Professional certification or expert-only work",
            )
            return validated({
                "updates": {
                    "course_title": f"{subject}: practical essentials",
                    "purpose": f"Build a safe, repeatable beginner workflow for {subject}.",
                    "audience": audience,
                    "level": "beginner",
                    "prior_knowledge": "No prior specialist knowledge",
                    "in_scope": [f"Core decisions for {subject}", "Practice and troubleshooting"],
                    "out_of_scope": [excluded],
                    "must_have_topics": must_have_topics,
                    "duration": "3 hours",
                    "modality": "self_paced",
                    "language": "English",
                    "jurisdiction": None,
                    "assessment_expectations": "One applied checklist",
                    "live_teaching_constraints": None,
                    "tools_or_equipment": "Ordinary beginner equipment",
                    "freshness_requirement": None,
                    "accessibility_requirements": None,
                }
            })
        if stage == "outcomes":
            if "targets" in payload:
                return validated({
                    "outcomes": [
                        {
                            "target_id": item["id"],
                            "statement": (
                                f"Apply and explain {item['statement'].rstrip('.')} safely."
                            ),
                            "cognitive_level": "apply",
                            "evidence": "A completed decision checklist with a short rationale",
                            "priority": item["priority"],
                        }
                        for item in payload["targets"]
                    ]
                })
            topics = payload["brief"]["must_have_topics"]
            return validated({
                "outcomes": [
                    {
                        "statement": f"Apply the essential decisions for {topic}.",
                        "cognitive_level": "apply",
                        "evidence": f"A completed {topic} decision checklist",
                        "priority": "core",
                    }
                    for topic in topics[:3]
                ]
            })
        if stage == "research":
            subject = payload["brief"]["subject"]
            return validated({
                "competitor_query": f"{subject} beginner course outline",
                "competitor_fallback_query": f"{subject} course curriculum modules",
                "source_query": f"{subject} authoritative practical guidance",
            })
        if stage == "course-model":
            return validated({
                "subtopics": [
                    {
                        "target_id": item["id"],
                        "title": f"{item['title']} — guided practice",
                        "purpose": (
                            f"{item['purpose'].rstrip('.')} through a bounded learner "
                            "decision."
                        ),
                        "in_scope": list(item["in_scope"]) or ["Beginner practice"],
                        "out_of_scope": list(item["out_of_scope"]),
                    }
                    for item in payload["targets"]
                ]
            })
        if stage == "blueprint":
            context_by_id = {
                item["id"]: item for item in payload["course_model_subtopics"]
            }
            plans = []
            for item in payload["targets"]:
                context = context_by_id[item["subtopic_id"]]
                current_assets = [
                    asset["asset_type"]
                    for asset in item.get("asset_plan", [])
                    if asset.get("selection_status") == "selected"
                ]
                asset_types = current_assets or ["course_content", "activities"]
                if payload["category"] == "structure":
                    semantic_text = json.dumps(context, ensure_ascii=False).lower()
                    asset_types = (
                        ["course_content", "case_study", "assessment"]
                        if "troubleshoot" in semantic_text
                        else ["course_content", "activities"]
                    )
                current_depth = item.get("depth_budget", {})
                minutes = int(current_depth.get("target_learning_minutes", 20))
                if payload["category"] == "depth":
                    minutes += 5
                plans.append(
                    {
                        "subtopic_id": item["subtopic_id"],
                        "asset_types": asset_types,
                        "depth": {
                            "level": current_depth.get("level", "introductory"),
                            "target_learning_minutes": minutes,
                            "required_example_count": int(
                                current_depth.get("required_example_count", 1)
                            ),
                            "case_depth": current_depth.get("case_depth", "brief"),
                            "assessment_complexity": current_depth.get(
                                "assessment_complexity", "application"
                            ),
                        },
                    }
                )
            return validated({"plans": plans})
        if stage == "lesson-plan":
            if payload["category"] == "sequence":
                target_ids = {item["id"] for item in payload["targets"]}
                anchors = [
                    subtopic_id
                    for session in payload["sessions"]
                    for subtopic_id in session["subtopic_ids"]
                    if subtopic_id not in target_ids
                ]
                return validated({
                    "placements": [
                        {
                            "target_id": item["id"],
                            "after_subtopic_id": anchors[-1],
                        }
                        for item in payload["targets"]
                    ]
                })
            return validated({
                "modes": [
                    {
                        "subtopic_id": item["id"],
                        "mode": (
                            "live"
                            if "assessment" in item["selected_asset_types"]
                            else "self_study"
                        ),
                    }
                    for item in payload["targets"]
                ]
            })
        raise AssertionError(f"unexpected eval stage: {stage}")


class NotReadyProvider(EvalStructuredProvider):
    def ready(self) -> bool:
        return False


class FailingProvider(EvalStructuredProvider):
    def generate(self, **_kwargs: Any) -> dict[str, Any]:
        raise llm.LLMError("eval provider failed without a usable proposal")


def _topic_research_provider(topic: dict[str, Any]) -> MockResearchProvider:
    subject = topic["subject"]
    topic_text = ", ".join(topic["must_have_topics"])
    results: list[SearchResult] = []
    outlines: dict[str, CompetitorOutline] = {}
    pages: dict[str, str] = {}
    for index, label in enumerate(("Foundations", "Practice", "Troubleshooting"), start=1):
        result_id = f"comp_{index}"
        locator = f"https://curriculum.example.test/{topic['course_id']}/{index}"
        results.append(
            SearchResult(
                id=result_id,
                title=f"{subject} {label} course",
                locator=locator,
                snippet=f"Beginner {subject} outline covering {topic_text}.",
            )
        )
        outlines[result_id] = CompetitorOutline(
            id=result_id,
            provider=f"Provider {index}",
            offering=f"{subject} {label}",
            locator=locator,
            audience=topic["audience"],
            level="beginner",
            duration="2 hours",
            delivery_format="self-paced",
            assessment_approach="applied checklist",
            outline_status="usable",
            outline_labels=tuple(topic["must_have_topics"]),
        )
        pages[locator] = f"Course outline for {subject}: {topic_text}."
    for index in range(1, 4):
        source_id = f"source_{index}"
        locator = f"https://guidance.example.test/{topic['course_id']}/{index}"
        results.append(
            SearchResult(
                id=source_id,
                title=f"{subject} practical guidance {index}",
                locator=locator,
                snippet=f"Authoritative beginner guidance for {subject}.",
            )
        )
        pages[locator] = (
            f"Practical evidence for {subject}: {topic_text}. Use a repeatable workflow, "
            "observe the result, and change one variable at a time."
        )
    return MockResearchProvider(search_results=results, pages=pages, outlines=outlines)


def _approve(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact["status"] = "approved"
    return artifact


@pytest.mark.parametrize("topic", EVAL_TOPICS, ids=lambda item: item["course_id"])
def test_live_stage_contracts_pass_on_two_unrelated_topics(
    topic: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    provider = EvalStructuredProvider()
    live = LiveStageImplementations(
        model=provider,
        research_provider_factory=lambda: _topic_research_provider(topic),
    )
    subject = intake.subject_request_artifact(
        subject=topic["subject"],
        description=(
            f"A practical course for {topic['audience']} covering "
            + ", ".join(topic["must_have_topics"])
            + "."
        ),
        constraints=[
            f"Audience: {topic['audience']}.",
            *[f"Must include: {item}." for item in topic["must_have_topics"]],
            f"Exclude: {topic['excluded']}.",
        ],
        course_id=topic["course_id"],
    )
    brief = _approve(live.intake({"subject_request": subject}, None)["brief"])
    outcomes = _approve(live.course_outcomes({"brief": brief}, None)["course_outcomes"])
    dossier = _approve(
        live.research({"brief": brief, "course_outcomes": outcomes}, None)[
            "research_dossier"
        ]
    )
    capture_provider = _topic_research_provider(topic)
    capture_store = SourceStore(course_dir(topic["course_id"]) / "sources")
    for candidate in dossier["body"]["source_candidates"][:2]:
        fetched = capture_provider.fetch(candidate["locator"])
        assert fetched.ok and fetched.content
        candidate["content_ref"] = capture_store.persist(
            course_id=topic["course_id"],
            source_id=candidate["id"],
            content=fetched.content,
            locator=candidate["locator"],
        ).content_ref
    registry = _approve(
        steps.source_selection_step({"research_dossier": dossier}, None)[
            "approved_source_registry"
        ]
    )
    model_inputs = {
        "brief": brief,
        "course_outcomes": outcomes,
        "research_dossier": dossier,
        "approved_source_registry": registry,
    }
    course_model = _approve(live.structure(model_inputs, None)["course_model"])
    blueprint = _approve(live.blueprint({"course_model": course_model}, None)["blueprint"])
    generated_asset_ids: list[str] = []
    verified_asset_ids: list[str] = []

    def generate_asset(*args: Any, **kwargs: Any) -> dict[str, Any]:
        asset = acceptance.deterministic_generate_asset(*args, **kwargs)
        generated_asset_ids.append(asset["id"])
        return asset

    def verify_package(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verified = acceptance.deterministic_verify_content_package(*args, **kwargs)
        verified_asset_ids.extend(
            asset["id"]
            for subtopic in verified["subtopics"]
            for asset in subtopic["assets"]
        )
        return verified

    content = steps.make_student_content_step(
        asset_generator=generate_asset,
        package_verifier=verify_package,
        asset_verifier=acceptance.deterministic_verify_asset,
    )(
        {
            "course_model": course_model,
            "blueprint": blueprint,
            "course_outcomes": outcomes,
        },
        None,
    )["content_package"]
    content = _approve(content)
    lesson = live.lesson_plan(
        {
            "content_package": content,
            "blueprint": blueprint,
            "course_model": course_model,
        },
        None,
    )["lesson_plan"]

    assert brief["course_id"] == topic["course_id"]
    assert brief["body"]["audience"] == topic["audience"]
    assert brief["body"]["out_of_scope"] == [topic["excluded"]]
    assert brief["body"]["must_have_topics"] == topic["must_have_topics"]
    provenance = {item["field"]: item for item in brief["body"]["provenance"]}
    assert provenance["must_have_topics"] == {
        "field": "must_have_topics",
        "source": "inferred",
        "confidence": "needs_review",
    }
    assert "must_have_topics" not in brief["body"]["intake_state"]["explicit_fields"]
    assert len(outcomes["body"]["outcomes"]) == 3
    assert len(dossier["body"]["competitor_findings"]) >= 3
    assert registry["body"]["decision"]["approved_ids"]
    approved_ids = set(registry["body"]["decision"]["approved_ids"])
    assert approved_ids == {
        item["id"] for item in registry["body"]["source_registry"]
    }
    assert all(
        item["id"]
        for module in course_model["body"]["modules"]
        for item in module["subtopics"]
    )
    assert all(
        any(
            asset["asset_type"] == "course_content"
            and asset["selection_status"] == "selected"
            for asset in plan["asset_plan"]
        )
        for plan in blueprint["body"]["subtopic_plans"]
    )
    expected_ids = [
        item["id"]
        for module in course_model["body"]["modules"]
        for item in module["subtopics"]
    ]
    assert lesson["body"]["coverage_summary"]["covered_subtopic_ids"] == expected_ids
    assert generated_asset_ids
    assert sorted(generated_asset_ids) == sorted(verified_asset_ids)
    subtopics_by_id = {
        item["id"]: item
        for module in course_model["body"]["modules"]
        for item in module["subtopics"]
    }
    for subtopic in content["body"]["subtopics"]:
        routed = set(subtopics_by_id[subtopic["subtopic_id"]]["approved_source_ids"])
        assert routed and routed <= approved_ids
        for asset in subtopic["assets"]:
            assert set(asset["sources"]) <= routed
            assert all(claim["source_id"] in asset["sources"] for claim in asset["claims"])
            assert all(claim["support"] == "supported" for claim in asset["claims"])
    serialized_model = json.dumps(course_model["body"], ensure_ascii=False).lower()
    assert all(item.lower() in serialized_model for item in topic["must_have_topics"])
    assert topic["excluded"].lower() in serialized_model
    if any("troubleshoot" in item.lower() for item in topic["must_have_topics"]):
        assert any(
            {
                asset["asset_type"]
                for asset in plan["asset_plan"]
                if asset["selection_status"] == "selected"
            }
            >= {"course_content", "case_study", "assessment"}
            for plan in blueprint["body"]["subtopic_plans"]
            if "troubleshoot"
            in json.dumps(subtopics_by_id[plan["subtopic_id"]], ensure_ascii=False).lower()
        )
    assert [call["stage"] for call in provider.calls] == [
        "brief",
        "outcomes",
        "research",
        "course-model",
        "blueprint",
        "lesson-plan",
    ]
    blueprint_call = next(call for call in provider.calls if call["stage"] == "blueprint")
    assert all(
        item["purpose"] and item["coverage_requirements"] and item["approved_sources"]
        for item in blueprint_call["payload"]["course_model_subtopics"]
    )
    lesson_call = next(call for call in provider.calls if call["stage"] == "lesson-plan")
    assert all(
        item["purpose"]
        and item["coverage_requirements"]
        and item["selected_asset_types"]
        and item["current_placement"]["duration_minutes"]
        for item in lesson_call["payload"]["targets"]
    )
    serialized = json.dumps(
        {"brief": brief["body"], "outcomes": outcomes["body"]},
        ensure_ascii=False,
    ).lower()
    other_subjects = {
        item["subject"].lower()
        for item in EVAL_TOPICS
        if item["course_id"] != topic["course_id"]
    }
    assert all(other not in serialized for other in other_subjects)


def test_registry_is_explicit_and_live_failure_never_falls_back() -> None:
    registry = build_default_implementation_registry(model_provider=NotReadyProvider())
    assert set(registry.selection("deterministic").steps) == REQUIRED_STEP_NAMES
    assert set(registry.selection("live").steps) == REQUIRED_STEP_NAMES
    assert registry.resolve("live", "student_content") is steps.student_content_step
    with pytest.raises(llm.ProviderNotReady, match="requires configured"):
        registry.assert_mode_ready("live", "outcomes")
    with pytest.raises(ValueError, match="unknown stage-run mode"):
        registry.selection("automatic")

    with pytest.raises(ValueError, match="registry mismatch"):
        StageImplementationRegistry(
            deterministic={},
            live={},
            live_readiness=lambda: {"ready": True},
        )


@pytest.mark.parametrize(
    ("claim", "classification", "blocking"),
    [
        ({"source_id": None, "support": None}, "missing_attribution", True),
        ({"source_id": "src1", "support": "partial"}, "human_review", False),
        ({"source_id": "src1", "support": "unsupported"}, "insufficient_evidence", True),
        (
            {"source_id": "src1", "support": "unsupported", "note": "Contradicts source"},
            "likely_content_error",
            True,
        ),
    ],
)
def test_live_content_boundary_preserves_repair_classifications(
    claim: dict[str, Any],
    classification: str,
    blocking: bool,
) -> None:
    actual, _reason, _recommendation, actual_blocking = (
        ContentRepairService._classify_claim(claim)
    )
    assert actual == classification
    assert actual_blocking is blocking


def test_live_source_repair_provider_bounds_and_extracts_candidates() -> None:
    topic = EVAL_TOPICS[0]
    provider = LiveSourceRepairProvider(
        _topic_research_provider(topic),
        max_content_chars=120,
    )
    candidates = provider.research(
        RepairResearchScope(
            repair_id="repair_1",
            subtopic_id="m1_s1",
            asset_id="m1_s1_cc",
            claim_id="cl1",
            finding_id="cl1",
            evidence_gap="Need a focused practical source.",
        ),
        limit=20,
    )

    assert 1 <= len(candidates) <= 3
    assert all(candidate.id.startswith("repair_src_") for candidate in candidates)
    assert all(candidate.source_type == "live web source" for candidate in candidates)
    assert all(candidate.content and len(candidate.content) <= 120 for candidate in candidates)


def _seed_acceptance_course(app: Any, course_id: str, *, draft_stage: str) -> None:
    artifact_types = {
        "outcomes": {"course_outcomes"},
        "course-model": {"course_model"},
        "blueprint": {"blueprint"},
        "lesson-plan": {"lesson_plan"},
    }[draft_stage]
    fixture_root = (
        REPO_ROOT
        / "examples"
        / "acceptance"
        / "coffee-acceptance"
        / "course_artifacts"
    )
    for path in fixture_root.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        artifact["status"] = "draft" if artifact["artifact_type"] in artifact_types else "approved"
        app.state.repository.save(artifact)


def _wait_for_job(client: TestClient, job_url: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(job_url).json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("live revision job did not finish")


def _record_map(stage: str, artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    body = artifact["body"]
    if stage == "outcomes":
        return {item["id"]: item for item in body["outcomes"]}
    if stage == "course-model":
        return {
            item["id"]: item
            for module in body["modules"]
            for item in module["subtopics"]
        }
    if stage == "blueprint":
        return {item["subtopic_id"]: item for item in body["subtopic_plans"]}
    if stage == "lesson-plan":
        return {
            cover["subtopic_id"]: cover
            for session in body["sessions"]
            for cover in session["covers"]
        }
        raise AssertionError(stage)


def test_live_research_uses_bounded_fallback_and_ranks_course_results() -> None:
    class RecordingProvider:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def search(self, query: str, *, limit: int) -> list[SearchResult]:
            self.queries.append(query)
            if query == "primary":
                return [
                    SearchResult(
                        id=f"guide_{index}",
                        title=f"Practical guide {index}",
                        locator=f"https://guides.test/{index}",
                        snippet="General article",
                    )
                    for index in range(limit)
                ]
            if query == "fallback":
                return [
                    SearchResult(
                        id=f"course_{index}",
                        title=f"Public Course Curriculum {index}",
                        locator=f"https://courses.test/{index}/syllabus",
                        snippet="Public curriculum",
                    )
                    for index in range(3)
                ]
            return [
                SearchResult(
                    id="source_1",
                    title="Authoritative practical source",
                    locator="https://sources.test/1",
                    snippet="Factual guidance",
                )
            ]

        def fetch(self, _locator: str) -> Any:  # pragma: no cover - not used here
            raise AssertionError("fetch should not be called")

        def extract_competitor_outline(self, _result: SearchResult) -> Any:
            raise AssertionError("outline extraction should not be called")

    delegate = RecordingProvider()
    provider = _PlannedResearchProvider(
        delegate,
        competitor_query="primary",
        competitor_fallback_query="fallback",
        source_query="sources",
        competitor_seed_locators=["https://operator.test/course/syllabus"],
    )

    competitors = provider.search("ignored", limit=6)
    sources = provider.search("ignored", limit=6)

    assert competitors[0].id == "operator_material_1"
    assert [item.id for item in competitors[1:4]] == ["course_0", "course_1", "course_2"]
    assert [item.id for item in sources] == ["source_1"]
    assert delegate.queries == ["primary", "fallback", "sources"]
    assert provider.search_count == 2
    assert provider.web_search_count == 3


@pytest.mark.parametrize(
    ("stage", "artifact_type", "target_type", "target_id", "category"),
    [
        ("outcomes", "course_outcomes", "outcome", "co1", "clarity"),
        ("course-model", "course_model", "subtopic", "m1_s1", "scope"),
        ("blueprint", "blueprint", "subtopic", "m1_s1", "depth"),
        ("lesson-plan", "lesson_plan", "subtopic", "m1_s1", "sequence"),
    ],
)
def test_live_scoped_revision_api_changes_only_named_record(
    stage: str,
    artifact_type: str,
    target_type: str,
    target_id: str,
    category: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    course_id = f"eval-revision-{stage.replace('-', '')}"
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
        structured_model_provider=EvalStructuredProvider(),
    )
    _seed_acceptance_course(app, course_id, draft_stage=stage)
    with TestClient(app) as client:
        repository = app.state.repository
        before = repository.require(course_id, artifact_type)
        before_records = _record_map(stage, before)
        before_order = (
            [
                cover["subtopic_id"]
                for session in before["body"]["sessions"]
                for cover in session["covers"]
            ]
            if stage == "lesson-plan"
            else []
        )
        stage_view = client.get(f"/api/courses/{course_id}/stages/{stage}").json()
        impact = client.post(
            f"/api/courses/{course_id}/stages/{stage}/impact",
            json={
                "action": "revise",
                "target_type": target_type,
                "target_ids": [target_id],
                "operation_summary": f"Apply one bounded {category} improvement.",
                "expected_checksum": stage_view["checksum"],
            },
        )
        assert impact.status_code == 200, impact.text
        response = client.post(
            f"/api/courses/{course_id}/stages/{stage}/revisions",
            json={
                "target_type": target_type,
                "target_ids": [target_id],
                "category": category,
                "instruction": f"Apply one bounded {category} improvement.",
                "mode": "live",
                "expected_checksum": stage_view["checksum"],
                "impact_acknowledged": True,
                "expected_impact_checksum": impact.json()["impact_checksum"],
            },
        )
        assert response.status_code == 202, response.text
        job = _wait_for_job(client, response.json()["job_url"])
        assert job["status"] == "completed", job.get("error")
        assert job["result"]["revision"]["changed_ids"] == [target_id]
        after = repository.require(course_id, artifact_type)
        after_records = _record_map(stage, after)
        if stage == "lesson-plan":
            after_order = [
                cover["subtopic_id"]
                for session in after["body"]["sessions"]
                for cover in session["covers"]
            ]
            assert before_order.index(target_id) != after_order.index(target_id)
            assert before_records[target_id] == after_records[target_id]
        else:
            assert before_records[target_id] != after_records[target_id]
        assert all(
            before_records[record_id] == after_records[record_id]
            for record_id in before_records
            if record_id != target_id
        )


def test_live_provider_failure_preserves_prior_artifact_and_never_substitutes() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as temporary:
        tmp_path = Path(temporary)
        app = create_app(
            repo_root=REPO_ROOT,
            courses_root=tmp_path / "courses",
            rendered_root=tmp_path / "rendered",
            runtime_root=tmp_path / "runtime",
            include_examples=False,
            structured_model_provider=FailingProvider(),
        )
        course_id = "eval-live-failure"
        _seed_acceptance_course(app, course_id, draft_stage="outcomes")
        with TestClient(app) as client:
            repository = app.state.repository
            before = repository.require(course_id, "course_outcomes")
            before_checksum = repository.checksum(before)
            stage_view = client.get(
                f"/api/courses/{course_id}/stages/outcomes"
            ).json()
            impact = client.post(
                f"/api/courses/{course_id}/stages/outcomes/impact",
                json={
                    "action": "revise",
                    "target_type": "outcome",
                    "target_ids": ["co1"],
                    "operation_summary": "Clarify only co1.",
                    "expected_checksum": stage_view["checksum"],
                },
            )
            assert impact.status_code == 200, impact.text
            response = client.post(
                f"/api/courses/{course_id}/stages/outcomes/revisions",
                json={
                    "target_type": "outcome",
                    "target_ids": ["co1"],
                    "category": "clarity",
                    "instruction": "Clarify only co1.",
                    "mode": "live",
                    "expected_checksum": stage_view["checksum"],
                    "impact_acknowledged": True,
                    "expected_impact_checksum": impact.json()["impact_checksum"],
                },
            )
            assert response.status_code == 202, response.text
            job = _wait_for_job(client, response.json()["job_url"])
            assert job["status"] == "failed"
            assert "eval provider failed" in job["error"]["message"]
            assert repository.checksum(
                repository.require(course_id, "course_outcomes")
            ) == before_checksum


def test_live_revision_and_downstream_invalidation_roll_back_as_one_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "eval-atomic-revision"
    courses_root = tmp_path / "courses"
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
        structured_model_provider=EvalStructuredProvider(),
    )
    _seed_acceptance_course(app, course_id, draft_stage="course-model")
    artifact_dir = courses_root / course_id
    before = {path.name: path.read_bytes() for path in artifact_dir.glob("*.json")}
    real_replace = repository_module.os.replace
    failed = False

    def fail_downstream_once(source: Any, destination: Any) -> None:
        nonlocal failed
        if not failed and Path(destination).name == "blueprint.json":
            failed = True
            raise OSError("injected downstream replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(repository_module.os, "replace", fail_downstream_once)
    with TestClient(app) as client:
        stage_view = client.get(
            f"/api/courses/{course_id}/stages/course-model"
        ).json()
        impact = client.post(
            f"/api/courses/{course_id}/stages/course-model/impact",
            json={
                "action": "revise",
                "target_type": "subtopic",
                "target_ids": ["m1_s1"],
                "operation_summary": "Tighten one scope boundary.",
                "expected_checksum": stage_view["checksum"],
            },
        )
        assert impact.status_code == 200, impact.text
        response = client.post(
            f"/api/courses/{course_id}/stages/course-model/revisions",
            json={
                "target_type": "subtopic",
                "target_ids": ["m1_s1"],
                "category": "scope",
                "instruction": "Tighten one scope boundary.",
                "mode": "live",
                "expected_checksum": stage_view["checksum"],
                "impact_acknowledged": True,
                "expected_impact_checksum": impact.json()["impact_checksum"],
            },
        )
        assert response.status_code == 202, response.text
        job = _wait_for_job(client, response.json()["job_url"])
        assert job["status"] == "failed"
        assert "injected downstream replacement failure" in job["error"]["message"]

    assert failed is True
    assert {path.name: path.read_bytes() for path in artifact_dir.glob("*.json")} == before


def test_live_brief_clarification_round_is_bounded_validated_and_answerable(
    tmp_path: Path,
) -> None:
    provider = EvalStructuredProvider()
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
        structured_model_provider=provider,
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/courses",
            json={
                "course_id": "eval-live-brief",
                "subject": "Home composting for beginners",
                "brief": {
                    "audience": "Apartment beginners",
                    "purpose": "Maintain a small low-odor compost routine.",
                    "prior_knowledge": "No prior knowledge",
                    "level": "beginner",
                    "duration": "2 hours",
                    "modality": "self_paced",
                    "language": "English",
                    "in_scope": ["kitchen scraps"],
                    "out_of_scope": ["kitchen scraps"],
                },
            },
        )
        assert created.status_code == 201, created.text
        artifact_view = client.get(
            "/api/courses/eval-live-brief/artifacts/brief"
        ).json()
        round_response = client.post(
            "/api/courses/eval-live-brief/brief/clarifications/run",
            json={
                "mode": "live",
                "expected_checksum": artifact_view["checksum"],
            },
        )
        assert round_response.status_code == 200, round_response.text
        round_data = round_response.json()
        assert round_data["round_kind"] == "clarification"
        assert 1 <= len(round_data["questions"]) <= 3
        assert all(
            question["id"].startswith(f"brief_followup_{question['field']}_")
            for question in round_data["questions"]
        )
        first = round_data["questions"][0]
        answer = client.put(
            "/api/courses/eval-live-brief/brief/answers",
            json={
                "mode": "live",
                "expected_checksum": round_data["checksum"],
                "answers": [
                    {
                        "question_id": first["id"],
                        "value": "kitchen scraps",
                    }
                ],
            },
        )
        assert answer.status_code == 200, answer.text
        assert first["field"] in answer.json()["artifact"]["body"]["intake_state"][
            "explicit_fields"
        ]
        repeated = client.post(
            "/api/courses/eval-live-brief/brief/clarifications/run",
            json={
                "mode": "live",
                "expected_checksum": answer.json()["checksum"],
            },
        )
        assert repeated.status_code == 200, repeated.text
        assert first["id"] in {
            question["id"] for question in repeated.json()["questions"]
        }
        assert [call["stage"] for call in provider.calls] == ["brief", "brief", "brief"]


def test_unready_live_brief_provider_returns_explicit_503(tmp_path: Path) -> None:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
        structured_model_provider=NotReadyProvider(),
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/courses",
            json={"course_id": "eval-unready", "subject": "Simple home repairs"},
        )
        assert created.status_code == 201, created.text
        checksum = client.get(
            "/api/courses/eval-unready/artifacts/brief"
        ).json()["checksum"]
        response = client.post(
            "/api/courses/eval-unready/brief/clarifications/run",
            json={"mode": "live", "expected_checksum": checksum},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "provider_not_ready"
