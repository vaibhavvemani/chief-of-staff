"""Typed human-interaction primitives for Course Builder checkpoints.

The terminal UI is intentionally a thin renderer over provider-independent
question and choice specifications. Later UI surfaces should be able to render
the same objects as form fields without involving an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AnswerType = Literal[
    "free_text",
    "single_choice",
    "multiple_choice",
    "number",
    "duration",
    "confirmation",
]
ChoiceMode = Literal["single", "multi"]


@dataclass(frozen=True)
class QuestionSpec:
    """A typed question that resolves one artifact field or decision."""

    id: str
    field: str
    prompt: str
    why: str
    answer_type: AnswerType = "free_text"
    required: bool = True
    options: tuple[str, ...] = ()
    default: Any | None = None
    allow_skip: bool = False
    show_if: dict[str, Any] = field(default_factory=dict)
    allow_agent_followup: bool = False

    def visible_for(self, answers: dict[str, Any]) -> bool:
        """Return True when this question's deterministic conditions are met."""
        for field_name, expected in self.show_if.items():
            actual = answers.get(field_name)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def resolved_by(self, answers: dict[str, Any]) -> bool:
        if self.field not in answers:
            return False
        if not self.required or self.allow_skip:
            return True
        return answers[self.field] not in (None, "", [])

    def coerce_answer(self, raw: Any) -> Any:
        """Coerce terminal/script values into the declared answer type."""
        if raw in (None, ""):
            if self.default is not None:
                return self.default
            return raw
        if self.answer_type == "multiple_choice" and isinstance(raw, str):
            return [item.strip() for item in raw.split(",") if item.strip()]
        if self.answer_type == "number" and isinstance(raw, str):
            if "." in raw:
                return float(raw)
            return int(raw)
        if self.answer_type == "confirmation" and isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in {"y", "yes", "true", "approve"}:
                return True
            if normalized in {"n", "no", "false", "reject"}:
                return False
        return raw

    def validate_answer(self, raw: Any) -> list[str]:
        """Return validation errors for a proposed answer."""
        try:
            value = self.coerce_answer(raw)
        except ValueError:
            return [f"{self.id}: expected a number"]

        if value in (None, "", []):
            if self.required and not self.allow_skip and self.default is None:
                return [f"{self.id}: answer is required"]
            return []

        if self.answer_type == "single_choice":
            if not isinstance(value, str):
                return [f"{self.id}: expected one option id"]
            if self.options and value not in self.options:
                return [f"{self.id}: {value!r} is not an allowed option"]
        elif self.answer_type == "multiple_choice":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                return [f"{self.id}: expected a list of option ids"]
            unknown = sorted(set(value) - set(self.options))
            if unknown:
                return [f"{self.id}: unknown option ids {unknown}"]
        elif self.answer_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return [f"{self.id}: expected a numeric value"]
        elif self.answer_type == "confirmation":
            if not isinstance(value, bool):
                return [f"{self.id}: expected yes/no confirmation"]
        elif self.answer_type in {"free_text", "duration"}:
            if not isinstance(value, str):
                return [f"{self.id}: expected text"]
        return []


@dataclass(frozen=True)
class ChoiceOption:
    """One selectable option inside a structured human decision."""

    id: str
    label: str
    description: str
    recommendation_rationale: str | None = None
    selected_by_default: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChoiceDecision:
    """The deterministic result of applying a structured choice prompt."""

    prompt_id: str
    selected_ids: tuple[str, ...]
    rejected_ids: tuple[str, ...]
    custom_items: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ChoicePrompt:
    """A provider-independent select/reject/edit/add decision form."""

    id: str
    stage: str
    target_artifact: str
    question: str
    mode: ChoiceMode
    options: tuple[ChoiceOption, ...]
    min_selections: int = 0
    max_selections: int | None = None
    allow_custom: bool = False

    def option_ids(self) -> set[str]:
        return {option.id for option in self.options}

    def default_selected_ids(self) -> tuple[str, ...]:
        return tuple(option.id for option in self.options if option.selected_by_default)

    def validate_selection(
        self,
        selected_ids: list[str] | tuple[str, ...],
        custom_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    ) -> list[str]:
        errors: list[str] = []
        selected = tuple(selected_ids)
        unknown = sorted(set(selected) - self.option_ids())
        if unknown:
            errors.append(f"{self.id}: unknown option ids {unknown}")
        if len(set(selected)) != len(selected):
            errors.append(f"{self.id}: selected option ids must be unique")
        if self.mode == "single" and len(selected) > 1:
            errors.append(f"{self.id}: only one option may be selected")
        if len(selected) < self.min_selections:
            errors.append(f"{self.id}: expected at least {self.min_selections} selection(s)")
        if self.max_selections is not None and len(selected) > self.max_selections:
            errors.append(f"{self.id}: expected at most {self.max_selections} selection(s)")
        if custom_items and not self.allow_custom:
            errors.append(f"{self.id}: custom items are not allowed")
        return errors

    def decide(
        self,
        selected_ids: list[str] | tuple[str, ...],
        custom_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    ) -> ChoiceDecision:
        errors = self.validate_selection(selected_ids, custom_items)
        if errors:
            raise ValueError("; ".join(errors))
        selected = tuple(selected_ids)
        rejected = tuple(option.id for option in self.options if option.id not in selected)
        return ChoiceDecision(
            prompt_id=self.id,
            selected_ids=selected,
            rejected_ids=rejected,
            custom_items=tuple(custom_items),
        )


class ScriptedResponder:
    """Deterministic responder for tests and non-interactive demos."""

    def __init__(
        self,
        *,
        answers: dict[str, Any] | None = None,
        choices: dict[str, list[str] | tuple[str, ...]] | None = None,
        custom_items: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.answers = answers or {}
        self.choices = choices or {}
        self.custom_items = custom_items or {}

    def answer_questions(self, questions: list[QuestionSpec]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for question in questions:
            raw = self.answers.get(question.id, self.answers.get(question.field))
            errors = question.validate_answer(raw)
            if errors:
                raise ValueError("; ".join(errors))
            value = question.coerce_answer(raw)
            if value in (None, "", []) and question.default is not None:
                value = question.default
            if value not in (None, "", []):
                resolved[question.field] = value
            elif not question.required or question.allow_skip:
                resolved[question.field] = None
        return resolved

    def choose(self, prompt: ChoicePrompt) -> ChoiceDecision:
        selected = self.choices.get(prompt.id, prompt.default_selected_ids())
        custom = self.custom_items.get(prompt.id, [])
        return prompt.decide(tuple(selected), tuple(custom))


class TerminalInteractionRenderer:
    """Console renderer for typed questions and structured choices."""

    def __init__(self, input_func=input, output_func=print) -> None:
        self._input = input_func
        self._output = output_func

    def answer_questions(self, questions: list[QuestionSpec]) -> dict[str, Any]:
        answers: dict[str, Any] = {}
        for question in questions:
            while True:
                self._output(f"\n{question.prompt}")
                if question.why:
                    self._output(f"Why it matters: {question.why}")
                if question.options:
                    self._output("Options: " + ", ".join(question.options))
                if question.default is not None:
                    self._output(f"Default: {question.default}")
                raw = self._input("> ").strip()
                value = question.default if raw == "" and question.default is not None else raw
                errors = question.validate_answer(value)
                if not errors:
                    coerced = question.coerce_answer(value)
                    if coerced not in (None, "", []):
                        answers[question.field] = coerced
                    elif not question.required or question.allow_skip:
                        answers[question.field] = None
                    break
                self._output("; ".join(errors))
        return answers

    def choose(self, prompt: ChoicePrompt) -> ChoiceDecision:
        self._output(f"\n{prompt.question}")
        for option in prompt.options:
            marker = " [recommended]" if option.selected_by_default else ""
            self._output(f"- {option.id}: {option.label}{marker}")
            self._output(f"  {option.description}")
            if option.recommendation_rationale:
                self._output(f"  Rationale: {option.recommendation_rationale}")
        default = ",".join(prompt.default_selected_ids())
        while True:
            raw = self._input(f"Select option id(s){f' [{default}]' if default else ''}: ")
            selected = default if raw.strip() == "" and default else raw
            selected_ids = tuple(item.strip() for item in selected.split(",") if item.strip())
            errors = prompt.validate_selection(selected_ids)
            if not errors:
                return prompt.decide(selected_ids)
            self._output("; ".join(errors))
