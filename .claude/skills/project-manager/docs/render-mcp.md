# The `pmkit-render` MCP Server

Validates a task-graph YAML and renders it as a Mermaid diagram for human review. Exposed to the PM agent as an MCP server so Phase 2 can show the user the graph and iterate. Code: `mcp/render_server.py` (it imports `graph_utils` from `scripts/`, put on `PYTHONPATH` by `run.sh`).

> Doc nit: `mcp/README.md` says the server lives at `../scripts/render_server.py`; the actual path is `mcp/render_server.py`. Trust the code.

## Tools

Both call `load_and_validate()` first, so they fail loudly on a malformed graph — rendering doubles as graph validation.

- **`render_graph_png(roadmap_path) -> png path`** — preferred for human review. Writes a `.mmd` next to the roadmap, then runs `mmdc` (mermaid-cli) with `puppeteer-config.json` to produce a `.png`. Errors clearly if `mmdc` isn't on PATH. The PM sends the PNG to the user via the (separate) Telegram MCP.
- **`render_graph_mmd(roadmap_path) -> mmd path`** — writes just the `.mmd` text. Use when a diffable/git-trackable/markdown-embeddable diagram is wanted.

Output files are written next to the input roadmap (same stem, `.png`/`.mmd` suffix).

## Setup (`mcp/setup.sh`)

One-time, on a fresh machine. Installs:
- **nvm** + **Node.js 20**;
- **mermaid-cli** (`mmdc`) globally via npm;
- Python deps (`mcp[cli]`, `pyyaml`, `jsonschema`) into a venv (default `$HOME/max-eliseev-venv`);
- appends nvm + venv env to `~/.bashrc` (idempotent, guarded by a marker).

```bash
bash ~/.claude/skills/project-manager/mcp/setup.sh
```

## Launcher (`mcp/run.sh`)

Sources nvm, sets `PYTHONPATH` to `scripts/` (so `render_server.py` can `import graph_utils`), and `exec`s `python3 mcp/render_server.py`. Relies on PATH/VIRTUAL_ENV coming from `~/.bashrc` or Claude settings env.

## Registration

Registered in `~/.mcp.json` as `pmkit-render` (runs `run.sh`). `puppeteer-config.json` carries the headless-Chromium flags mermaid-cli needs to render without a display.

## Changing rendering

The diagram content comes from `graph_utils.to_mermaid()` (see `task-graph.md`) — change node labels/styling there, not in the server. The server only handles validation, file IO, and the `mmdc` invocation.
