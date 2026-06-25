"""
Dependency-free JSON Schema subset validator for v0.2 Content Package contracts.

Supports ONLY the keyword subset that content_package.v0.2.schema.json uses:
  type, required, properties, additionalProperties (false), const, enum,
  minLength, minimum, items, $ref (into root $defs), anyOf, pattern,
  uniqueItems, contains.

Usage
-----
    errors = validate(instance, schema)          # [] = valid
    errors = validate_content_package(instance)  # loads real schema file

Design notes
------------
- `validate(instance, schema, root=None)` is fully recursive.  The `root`
  argument is always the top-level schema dict so that $ref resolution can walk
  `root["$defs"]` from any depth.
- Errors are human-readable strings; the list is never empty for invalid docs
  (this is intentional: callers assert `errors == []` for the positive case and
  `errors != []` for the negative case).
- No third-party libraries are used.  re is part of stdlib.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "content_package.v0.2.schema.json"

# ---------------------------------------------------------------------------
# $ref resolution
# ---------------------------------------------------------------------------


def _resolve_ref(ref: str, root: dict) -> dict:
    """Resolve a JSON Pointer $ref of the form '#/$defs/<name>'.

    Only intra-document refs (starting with '#/') are supported.  That is
    sufficient for the v0.2 schema.
    """
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported $ref (only '#/...' is handled): {ref!r}")
    parts = ref[2:].split("/")  # strip the leading '#/'
    node: dict = root  # type: ignore[assignment]
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"$ref '{ref}' could not be resolved in schema")
        node = node[part]
    return node  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Core recursive validator
# ---------------------------------------------------------------------------


def validate(instance: object, schema: dict, root: dict | None = None) -> list[str]:
    """Validate *instance* against *schema*, returning a list of error strings.

    Parameters
    ----------
    instance : any JSON-decoded Python value
    schema   : a JSON Schema dict (the current sub-schema being applied)
    root     : the top-level schema dict, used for $ref resolution.
               Defaults to *schema* itself on the initial call.
    """
    if root is None:
        root = schema

    errors: list[str] = []

    # ---- $ref: replace current schema with the referenced sub-schema --------
    if "$ref" in schema:
        ref_schema = _resolve_ref(schema["$ref"], root)
        # Merge any sibling keywords that exist alongside $ref (draft-07 style)
        # In the v0.2 schema there are none, but be safe.
        errors.extend(validate(instance, ref_schema, root))
        return errors

    # ---- anyOf: pass if at least one sub-schema validates --------------------
    if "anyOf" in schema:
        any_matched = False
        for sub in schema["anyOf"]:
            sub_errs = validate(instance, sub, root)
            if not sub_errs:
                any_matched = True
                break
        if not any_matched:
            errors.append(f"Value {instance!r} did not match any of the anyOf sub-schemas")
        return errors

    # ---- type ----------------------------------------------------------------
    if "type" in schema:
        type_spec = schema["type"]
        if isinstance(type_spec, list):
            # e.g. ["string", "null"]
            allowed = set(type_spec)
        else:
            allowed = {type_spec}
        if not _type_matches(instance, allowed):
            errors.append(
                f"Expected type(s) {sorted(allowed)}, got {type(instance).__name__!r} "
                f"(value: {instance!r})"
            )
            # No point checking further if the type is wrong.
            return errors

    # ---- const ---------------------------------------------------------------
    if "const" in schema:
        if instance != schema["const"]:
            errors.append(f"Expected const {schema['const']!r}, got {instance!r}")

    # ---- enum ----------------------------------------------------------------
    if "enum" in schema:
        if instance not in schema["enum"]:
            errors.append(f"Value {instance!r} not in enum {schema['enum']!r}")

    # ---- minLength (strings) -------------------------------------------------
    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            errors.append(f"String {instance!r} is shorter than minLength={schema['minLength']}")

    # ---- minimum (numbers/integers) ------------------------------------------
    if "minimum" in schema and isinstance(instance, (int, float)):
        if instance < schema["minimum"]:
            errors.append(f"Value {instance!r} is less than minimum={schema['minimum']}")

    # ---- pattern (strings) ---------------------------------------------------
    if "pattern" in schema and isinstance(instance, str):
        if not re.fullmatch(schema["pattern"], instance):
            errors.append(f"String {instance!r} does not match pattern {schema['pattern']!r}")

    # ---- Object keywords -----------------------------------------------------
    if isinstance(instance, dict):
        # required
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"Required property {key!r} is missing")

        # properties
        for prop, sub_schema in schema.get("properties", {}).items():
            if prop in instance:
                child_errors = validate(instance[prop], sub_schema, root)
                for e in child_errors:
                    errors.append(f".{prop}: {e}")

        # additionalProperties: false
        if schema.get("additionalProperties") is False:
            allowed_props = set(schema.get("properties", {}).keys())
            for key in instance:
                if key not in allowed_props:
                    errors.append(
                        f"Additional property {key!r} is not allowed "
                        f"(allowed: {sorted(allowed_props)})"
                    )

    # ---- Array keywords ------------------------------------------------------
    if isinstance(instance, list):
        # items
        if "items" in schema:
            item_schema = schema["items"]
            for idx, item in enumerate(instance):
                item_errors = validate(item, item_schema, root)
                for e in item_errors:
                    errors.append(f"[{idx}]: {e}")

        # uniqueItems
        if schema.get("uniqueItems"):
            seen: list = []
            for item in instance:
                if item in seen:
                    errors.append(f"Array must have unique items; duplicate: {item!r}")
                    break
                seen.append(item)

        # contains: at least one item must match the sub-schema
        if "contains" in schema:
            contains_schema = schema["contains"]
            if not any(not validate(item, contains_schema, root) for item in instance):
                errors.append(
                    f"Array does not contain any item matching the 'contains' schema "
                    f"({contains_schema!r})"
                )

    return errors


# ---------------------------------------------------------------------------
# Type-checking helper
# ---------------------------------------------------------------------------


def _type_matches(instance: object, allowed: set[str]) -> bool:
    """Return True if *instance* matches at least one JSON Schema primitive type."""
    if "null" in allowed and instance is None:
        return True
    if "boolean" in allowed and isinstance(instance, bool):
        return True
    # NB: bool is a subclass of int in Python, so check bool first.
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


# ---------------------------------------------------------------------------
# Convenience wrapper for the v0.2 Content Package schema
# ---------------------------------------------------------------------------


def validate_content_package(instance: object) -> list[str]:
    """Load the real v0.2 schema from disk and validate *instance* against it.

    Returns [] if valid, or a non-empty list of human-readable error strings.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return validate(instance, schema)
