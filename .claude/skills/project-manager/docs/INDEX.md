# PMKit Documentation Index

Maintainer docs for the **project-manager** skill (*PMKit*) — how it works internally, so changes stay safe. The PM-facing operational flow lives in `SKILL.md`; these docs don't repeat it. (Distinct from `templates/docs/INDEX.md`, the empty index stamped into generated projects.)

- `architecture.md`: The two actors (PM agent vs. deterministic runner), generated-project layout, and the no-state-file design. **Read first.**
- `runner.md`: `scripts/runner.py` internals — the seven-state machine, `compute_states` fixpoint, launching, lifecycle `status` file, `summary.json`, CLI flags.
- `task-graph.md`: Roadmap YAML — `schema/graph.schema.json` fields, `graph_utils.py` validation checks, Mermaid rendering.
- `worker-contract.md`: The worker↔runner contract — report frontmatter → state mapping, the `decisions.md` log, templates/scaffold relationship.
- `scripts.md`: `scaffold.py`, `status.py`, `finalize.py`, `notify.py` internals and the shared-venv note.
- `render-mcp.md`: The `pmkit-render` MCP server — tools, setup/run, registration.
- `development.md`: Environment, compile checks, and the dry-run recipe for testing the state machine without real workers.
