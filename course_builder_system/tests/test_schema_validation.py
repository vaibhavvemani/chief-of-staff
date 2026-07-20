import json
from pathlib import Path

import pytest

from schema_validation import validate_json_schema

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


@pytest.mark.parametrize(
    "schema_name",
    [
        "course_model.v0.2.schema.json",
        "course_outcomes.v0.2.schema.json",
        "research_dossier.v0.2.schema.json",
    ],
)
def test_current_contract_schema_keywords_are_supported(schema_name: str) -> None:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))

    assert validate_json_schema(None, schema)


def test_unsupported_schema_keyword_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported JSON Schema keyword 'maxProperties'"):
        validate_json_schema({}, {"type": "object", "maxProperties": 1})


def test_unsupported_keyword_in_unselected_any_of_branch_fails_closed() -> None:
    schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "integer", "exclusiveMinimum": 0},
        ]
    }

    with pytest.raises(
        ValueError,
        match="Unsupported JSON Schema keyword 'exclusiveMinimum' at \\$.anyOf\\[1\\]",
    ):
        validate_json_schema("already matches", schema)


def test_ref_and_its_assertion_siblings_are_all_applied() -> None:
    schema = {
        "$defs": {"nonempty": {"type": "string", "minLength": 1}},
        "$ref": "#/$defs/nonempty",
        "maxLength": 3,
    }

    assert validate_json_schema("ok", schema) == []
    assert validate_json_schema("", schema) == [
        {"path": "$", "message": "String is shorter than 1."}
    ]
    assert validate_json_schema("long", schema) == [
        {"path": "$", "message": "String is longer than 3."}
    ]


def test_any_of_and_its_assertion_siblings_are_all_applied() -> None:
    schema = {
        "anyOf": [{"type": "string"}, {"type": "integer"}],
        "enum": ["allowed", 1],
    }

    assert validate_json_schema("allowed", schema) == []
    assert validate_json_schema("other", schema) == [
        {"path": "$", "message": "Value is not one of ['allowed', 1]."}
    ]
    assert validate_json_schema([], schema) == [
        {"path": "$", "message": "Value does not match any allowed schema shape."},
        {"path": "$", "message": "Value is not one of ['allowed', 1]."},
    ]
