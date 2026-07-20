"""Canonical Brief intake normalization and merge boundary.

The service is intentionally provider-neutral. NC-20 injects the deterministic
clarifier; a live clarifier can implement the same protocol in NC-909 without moving
visibility, validation, or persistence into React or a model response.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Protocol

import llm
from agents import intake
from interaction import QuestionSpec


class ClarificationProvider(Protocol):
    def propose(
        self,
        subject_request: dict,
        brief_body: dict,
        gaps: tuple[intake.IntakeGap, ...],
        *,
        max_questions: int,
    ) -> list[QuestionSpec]: ...


class DeterministicClarificationProvider:
    """Turn current deterministic gaps into bounded, field-safe questions."""

    def propose(
        self,
        subject_request: dict,
        brief_body: dict,
        gaps: tuple[intake.IntakeGap, ...],
        *,
        max_questions: int,
    ) -> list[QuestionSpec]:
        del gaps
        answered = brief_body.get("intake_state", {}).get("answered_question_ids", [])
        return intake.gap_followups(
            subject_request,
            brief_body,
            max_questions=max_questions,
            answered_question_ids=answered,
        )


class BriefIntakeService:
    def __init__(
        self,
        clarification_provider: ClarificationProvider | None = None,
        *,
        clarification_providers: Mapping[str, ClarificationProvider | None] | None = None,
    ) -> None:
        deterministic = clarification_provider or DeterministicClarificationProvider()
        configured = dict(clarification_providers or {})
        self.clarification_providers: dict[str, ClarificationProvider | None] = {
            "deterministic": configured.pop("deterministic", deterministic),
            "live": configured.pop("live", None),
        }
        if configured:
            raise ValueError(
                "unknown Brief clarification modes: " + ", ".join(sorted(configured))
            )

    def normalize(self, subject_request: dict, brief_body: dict) -> dict:
        return intake.normalize_brief_body(subject_request, brief_body)

    def normalize_artifact(self, subject_request: dict, brief: dict) -> dict:
        """Return one read-only normalized Brief view without persisting a migration.

        Approved pre-NC-20 snapshots are grandfathered so committed examples remain
        compatible. Historical drafts must still explicitly accept defaults whose
        provenance says they were merely assumed.
        """
        normalized = deepcopy(brief)
        normalized["body"] = intake.normalize_brief_body(
            subject_request,
            brief.get("body", {}),
            grandfather_assumed_defaults=brief.get("status") == "approved",
        )
        return normalized

    def is_resolved(self, subject_request: dict, brief: dict) -> bool:
        normalized = self.normalize_artifact(subject_request, brief)
        state = normalized.get("body", {}).get("intake_state", {})
        unresolved = (
            state.get("unresolved_required_fields", [])
            if isinstance(state, dict)
            else ["invalid_intake_state"]
        )
        return isinstance(unresolved, list) and not unresolved

    def is_approved_and_resolved(self, subject_request: dict, brief: dict) -> bool:
        return brief.get("status") == "approved" and self.is_resolved(
            subject_request, brief
        )

    def question_round(
        self,
        subject_request: dict,
        brief_body: dict,
        *,
        mode: str = "deterministic",
    ) -> dict:
        return intake.brief_question_round(
            subject_request,
            brief_body,
            clarification_provider=self._provider(mode),
        )

    def merge_answers(
        self,
        subject_request: dict,
        brief_body: dict,
        answers: list[dict],
        *,
        mode: str = "deterministic",
    ) -> dict:
        return intake.merge_answer_round(
            subject_request,
            brief_body,
            answers,
            clarification_provider=self._provider(mode),
        )

    def merge_updates(
        self,
        subject_request: dict,
        brief_body: dict,
        updates: dict,
    ) -> dict:
        return intake.merge_brief_updates(subject_request, brief_body, updates)

    def _provider(self, mode: str) -> ClarificationProvider:
        if mode not in self.clarification_providers:
            raise ValueError(f"unknown Brief clarification mode: {mode!r}")
        provider = self.clarification_providers[mode]
        if provider is None:
            raise llm.ProviderNotReady(
                f"{mode.capitalize()} Brief clarification is not configured; "
                "choose deterministic mode explicitly or configure the live provider."
            )
        return provider


def serialize_question(question: QuestionSpec) -> dict:
    return {
        "id": question.id,
        "field": question.field,
        "prompt": question.prompt,
        "rationale": question.why,
        "answer_type": question.answer_type,
        "options": list(question.options),
        "default": question.default,
        "required": question.required,
        "allow_skip": question.allow_skip,
        "visibility": {"show_if": dict(question.show_if)},
    }


def serialize_round(round_data: dict, *, checksum: str) -> dict:
    return {
        "questions": [serialize_question(item) for item in round_data["questions"]],
        "round_kind": round_data["round_kind"],
        "gap_analysis": round_data["gap_analysis"],
        "intake_state": round_data["intake_state"],
        "checksum": checksum,
    }
