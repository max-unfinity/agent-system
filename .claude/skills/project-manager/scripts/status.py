#!/usr/bin/env python3
"""PMKit health check — one command to confirm a run is OK.

Prints, in one shot:
  - the runner's lifecycle status (running / complete / missing)
  - which pmkit-* tmux sessions are alive (runner + workers)
  - the current per-task state derived from disk reports + tmux
  - the tail of the runner log

Use it right after launching the runner (to confirm a clean first tick) and any
time you want a snapshot:

    python status.py --project <dir> --roadmap agents/roadmaps/<NNN>-<name>.yaml
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from graph_utils import GraphError, load_and_validate
from runner import (
    BLOCKED, DONE, FAILED, PENDING, READY, REVIEW, RUNNING,
    compute_states,
)


def alive_sessions(prefix: str) -> list[str]:
    try:
        out = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True,
        ).stdout
    except FileNotFoundError:
        return []
    return sorted(s for s in out.split() if s.startswith(prefix + "-"))


def main() -> None:
    ap = argparse.ArgumentParser(description="PMKit run health check.")
    ap.add_argument("--project", type=Path, default=Path("."), help="project root")
    ap.add_argument("--roadmap", type=Path, required=True, help="path to roadmap YAML")
    ap.add_argument("--prefix", default="pmkit", help="tmux session name prefix")
    ap.add_argument("--lines", type=int, default=15, help="log tail lines")
    args = ap.parse_args()

    project = args.project.resolve()
    runner_dir = project / "agents" / ".runner"

    status_file = runner_dir / "status"
    lifecycle = status_file.read_text().strip() if status_file.exists() else "(no status file — runner not started?)"
    print(f"runner lifecycle: {lifecycle}")

    sessions = alive_sessions(args.prefix)
    runner_up = f"{args.prefix}-runner" in sessions
    print(f"runner tmux session: {'ALIVE' if runner_up else 'not running'}")
    workers = [s for s in sessions if s != f"{args.prefix}-runner"]
    print(f"worker sessions alive: {', '.join(workers) if workers else 'none'}")

    try:
        data = load_and_validate(args.roadmap)
    except GraphError as e:
        print(f"\nERROR: invalid roadmap: {e}")
        return

    # Snapshot from disk + tmux only (no in-memory launch history): launched={}, grace 0.
    state = compute_states(project, data["tasks"], {}, args.prefix, 0.0)
    print("\nper-task state:")
    for t in data["tasks"]:
        flag = " [review-type]" if t.get("review") else ""
        print(f"  {t['id']} {t['name']}: {state[t['id']]}{flag}")

    counts = {k: sum(1 for s in state.values() if s == k)
              for k in (DONE, RUNNING, READY, PENDING, REVIEW, FAILED, BLOCKED)}
    print(f"\ncounts: done={counts[DONE]} running={counts[RUNNING]} "
          f"ready={counts[READY]} pending={counts[PENDING]} "
          f"review={counts[REVIEW]} failed={counts[FAILED]} blocked={counts[BLOCKED]}")

    awaiting = [t["id"] for t in data["tasks"] if state[t["id"]] == REVIEW]
    if awaiting:
        print(f"\nAWAITING YOUR VALIDATION: tasks {', '.join(awaiting)} — "
              f"approve by setting `status: success` in the report frontmatter.")

    log = runner_dir / "runner.log"
    if log.exists():
        tail = log.read_text().splitlines()[-args.lines:]
        print(f"\n--- last {len(tail)} log lines ---")
        for line in tail:
            print(line)
    else:
        print("\n(no runner.log yet)")


if __name__ == "__main__":
    main()
