"""Small dependency-free JSON Schema validator used by runtime domain guards.

The repository's v0.2 schemas deliberately use a compact keyword subset. Keeping
that subset explicit here lets production validation use the checked-in contract
without a new runtime dependency. Unknown assertion keywords fail closed instead
of being silently ignored.
"""

from __future__ import annotations

import re
from typing import Any

_SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$defs",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "anyOf",
        "const",
        "contains",
        "enum",
        "items",
        "maxItems",
        "maxLength",
        "minItems",
        "minLength",
        "minimum",
        "pattern",
        "properties",
        "required",
        "type",
        "uniqueItems",
    }
)

# These standard annotation keywords do not affect instance validity. They are
# accepted intentionally; every other unimplemented keyword is rejected.
_SUPPORTED_ANNOTATION_KEYWORDS = frozenset({"description", "title"})


def validate_json_schema(
    instance: object,
    schema: dict[str, Any],
    *,
    root: dict[str, Any] | None = None,
    path: str = "$",
) -> list[dict[str, str]]:
    """Return path-aware issues for the supported JSON Schema keyword subset.

    Unsupported or malformed schemas raise ``ValueError``. Schemas are trusted
    application contracts rather than user input, so a contract the runtime
    cannot enforce must fail loudly instead of accepting an instance unchecked.
    """
    root = schema if root is None else root
    _assert_supported_schema(root)
    if schema is not root:
        _assert_supported_schema(schema, path="$fragment")
    return _validate_json_schema(instance, schema, root=root, path=path)


def _validate_json_schema(
    instance: object,
    schema: dict[str, Any],
    *,
    root: dict[str, Any],
    path: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    if "$ref" in schema:
        target = _resolve_ref(schema["$ref"], root)
        issues.extend(_validate_json_schema(instance, target, root=root, path=path))

    if "anyOf" in schema and not any(
        not _validate_json_schema(instance, option, root=root, path=path)
        for option in schema["anyOf"]
    ):
        issues.append(_issue(path, "Value does not match any allowed schema shape."))

    if "type" in schema:
        requested = schema["type"]
        allowed = set(requested if isinstance(requested, list) else [requested])
        if not _type_matches(instance, allowed):
            return [
                *issues,
                _issue(
                    path,
                    f"Expected {', '.join(sorted(allowed))}; got {type(instance).__name__}.",
                ),
            ]

    if "const" in schema and instance != schema["const"]:
        issues.append(_issue(path, f"Value must equal {schema['const']!r}."))
    if "enum" in schema and instance not in schema["enum"]:
        issues.append(_issue(path, f"Value is not one of {schema['enum']!r}."))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            issues.append(_issue(path, f"String is shorter than {schema['minLength']}."))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            issues.append(_issue(path, f"String is longer than {schema['maxLength']}."))
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
            issues.append(_issue(path, f"String does not match {schema['pattern']!r}."))

    if (
        "minimum" in schema
        and isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and instance < schema["minimum"]
    ):
        issues.append(_issue(path, f"Value is less than {schema['minimum']}."))

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                issues.append(_issue(_property_path(path, name), "Required property is missing."))
        for name, value in instance.items():
            property_path = _property_path(path, name)
            if name in properties:
                issues.extend(
                    _validate_json_schema(
                        value,
                        properties[name],
                        root=root,
                        path=property_path,
                    )
                )
                continue
            additional_properties = schema.get("additionalProperties", True)
            if additional_properties is False:
                issues.append(_issue(property_path, "Property is not allowed."))
            elif isinstance(additional_properties, dict):
                issues.extend(
                    _validate_json_schema(
                        value,
                        additional_properties,
                        root=root,
                        path=property_path,
                    )
                )

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            issues.append(_issue(path, f"Array has fewer than {schema['minItems']} items."))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(_issue(path, f"Array has more than {schema['maxItems']} items."))
        if "items" in schema:
            for index, value in enumerate(instance):
                issues.extend(
                    _validate_json_schema(
                        value,
                        schema["items"],
                        root=root,
                        path=f"{path}[{index}]",
                    )
                )
        if schema.get("uniqueItems"):
            for index, value in enumerate(instance):
                if value in instance[:index]:
                    issues.append(_issue(f"{path}[{index}]", "Array items must be unique."))
                    break
        if "contains" in schema and not any(
            not _validate_json_schema(value, schema["contains"], root=root, path=path)
            for value in instance
        ):
            issues.append(_issue(path, "Array does not contain a required matching item."))

    return issues


def _assert_supported_schema(schema: object, *, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"JSON Schema at {path} must be an object.")

    unsupported = set(schema) - _SUPPORTED_SCHEMA_KEYWORDS - _SUPPORTED_ANNOTATION_KEYWORDS
    if unsupported:
        keyword = sorted(unsupported)[0]
        raise ValueError(f"Unsupported JSON Schema keyword {keyword!r} at {path}.")

    _assert_keyword_shapes(schema, path=path)

    definitions = schema.get("$defs", {})
    for name, subschema in definitions.items():
        _assert_supported_schema(
            subschema,
            path=f"{path}.$defs{_schema_name_suffix(name)}",
        )

    properties = schema.get("properties", {})
    for name, subschema in properties.items():
        _assert_supported_schema(
            subschema,
            path=f"{path}.properties{_schema_name_suffix(name)}",
        )

    for keyword in ("items", "contains"):
        if keyword in schema:
            _assert_supported_schema(schema[keyword], path=f"{path}.{keyword}")

    additional_properties = schema.get("additionalProperties")
    if isinstance(additional_properties, dict):
        _assert_supported_schema(
            additional_properties,
            path=f"{path}.additionalProperties",
        )

    for index, subschema in enumerate(schema.get("anyOf", [])):
        _assert_supported_schema(subschema, path=f"{path}.anyOf[{index}]")


def _assert_keyword_shapes(schema: dict[str, Any], *, path: str) -> None:
    if "$ref" in schema and not isinstance(schema["$ref"], str):
        raise ValueError(f"JSON Schema $ref at {path} must be a string.")

    if "$defs" in schema and not isinstance(schema["$defs"], dict):
        raise ValueError(f"JSON Schema $defs at {path} must be an object.")
    if "properties" in schema and not isinstance(schema["properties"], dict):
        raise ValueError(f"JSON Schema properties at {path} must be an object.")

    if "anyOf" in schema and (
        not isinstance(schema["anyOf"], list) or not schema["anyOf"]
    ):
        raise ValueError(f"JSON Schema anyOf at {path} must be a non-empty array.")

    for keyword in ("items", "contains"):
        if keyword in schema and not isinstance(schema[keyword], dict):
            raise ValueError(f"JSON Schema {keyword} at {path} must be an object.")

    if "additionalProperties" in schema and not isinstance(
        schema["additionalProperties"], (bool, dict)
    ):
        raise ValueError(
            f"JSON Schema additionalProperties at {path} must be a boolean or object."
        )

    allowed_types = {"array", "boolean", "integer", "null", "number", "object", "string"}
    if "type" in schema:
        raw_types = schema["type"]
        types = raw_types if isinstance(raw_types, list) else [raw_types]
        if (
            not types
            or any(not isinstance(item, str) or item not in allowed_types for item in types)
            or len(types) != len(set(types))
        ):
            raise ValueError(f"JSON Schema type at {path} is not supported.")

    if "enum" in schema and (
        not isinstance(schema["enum"], list) or not schema["enum"]
    ):
        raise ValueError(f"JSON Schema enum at {path} must be a non-empty array.")
    if "required" in schema and (
        not isinstance(schema["required"], list)
        or any(not isinstance(item, str) for item in schema["required"])
        or len(schema["required"]) != len(set(schema["required"]))
    ):
        raise ValueError(f"JSON Schema required at {path} must contain unique strings.")

    for keyword in ("minItems", "maxItems", "minLength", "maxLength"):
        if keyword in schema and (
            not isinstance(schema[keyword], int)
            or isinstance(schema[keyword], bool)
            or schema[keyword] < 0
        ):
            raise ValueError(f"JSON Schema {keyword} at {path} must be a non-negative integer.")

    if "minimum" in schema and (
        not isinstance(schema["minimum"], (int, float))
        or isinstance(schema["minimum"], bool)
    ):
        raise ValueError(f"JSON Schema minimum at {path} must be numeric.")
    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise ValueError(f"JSON Schema uniqueItems at {path} must be a boolean.")
    if "pattern" in schema:
        if not isinstance(schema["pattern"], str):
            raise ValueError(f"JSON Schema pattern at {path} must be a string.")
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            raise ValueError(f"Invalid JSON Schema pattern at {path}: {exc}.") from exc


def _schema_name_suffix(name: object) -> str:
    value = str(name)
    return (
        f".{value}"
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
        else f"[{value!r}]"
    )


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported external JSON Schema reference: {ref!r}")
    node: Any = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"Unresolvable JSON Schema reference: {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"JSON Schema reference does not resolve to an object: {ref!r}")
    return node


def _type_matches(instance: object, allowed: set[str]) -> bool:
    if "null" in allowed and instance is None:
        return True
    if "boolean" in allowed and isinstance(instance, bool):
        return True
    if "integer" in allowed and isinstance(instance, int) and not isinstance(instance, bool):
        return True
    if (
        "number" in allowed
        and isinstance(instance, (int, float))
        and not isinstance(instance, bool)
    ):
        return True
    if "string" in allowed and isinstance(instance, str):
        return True
    if "array" in allowed and isinstance(instance, list):
        return True
    if "object" in allowed and isinstance(instance, dict):
        return True
    return False


def _property_path(path: str, name: object) -> str:
    value = str(name)
    return (
        f"{path}.{value}"
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
        else f"{path}[{value!r}]"
    )


def _issue(path: str, message: str) -> dict[str, str]:
    return {"path": path, "message": message}
