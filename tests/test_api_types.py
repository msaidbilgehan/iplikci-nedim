"""The interface's TypeScript types come from the API's OpenAPI document (ADR-0007) and stay current with it."""

from pathlib import Path

from iplikci.api import typescript
from iplikci.api.app import openapi_document
from iplikci.cli import main

GENERATED = Path(__file__).parents[1] / "web" / "src" / "api" / "schema.ts"


def test_the_interfaces_types_are_generated_from_the_api_as_it_is():
    assert GENERATED.read_text(encoding="utf-8") == typescript.render(openapi_document()), (
        "the API's models changed: uv run iplikci dev api-tipleri web/src/api/schema.ts"
    )


def schema(**schemas: object) -> dict[str, object]:
    return {"components": {"schemas": schemas}}


def test_objects_become_interfaces_with_their_optional_fields_marked():
    out = typescript.render(
        schema(
            Thing={
                "type": "object",
                "properties": {"id": {"type": "integer"}, "note": {"type": "string"}, "odd-key": {"type": "boolean"}},
                "required": ["id"],
            }
        )
    )
    assert 'export interface Thing {\n  id: number;\n  note?: string;\n  "odd-key"?: boolean;\n}\n' in out


def test_unions_maps_arrays_enums_and_references_become_their_typescript_forms():
    out = typescript.render(
        schema(
            Kind={"enum": ["a", "b"], "type": "string"},
            Holder={
                "type": "object",
                "properties": {
                    "kind": {"$ref": "#/components/schemas/Kind"},
                    "maybe": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
                    "counts": {"type": "object", "additionalProperties": {"type": "integer"}},
                    "anything": {"type": "object", "additionalProperties": True},
                    "mixed": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
                    "fixed": {"const": "x"},
                    "listed": {"type": ["string", "null"]},
                    "free": {},
                },
                "required": ["kind", "maybe", "counts", "anything", "mixed", "fixed", "listed", "free"],
            },
        )
    )
    assert 'export type Kind = "a" | "b";' in out
    for line in (
        "  kind: Kind;",
        "  maybe: boolean | null;",
        "  counts: Record<string, number>;",
        "  anything: Record<string, unknown>;",
        "  mixed: (string | number)[];",
        '  fixed: "x";',
        "  listed: string | null;",
        "  free: unknown;",
    ):
        assert line in out


def test_names_fastapi_gives_split_schemas_become_typescript_names():
    out = typescript.render(schema(**{"Model-Output": {"type": "object", "properties": {"a": {"type": "string"}}}}))
    assert "export interface ModelOutput {" in out


def test_a_long_description_wraps_within_the_line_length():
    words = " ".join(["sözcük"] * 40)
    out = typescript.render(schema(Long={"type": "string", "description": words}))
    assert out.splitlines()[3] == "/**"
    assert all(len(line) <= typescript.WIDTH for line in out.splitlines())


def test_the_dev_command_writes_the_types_and_says_when_nothing_changed(tmp_path, capsys):
    target = tmp_path / "schema.ts"
    assert main(["dev", "api-tipleri", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == typescript.render(openapi_document())
    assert main(["dev", "api-tipleri", str(target)]) == 0
    assert capsys.readouterr().out.splitlines()[-1].endswith("değişmedi")
