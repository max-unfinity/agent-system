#!/usr/bin/env python3
"""PMKit render MCP server.

Exposes two tools to the PM agent. Both validate the task-graph YAML against
schema/graph.schema.json before doing anything, so they double as the PM's
"is my graph well-formed?" check.

  - render_graph_png(roadmap_path) -> png path   (preferred; for review via Telegram)
  - render_graph_mmd(roadmap_path) -> mmd path    (diffable / embeddable text)

The PM sends the resulting file to the user through the (separate) Telegram MCP.

Run standalone for the PM session via .mcp.json (see README). Requires `mmdc`
(mermaid-cli) on PATH for PNG rendering: npm install -g @mermaid-js/mermaid-cli
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from graph_utils import load_and_validate, to_mermaid

mcp = FastMCP("pmkit-render")

PUPPETEER_CFG = Path(__file__).resolve().parent / "puppeteer-config.json"


def _write_mmd(roadmap_path: str) -> Path:
    data = load_and_validate(roadmap_path)  # raises GraphError on bad graph
    out = Path(roadmap_path).with_suffix(".mmd")
    out.write_text(to_mermaid(data))
    return out


@mcp.tool()
def render_graph_mmd(roadmap_path: str) -> str:
    """Validate a task-graph YAML and write a Mermaid (.mmd) text file next to it.

    Returns the .mmd path. Use when you want a diffable, git-trackable, or
    markdown-embeddable diagram rather than an image.
    """
    return str(_write_mmd(roadmap_path))


@mcp.tool()
def render_graph_png(roadmap_path: str) -> str:
    """Validate a task-graph YAML and render it to a PNG via mermaid-cli.

    Returns the PNG path. This is the preferred tool for human review (e.g.
    sending the diagram through the Telegram MCP). Requires `mmdc` on PATH.
    """
    if shutil.which("mmdc") is None:
        raise RuntimeError(
            "mermaid-cli (mmdc) not found on PATH. "
            "Install with: npm install -g @mermaid-js/mermaid-cli"
        )
    mmd = _write_mmd(roadmap_path)
    png = Path(roadmap_path).with_suffix(".png")
    res = subprocess.run(
        ["mmdc", "-p", str(PUPPETEER_CFG), "-i", str(mmd), "-o", str(png)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"mmdc failed: {res.stderr.strip() or res.stdout.strip()}")
    return str(png)


if __name__ == "__main__":
    mcp.run()
