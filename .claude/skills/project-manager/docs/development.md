# Development & Testing

How to make and verify changes to PMKit safely.

## Python environment

The scripts need `pyyaml`, `jsonschema`, and `requests` (and `mcp` for the render server). These live in the venv from `mcp/setup.sh` (default `$HOME/max-eliseev-venv`). If that venv isn't present in a given environment, any Python with those packages works (e.g. `/opt/venv/bin/python` on some machines). Pick one interpreter and use it for everything — `status.py`/`finalize.py` import from `runner.py`/`graph_utils.py`, so they must run under the same interpreter as the runner.

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

Workers are spawned via an external `claude` command, so you test the runner's *control flow* by faking reports, not by spawning Claude. The recipe:

1. Scaffold a temp project: `$PY scaffold.py --project "$T"`.
2. Write a roadmap YAML under `$T/agents/roadmaps/` (include a `review: true` task to exercise that path).
3. Fake task outcomes by writing `$T/agents/reports/<id>-<name>.md` with hand-set frontmatter:
   ```
   ---
   status: success    # or failed / review
   ---
   ```
4. Inspect derived state with `status.py` (it uses the same `compute_states`), or run a single tick with `runner.py --once --dry-run --no-notify`.

This lets you walk the whole state machine — e.g. assert that `success` on a dep makes the next task READY, that a `review` report holds dependents at PENDING, that flipping `review`→`success` releases them, and that an all-success run writes `status: complete` + `summary.json`.

Things worth asserting when touching the relevant code:
- **Review prompt injection**: `runner.build_prompt(task, "INSTR")` contains the review instruction iff `task["review"]` is set.
- **finalize scoping**: `finalize.py` kills `pmkit-*` sessions but leaves unrelated ones (e.g. `claude-pmkit-comfyui-*`) — the filter anchors on `pmkit-`. Test with `--dry-run` against live dummy `tmux new-session -d -s pmkit-xxx "sleep 60"` sessions.
- **Monitor branches**: with `pmkit-runner` absent, `status=complete` → `RUNNER_DONE`, otherwise → `RUNNER_DEAD`; a report with `status: review` → `REVIEW_PENDING`.

Always clean up temp dirs and dummy tmux sessions afterward.

## Where to change what

| Change | Edit | Then update |
|--------|------|-------------|
| Task-graph field | `schema/graph.schema.json` | runner (`build_prompt`/`task_claude_cmd`/`compute_states`), `example.graph.yaml`, `to_mermaid` if visible, `task-graph.md` |
| Worker behaviour | `templates/agents/instructions.md` (+ `decisions.md`) | re-stamp with `scaffold.py --force` for existing projects; `worker-contract.md` |
| Execution/state logic | `scripts/runner.py` | `runner.md`, `monitoring-and-lifecycle.md` |
| Diagram look | `graph_utils.to_mermaid` | `task-graph.md` |
| Rendering/MCP | `mcp/render_server.py` | `render-mcp.md` |
| PM flow / monitor / wrap-up | `SKILL.md` | `monitoring-and-lifecycle.md`, `architecture.md` |

Keep these docs in sync when you change behaviour — that's the whole point of them.
