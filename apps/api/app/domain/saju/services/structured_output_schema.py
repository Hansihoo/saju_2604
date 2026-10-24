"""The same provider schema for Responses and Codex exec; validate prose later."""

from copy import deepcopy
from typing import Any, Dict


SCHEMA_NOISE_KEYS = {
    "default", "examples", "minLength", "maxLength", "pattern", "format",
    "minimum", "maximum", "multipleOf", "minItems", "maxItems",
}


def strict_output_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = deepcopy(schema)

    def visit(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for key in SCHEMA_NOISE_KEYS:
            node.pop(key, None)
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        # Property/definition names are data, not JSON Schema keywords.
        for key in ("properties", "$defs", "definitions"):
            for child in node.get(key, {}).values():
                visit(child)
        for key in ("items", "additionalProperties"):
            visit(node.get(key))
        for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
            for child in node.get(key, []):
                visit(child)

    visit(cleaned)
    return cleaned


def make_openai_json_schema_strict(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "json_schema", "name": name, "strict": True, "schema": strict_output_schema(schema)}
