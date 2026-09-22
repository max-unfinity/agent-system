#!/usr/bin/env python3
"""List projects that have transcripts: real cwd, session count, last activity. Newest first."""

import datetime as dt
import glob
import json
import os

PROJECTS = os.path.expanduser("~/.claude/projects")
WORKTREE = "--claude-worktrees-"


def cwd_of(d: str) -> str | None:
    for p in glob.glob(os.path.join(d, "*.jsonl")):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                cwd = json.loads(line).get("cwd")
            except (json.JSONDecodeError, AttributeError):
                continue
            if cwd:
                return cwd
    return None


rows = {}
for d in sorted(glob.glob(os.path.join(PROJECTS, "*"))):
    name = os.path.basename(d)
    if not os.path.isdir(d) or name.startswith("-tmp-"):
        continue
    base = name.split(WORKTREE)[0]
    files = glob.glob(os.path.join(d, "*.jsonl"))
    r = rows.setdefault(base, {"cwd": None, "sessions": 0, "last": 0.0, "worktrees": 0})
    r["sessions"] += len(files)
    r["last"] = max([r["last"]] + [os.path.getmtime(f) for f in files])
    if name == base:
        r["cwd"] = cwd_of(d)
    else:
        r["worktrees"] += 1

for base, r in sorted(rows.items(), key=lambda kv: -kv[1]["last"]):
    if not r["sessions"]:
        continue
    last = dt.datetime.fromtimestamp(r["last"]).strftime("%Y-%m-%d %H:%M")
    wt = f", {r['worktrees']} worktrees" if r["worktrees"] else ""
    print(f"- {r['cwd'] or '? (' + base + ')'} — {r['sessions']} sessions{wt}, last {last}")
