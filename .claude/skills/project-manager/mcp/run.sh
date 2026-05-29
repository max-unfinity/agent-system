#!/usr/bin/env bash
# Launcher for pmkit-render MCP server.
# Relies on PATH/VIRTUAL_ENV from ~/.claude/settings.json env or ~/.bashrc.
# Only sets PYTHONPATH (so render_server.py can import graph_utils).

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

export PYTHONPATH="$SKILL_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}"

exec python3 "$SKILL_DIR/mcp/render_server.py"
