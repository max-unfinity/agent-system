# PMKit Documentation Index

Maintainer documentation for the **project-manager** skill (a.k.a. *PMKit*). These docs describe how the skill works internally so future changes can be made safely. Each entry is a relative path followed by a description and when to read it. Append new records here.

> Scope note: this is documentation *of the skill itself*, for people/agents editing it. It is distinct from `templates/docs/INDEX.md`, which is the empty INDEX stamped into each generated project for worker sub-agents to fill in.

- `architecture.md`: The big picture — the PM-agent / deterministic-runner split, the four-phase flow, the on-disk layout of a generated project, and how state is derived from disk + tmux with no state file. **Read this first.**
- `runner.md`: Deep dive on `scripts/runner.py` — the task state machine (PENDING/READY/RUNNING/DONE/FAILED/BLOCKED/REVIEW), the fixpoint in `compute_states`, launching workers, per-task model/effort, review handling, the lifecycle `status` file, `summary.json`, finalize, and CLI flags. Read when changing execution or state logic.
- `task-graph.md`: The roadmap YAML contract — `schema/graph.schema.json` fields and `scripts/graph_utils.py` (load/validate, the four semantic checks, cycle detection, Mermaid rendering). Read when changing the graph format or validation.
- `worker-contract.md`: What a worker sub-agent is told to do — `templates/agents/instructions.md` six phases, report frontmatter (`success`/`failed`/`review`), and the single-file `agents/decisions.md` log. Read when changing the worker contract or templates.
- `scripts.md`: The supporting scripts — `scaffold.py`, `status.py`, `finalize.py`, `notify.py`: purpose, usage, internals, and the shared-venv dependency note. Read when touching any helper script.
- `render-mcp.md`: The `pmkit-render` MCP server (`mcp/render_server.py`) — its two tools, setup/run scripts, registration, and headless-Chromium rendering. Read when changing rendering or MCP wiring.
- `development.md`: How to make and verify changes — the Python environment, compile checks, and the end-to-end dry-run recipe used to validate the state machine without spawning real Claude workers. Read before editing and to test changes.
- `monitoring-and-lifecycle.md`: The run lifecycle as seen from outside — the `status` file values, the combined Monitor (`RUNNER_DONE` / `RUNNER_DEAD` / `REVIEW_PENDING`), the wrap-up + finalize flow, and Telegram alerts. Read when changing how the PM observes or finishes a run.
