"""Small dependency-free JSON Schema validator used by runtime domain guards.

The repository's v0.2 schemas deliberately use a compact keyword subset.  Keeping
that subset here lets production validation use the checked-in contract without a
new runtime dependency.  Unsupported schema keywords are annotations or are outside
the subset used by the current contracts.
"""

from __future__ import annotations

import re
from typing import Any


def validate_json_schema(
    instance: object,
    schema: dict[str, Any],
    *,
    root: dict[str, Any] | None = None,
    path: str = "$",
) -> list[dict[str, str]]:
    """Return path-aware issues for the supported JSON Schema keyword subset."""
    root = schema if root is None else root
    issues: list[dict[str, str]] = []

    if "$ref" in schema:
        target = _resolve_ref(str(schema["$ref"]), root)
        return validate_json_schema(instance, target, root=root, path=path)

    if "anyOf" in schema:
        if not any(
            not validate_json_schema(instance, option, root=root, path=path)
            for option in schema["anyOf"]
        ):
            issues.append(_issue(path, "Value does not match any allowed schema shape."))
        return issues

    if "type" in schema:
        requested = schema["type"]
        allowed = set(requested if isinstance(requested, list) else [requested])
        if not _type_matches(instance, allowed):
            return [
                _issue(
                    path,
                    f"Expected {', '.join(sorted(allowed))}; got {type(instance).__name__}.",
                )
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
            if name in properties:
                issues.extend(
                    validate_json_schema(
                        value,
                        properties[name],
                        root=root,
                        path=_property_path(path, name),
                    )
                )
            elif schema.get("additionalProperties") is False:
                issues.append(_issue(_property_path(path, name), "Property is not allowed."))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            issues.append(_issue(path, f"Array has fewer than {schema['minItems']} items."))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(_issue(path, f"Array has more than {schema['maxItems']} items."))
        if "items" in schema:
            for index, value in enumerate(instance):
                issues.extend(
                    validate_json_schema(
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
            not validate_json_schema(value, schema["contains"], root=root, path=path)
            for value in instance
        ):
            issues.append(_issue(path, "Array does not contain a required matching item."))

    return issues


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
