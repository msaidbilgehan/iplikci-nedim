"""The interface's TypeScript types, generated from the API's OpenAPI document (ADR-0007).

openapi-typescript needs TypeScript 5 and the interface uses 7, so this small generator covers the JSON Schema that
the API's pydantic models produce: objects, arrays, maps, unions, enums, literals and references. `iplikci dev
api-tipleri` writes the file; a test keeps the copy in web/ current.
"""

import json
import re
import textwrap
from collections.abc import Mapping, Sequence
from typing import Any, cast

HEADER = (
    "// The service's API types, generated from its OpenAPI document by `iplikci dev api-tipleri` (ADR-0007).\n"
    "// Do not edit by hand: change the API's models and generate again; a test keeps this file current.\n"
)
_REF = "#/components/schemas/"
_IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_SCALARS = {"string": "string", "integer": "number", "number": "number", "boolean": "boolean", "null": "null"}
WIDTH = 120  # the repository's line length

Schema = Mapping[str, Any]


def render(document: Schema) -> str:
    """A TypeScript module with a declaration for every schema of the document, in name order."""
    schemas = cast(Mapping[str, Schema], document.get("components", {}).get("schemas", {}))
    blocks = [_declaration(name, schemas[name]) for name in sorted(schemas)]
    return HEADER + "".join(f"\n{block}\n" for block in blocks)


def _declaration(name: str, schema: Schema) -> str:
    about = _comment(schema, "")
    if _is_interface(schema):
        return f"{about}export interface {_name(name)} {_object(schema, 0)}"
    return f"{about}export type {_name(name)} = {_type(schema, 0)};"


def _is_interface(schema: Schema) -> bool:
    return schema.get("type") == "object" and bool(schema.get("properties"))


def _type(schema: Schema, depth: int) -> str:
    if "$ref" in schema:
        return _name(str(schema["$ref"]).removeprefix(_REF))
    if "enum" in schema:
        return _union([_literal(value) for value in schema["enum"]])
    if "const" in schema:
        return _literal(schema["const"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return _union([_type(part, depth) for part in cast(Sequence[Schema], schema[key])])
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _type(schema["allOf"][0], depth)
    kind = schema.get("type")
    if isinstance(kind, list):  # OpenAPI 3.1 allows a list of types
        return _union([_type({**schema, "type": one}, depth) for one in cast(list[str], kind)])
    if kind == "array":
        item = _type(schema.get("items", {}), depth)
        return f"({item})[]" if " | " in item else f"{item}[]"
    if kind == "object":
        return _object(schema, depth) if schema.get("properties") else f"Record<string, {_values(schema, depth)}>"
    return _SCALARS.get(str(kind), "unknown")


def _values(schema: Schema, depth: int) -> str:
    """The value type of a map: additionalProperties true (or absent) allows anything, false nothing."""
    extra = schema.get("additionalProperties", True)
    if extra is False:
        return "never"
    if extra is True or extra == {}:
        return "unknown"
    return _type(cast(Schema, extra), depth)


def _object(schema: Schema, depth: int) -> str:
    required = set(cast(Sequence[str], schema.get("required", ())))
    pad = "  " * (depth + 1)
    lines = ["{"]
    for key, spec in cast(Mapping[str, Schema], schema["properties"]).items():
        name = key if _IDENTIFIER.fullmatch(key) else json.dumps(key, ensure_ascii=False)
        mark = "" if key in required else "?"
        lines.append(f"{_comment(spec, pad)}{pad}{name}{mark}: {_type(spec, depth + 1)};")
    lines.append(f"{'  ' * depth}}}")
    return "\n".join(lines)


def _comment(schema: Schema, pad: str) -> str:
    """A schema's description as a doc comment, on one line when it fits in WIDTH."""
    text = " ".join(str(schema.get("description", "")).split()).replace("*/", "* /")
    if not text:
        return ""
    if len(pad) + len(text) + 7 <= WIDTH:
        return f"{pad}/** {text} */\n"
    lines = textwrap.wrap(text, WIDTH - len(pad) - 3, break_long_words=False, break_on_hyphens=False)
    return f"{pad}/**\n" + "".join(f"{pad} * {line}\n" for line in lines) + f"{pad} */\n"


def _literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _union(parts: Sequence[str]) -> str:
    return " | ".join(dict.fromkeys(parts))


def _name(name: str) -> str:
    """A TypeScript name for a schema: FastAPI's "Model-Output" becomes "ModelOutput"."""
    return re.sub(r"[^A-Za-z0-9_$]", "", name)
