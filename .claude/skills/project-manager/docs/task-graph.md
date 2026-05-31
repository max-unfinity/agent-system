# The Task Graph

The roadmap YAML is the single source of truth for the runner. Its contract is `schema/graph.schema.json`; loading/validation/rendering live in `scripts/graph_utils.py` so the graph rules are enforced in exactly one place (used by both the runner and the render MCP).

## Schema (`schema/graph.schema.json`)

Top level (all required, no additional properties):

| Field | Type | Notes |
|-------|------|-------|
| `project` | string | Project name (matches `CLAUDE.md`). |
| `roadmap_id` | string | Three digits, e.g. `"001"`. |
| `tasks` | array (min 1) | The task nodes. |

Each task (`id`, `name`, `file`, `deps` required):

| Field | Type | Notes |
|-------|------|-------|
| `id` | string `^[0-9]{3}$` | Stable identity, **not** execution order. |
| `name` | string | Short kebab-case; used in filenames. |
| `file` | string | Path to the task spec, e.g. `agents/tasks/001-setup.md`. |
| `deps` | array of `^[0-9]{3}$` | Task ids that must reach `status: success` first. Empty = root. |
| `model` | string *(optional)* | Per-task model override, e.g. `claude-sonnet-4-6`. Omit → runner default (opus-4-8). |
| `effort` | enum *(optional)* | `low`/`medium`/`high`/`xhigh`/`max`. Omit → runner default (medium). |
| `review` | boolean *(optional)* | `true` → review task: worker reports `status: review`, dependents wait for user validation. Default false. |

`deps` defines execution order; tasks with no path between them run in parallel (subject to `--max-concurrency`). See `schema/example.graph.yaml` for a worked diamond with model/effort/review examples.

## Validation (`graph_utils.py`)

`load_and_validate(path)` = `load_graph` + `validate_graph`. `validate_graph` runs:

1. **JSON-schema** check (`jsonschema`). On failure raises `GraphError` with the failing path.
2. **Duplicate ids** — none allowed.
3. **Dependency integrity** — no self-dependency; every `deps` entry must reference a known id.
4. **Cycle detection** — `detect_cycle()` does a DFS three-colour (WHITE/GRAY/BLACK) walk and returns the offending cycle as a list of ids; any cycle is a `GraphError`.

All failures raise `GraphError` (a `ValueError` subclass). The runner catches it and exits non-zero; the render MCP surfaces it to the PM, so rendering doubles as the PM's "is my graph well-formed?" check.

## Rendering (`to_mermaid()`)

Produces a Mermaid `graph TD`. Node ids are prefixed with `t` so numeric task ids (`001`) are valid Mermaid identifiers. Review tasks get a `⏸ review` suffix on their label so the human can see at a glance which nodes will pause for sign-off. Edges are drawn dep → task.

The actual `.mmd`/`.png` files are produced by the `pmkit-render` MCP server, which calls `to_mermaid` then (for PNG) `mmdc`. See `render-mcp.md`.

## Changing the format

If you add a task field: update `schema/graph.schema.json`, then teach the runner about it (`task_claude_cmd`/`build_prompt`/`compute_states` as relevant), then `example.graph.yaml`, then `to_mermaid` if it should show on the diagram. Keep `additionalProperties: false` honest — an unrecognised field should fail validation, not be silently ignored.
