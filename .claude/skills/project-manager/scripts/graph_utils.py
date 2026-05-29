#!/usr/bin/env python3
"""Shared task-graph utilities: load, validate, and render.

Used by both the render MCP server and the runner so the graph contract is
enforced in exactly one place.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import ValidationError
from jsonschema import validate as _js_validate

TOOLKIT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = TOOLKIT / "schema" / "graph.schema.json"


class GraphError(ValueError):
    """Raised for any malformed or invalid task graph."""


def load_graph(path) -> dict:
    p = Path(path)
    if not p.exists():
        raise GraphError(f"roadmap not found: {p}")
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict):
        raise GraphError(f"roadmap is not a YAML mapping: {p}")
    return data


def detect_cycle(data: dict):
    """Return a cycle as a list of ids (e.g. ['001','002','001']) or None."""
    deps = {t["id"]: list(t["deps"]) for t in data["tasks"]}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {i: WHITE for i in deps}
    stack: list[str] = []

    def dfs(u: str):
        color[u] = GRAY
        stack.append(u)
        for v in deps.get(u, []):
            if color.get(v) == GRAY:
                return stack[stack.index(v):] + [v]
            if color.get(v) == WHITE:
                found = dfs(v)
                if found:
                    return found
        color[u] = BLACK
        stack.pop()
        return None

    for node in deps:
        if color[node] == WHITE:
            found = dfs(node)
            if found:
                return found
    return None


def validate_graph(data: dict, schema_path=SCHEMA_PATH) -> None:
    """Validate against the JSON schema, then run semantic checks. Raises GraphError."""
    schema = json.loads(Path(schema_path).read_text())
    try:
        _js_validate(instance=data, schema=schema)
    except ValidationError as e:
        loc = " -> ".join(str(x) for x in e.absolute_path) or "(root)"
        raise GraphError(f"schema validation failed at {loc}: {e.message}") from None

    ids = [t["id"] for t in data["tasks"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise GraphError(f"duplicate task ids: {dupes}")

    idset = set(ids)
    for t in data["tasks"]:
        for d in t["deps"]:
            if d == t["id"]:
                raise GraphError(f"task {t['id']} depends on itself")
            if d not in idset:
                raise GraphError(f"task {t['id']} depends on unknown id {d}")

    cycle = detect_cycle(data)
    if cycle:
        raise GraphError(f"dependency cycle: {' -> '.join(cycle)}")


def load_and_validate(path, schema_path=SCHEMA_PATH) -> dict:
    data = load_graph(path)
    validate_graph(data, schema_path)
    return data


def to_mermaid(data: dict) -> str:
    """Render the graph as a Mermaid `graph TD`. Node ids are prefixed with `t`
    so numeric task ids ('001') are valid Mermaid identifiers."""
    lines = ["graph TD"]
    for t in data["tasks"]:
        label = f'{t["id"]} {t["name"]}'.replace('"', "'")
        lines.append(f'  t{t["id"]}["{label}"]')
    for t in data["tasks"]:
        for d in t["deps"]:
            lines.append(f'  t{d} --> t{t["id"]}')
    return "\n".join(lines) + "\n"
