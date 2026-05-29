# pmkit-render MCP Server

MCP server that validates PMKit task-graph YAML files against `schema/graph.schema.json` and renders them as Mermaid diagrams (`.mmd` text or `.png` image).

## Tools

### `render_graph_mmd`

Validates a task-graph YAML and writes a Mermaid `.mmd` file next to it. Returns the output path.

**When to use:** diffable/git-trackable diagrams, markdown embedding.

### `render_graph_png`

Validates a task-graph YAML and renders it to PNG via mermaid-cli (`mmdc`). Returns the output path.

**When to use:** human review, sending via Telegram MCP.

## Input format

The YAML must conform to `../schema/graph.schema.json`. See `../schema/example.graph.yaml` for a worked example.

Validation checks: JSON schema compliance, no duplicate task IDs, no self-dependencies, no unknown dependency references, no cycles.

## Setup

Run the setup script on a fresh machine:

```bash
bash ~/.claude/skills/project-manager/mcp/setup.sh
```

This installs nvm, Node.js 20, mermaid-cli, and the Python dependencies (`mcp`, `pyyaml`, `jsonschema`) into the venv.

## Files

| File | Purpose |
|------|---------|
| `run.sh` | Launcher — sets up nvm/venv env, runs `render_server.py` |
| `setup.sh` | One-time dependency setup |
| `puppeteer-config.json` | Chromium flags for headless mermaid rendering |
| `README.md` | This file |

The server code lives at `../scripts/render_server.py` (with `graph_utils.py` in the same directory).

## MCP registration

Registered in `~/.mcp.json` as `pmkit-render`.
