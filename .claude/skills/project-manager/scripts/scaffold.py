#!/usr/bin/env python3
"""Scaffold a new PMKit project: create the directory structure and stamp templates.

Usage:
    python scaffold.py --project /path/to/project
    python scaffold.py --project . --name "My Project"

Idempotent: re-running won't clobber existing files unless --force.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

TOOLKIT = Path(__file__).resolve().parent.parent
TEMPLATES = TOOLKIT / "templates"

DIRS = [
    "agents/roadmaps",
    "agents/tasks",
    "agents/reports",
    "agents/adr",
    "docs",
]


def stamp(src: Path, dst: Path, *, overwrite: bool) -> None:
    if dst.exists() and not overwrite:
        print(f"  skip (exists): {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  wrote:         {dst}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Scaffold a PMKit project.")
    ap.add_argument("--project", type=Path, default=Path("."), help="target project root")
    ap.add_argument("--name", default=None, help="project name (unused, kept for compat)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing instructions.md")
    args = ap.parse_args()

    root = args.project.resolve()
    print(f"Scaffolding PMKit project at {root}\n")

    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
        print(f"  dir:           {root / d}")

    stamp(TEMPLATES / "agents" / "instructions.md",
          root / "agents" / "instructions.md", overwrite=args.force)

    stamp(TEMPLATES / "docs" / "INDEX.md",
          root / "docs" / "INDEX.md", overwrite=False)

    print("\nDone.")


if __name__ == "__main__":
    main()
