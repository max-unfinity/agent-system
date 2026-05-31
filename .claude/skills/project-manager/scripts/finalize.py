#!/usr/bin/env python3
"""PMKit teardown — run once the user has approved the final report.

Kills every pmkit-* tmux session (the runner and any lingering worker sessions),
so nothing is left attached after a project wraps up. This is the single,
deliberate teardown point: worker sessions are intentionally kept alive during and
after the run (so their output stays inspectable) and only torn down here.

It is also the natural home for future post-run work — archiving the project,
packaging deliverables, kicking off a deploy. Add such steps below the teardown.

    python finalize.py --project <dir>
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def list_sessions(prefix: str) -> list[str]:
    try:
        out = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True,
        ).stdout
    except FileNotFoundError:
        return []
    return sorted(s for s in out.split() if s.startswith(prefix + "-"))


def main() -> None:
    ap = argparse.ArgumentParser(description="PMKit teardown / finalize.")
    ap.add_argument("--project", type=Path, default=Path("."), help="project root")
    ap.add_argument("--prefix", default="pmkit", help="tmux session name prefix")
    ap.add_argument("--dry-run", action="store_true", help="list sessions, don't kill")
    args = ap.parse_args()

    sessions = list_sessions(args.prefix)
    if not sessions:
        print(f"No {args.prefix}-* tmux sessions to close.")
    for s in sessions:
        if args.dry_run:
            print(f"[dry-run] would kill {s}")
            continue
        subprocess.run(["tmux", "kill-session", "-t", s], capture_output=True)
        print(f"closed {s}")

    # --- future post-run work goes here (archive, package, deploy, ...) ---

    print("Finalize complete.")


if __name__ == "__main__":
    main()
