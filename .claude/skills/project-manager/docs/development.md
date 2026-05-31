# Development & Testing

How to make and verify changes to PMKit safely.

## Python environment

Scripts need `pyyaml`, `jsonschema`, `requests` (+ `mcp` for the render server) — from the venv built by `mcp/setup.sh` (default `$HOME/max-eliseev-venv`), or any Python with those packages. Use one interpreter for everything: `status.py`/`finalize.py` import from `runner.py`/`graph_utils.py`.

```bash
PY=$HOME/max-eliseev-venv/bin/python   # or another python with the deps
$PY -c "import yaml, jsonschema, requests; print('deps OK')"
```

## Quick checks

```bash
cd scripts
$PY -m py_compile runner.py graph_utils.py scaffold.py status.py finalize.py notify.py render_server.py
# validate + render the example graph
$PY -c "import graph_utils as g; d=g.load_and_validate('../schema/example.graph.yaml'); print(g.to_mermaid(d))"
```

## End-to-end dry run (no real workers)

Workers spawn via an external `claude` command, so test *control flow* by faking reports, not by spawning Claude:

1. Scaffold a temp project: `$PY scaffold.py --project "$T"`.
2. Write a roadmap YAML under `$T/agents/roadmaps/` (include a `review: true` task).
3. Fake outcomes: write `$T/agents/reports/<id>-<name>.md` with frontmatter `status: success` (or `failed` / `review`).
4. Inspect state with `status.py`, or run one tick: `runner.py --once --dry-run --no-notify`.

This walks the whole state machine — e.g. `success` on a dep → next task READY; a `review` report holds dependents PENDING; flipping `review`→`success` releases them; an all-success run writes `status: complete` + `summary.json`.

Specific checks when touching the relevant code:
- **Review prompt injection**: `build_prompt(task, "INSTR")` contains the review instruction iff `task["review"]`.
- **finalize scoping**: `finalize.py --dry-run` lists `pmkit-*` but leaves unrelated sessions (e.g. `claude-pmkit-comfyui-*`) — the filter anchors on `pmkit-`.

## Where to change what

| Change | Edit | Then update |
|--------|------|-------------|
| Task-graph field | `schema/graph.schema.json` | runner (`build_prompt`/`task_claude_cmd`/`compute_states`), `example.graph.yaml`, `to_mermaid` if visible, `task-graph.md` |
| Worker behaviour | `templates/agents/instructions.md` (+ `decisions.md`) | re-stamp with `scaffold.py --force` for existing projects; `worker-contract.md` |
| Execution/state logic | `scripts/runner.py` | `runner.md` |
| Diagram look | `graph_utils.to_mermaid` | `task-graph.md` |
| Rendering/MCP | `mcp/render_server.py` | `render-mcp.md` |
| PM flow / monitor / wrap-up | `SKILL.md` | (operational flow lives only there) |
