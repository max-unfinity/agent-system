#!/usr/bin/env python3
"""PMKit runner — deterministic DAG executor (Option A).

Reads a task-graph YAML and drives it to completion. Each ready task is launched
as an interactive Claude session in its own tmux session (`pmkit-<id>`), so you can
attach and watch (or answer a worker's CLI question). The runner needs no LLM
judgment of its own — control flow is pure code.

State is reconstructed from disk + tmux each tick; there is no separate state file:

  DONE     report agents/reports/<id>-<name>.md exists with `status: success`
  FAILED   report exists with status != success, OR launched-this-run but the
           tmux session died with no report (crash), past a startup grace period
  BLOCKED  some dependency is FAILED or BLOCKED (transitively) -> never runs
  RUNNING  tmux session alive and no report yet (or within startup grace)
  READY    all deps DONE and not yet launched
  PENDING  deps not all DONE yet

A task launches only when all its deps are DONE. On any failure, the dependent
sub-graph is blocked and never runs (no retries — by design).

Because there's no state file, a restart re-derives everything: finished reports
are honored, live `pmkit-*` sessions are adopted as in-flight, and a task with no
report and no session is simply (re-)launched.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import yaml

from graph_utils import GraphError, load_and_validate

PENDING, READY, RUNNING, DONE, FAILED, BLOCKED = (
    "pending", "ready", "running", "done", "failed", "blocked",
)
TERMINAL = {DONE, FAILED, BLOCKED}

# Outer shell runs tmux; tmux runs the inner `sh -c` command. "$(cat file)" is
# safe for arbitrary prompt content (no re-splitting, no quote reinterpretation).
DEFAULT_LAUNCH = "tmux new-session -d -s {session} -c {cwd} '{claude_cmd} \"$(cat {prompt_file})\"'"


# ---------- disk / tmux probes ----------

def session_name(prefix: str, tid: str) -> str:
    return f"{prefix}-{tid}"


def tmux_alive(session: str) -> bool:
    try:
        return subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True,
        ).returncode == 0
    except FileNotFoundError:
        return False  # no tmux -> nothing is "alive" (launch itself will error loudly)


def report_path(project: Path, task: dict) -> Path:
    return project / "agents" / "reports" / f"{task['id']}-{task['name']}.md"


def read_status(path: Path):
    """Return the frontmatter `status` ('success'/'failed'/...) or None if no report."""
    if not path.exists():
        return None
    text = path.read_text()
    if not text.lstrip().startswith("---"):
        return "failed"  # report exists but malformed -> treat as failure, loudly
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "failed"
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return "failed"
    return fm.get("status", "failed")


# ---------- state computation ----------

def compute_states(project, tasks, launched, prefix, grace):
    """launched: dict task_id -> launch monotonic time (in-memory, this run only)."""
    deps = {t["id"]: list(t["deps"]) for t in tasks}
    state: dict[str, str | None] = {}
    now = time.monotonic()

    for t in tasks:
        tid = t["id"]
        st = read_status(report_path(project, t))
        if st == "success":
            state[tid] = DONE
        elif st is not None:
            state[tid] = FAILED
        elif tmux_alive(session_name(prefix, tid)):
            state[tid] = RUNNING
        elif tid in launched:
            # we started it; no report and session gone
            state[tid] = RUNNING if (now - launched[tid]) <= grace else FAILED
        else:
            state[tid] = None  # resolve via deps below

    # Fixpoint: propagate BLOCKED, settle READY/PENDING.
    changed = True
    while changed:
        changed = False
        for tid in state:
            if state[tid] in TERMINAL or state[tid] == RUNNING:
                continue
            ds = [state[d] for d in deps[tid]]
            if any(d in (FAILED, BLOCKED) for d in ds):
                new = BLOCKED
            elif all(d == DONE for d in ds):
                new = READY
            else:
                new = PENDING
            if state[tid] != new:
                state[tid] = new
                changed = True
    return state


# ---------- launching ----------

def build_prompt(task: dict, instructions: str) -> str:
    return (
        f"{instructions}\n\n"
        "---\n\n"
        f"You are assigned task `{task['id']}`.\n"
        f"Your task file: {task['file']}\n"
        f"Read it now and execute it following the phases above.\n"
        f"Write your report to agents/reports/{task['id']}-{task['name']}.md when done.\n"
    )


def task_claude_cmd(task: dict, base_cmd: str) -> str:
    """Build the claude command for a task, applying per-task model/effort overrides."""
    cmd = base_cmd
    if task.get("model"):
        cmd += f" --model {task['model']}"
    if task.get("effort"):
        cmd += f" --effort {task['effort']}"
    return cmd


def launch(project: Path, task: dict, args, instructions: str) -> None:
    runner_dir = project / "agents" / ".runner"
    runner_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = runner_dir / f"{task['id']}.prompt.md"
    prompt_file.write_text(build_prompt(task, instructions))

    sess = session_name(args.prefix, task["id"])
    claude_cmd = task_claude_cmd(task, args.claude_cmd)
    cmd = args.launch_template.format(
        session=sess, cwd=str(project),
        claude_cmd=claude_cmd, prompt_file=str(prompt_file),
    )
    if args.dry_run:
        print(f"[dry-run] launch {sess}: {cmd}")
        return
    subprocess.run(cmd, shell=True, check=True)
    print(f"launched {sess}  ({task['id']}-{task['name']})")


# ---------- finalization ----------

def collate_adrs(project: Path) -> None:
    adr_dir = project / "agents" / "adr"
    adrs = sorted(adr_dir.glob("*.md")) if adr_dir.exists() else []
    out = [
        "# Project Decision Log",
        "",
        "Collated Architecture Decision Records (ADRs) written by sub-agents.",
        "",
    ]
    if not adrs:
        out.append("_No decisions recorded yet._")
    for a in adrs:
        out += [f"## {a.stem}", "", a.read_text().strip(), "", "---", ""]
    (project / "agents" / "project.md").write_text("\n".join(out) + "\n")


def write_final_report(project: Path, data: dict, state: dict) -> Path:
    rid = data["roadmap_id"]
    tasks = data["tasks"]
    lines = [
        f"# Final report — roadmap {rid}: {data['project']}",
        "",
        "## Task status",
        "",
        "| id | name | status | report |",
        "|----|------|--------|--------|",
    ]
    for t in tasks:
        rp = f"agents/reports/{t['id']}-{t['name']}.md"
        lines.append(f"| {t['id']} | {t['name']} | {state[t['id']]} | `{rp}` |")

    fails = [t for t in tasks if state[t["id"]] in (FAILED, BLOCKED)]
    lines += ["", "## Failures & blocked", ""]
    if not fails:
        lines.append("None — all tasks completed successfully.")
    else:
        for t in fails:
            lines.append(
                f"- **{t['id']} {t['name']}** — {state[t['id']]}. "
                f"See `agents/reports/{t['id']}-{t['name']}.md`."
            )

    lines += [
        "",
        "## Notes",
        "",
        "Per-task difficulties, surprises and insights are in each task's report. "
        "Technical decisions are collated in `agents/project.md`.",
        "",
    ]
    fr = project / "agents" / "roadmaps" / f"{rid}-final-report.md"
    fr.write_text("\n".join(lines))
    return fr


def finalize(project: Path, data: dict, state: dict, args) -> None:
    fr = write_final_report(project, data, state)
    collate_adrs(project)
    print(f"wrote {fr}")
    print(f"wrote {project / 'agents' / 'project.md'}")

    if args.no_notify:
        return
    try:
        import notify
        notify.send_document(fr, caption=f"Final report — {data['project']} ({data['roadmap_id']})")
        print("final report sent via Telegram")
    except Exception as e:  # noqa: BLE001 - never let notification kill the run
        print(f"Telegram notification skipped: {e}")


# ---------- main loop ----------

def main() -> None:
    ap = argparse.ArgumentParser(description="PMKit DAG runner.")
    ap.add_argument("--project", type=Path, default=Path("."), help="project root")
    ap.add_argument("--roadmap", type=Path, required=True, help="path to roadmap YAML")
    ap.add_argument("--max-concurrency", type=int, default=1,
                    help="max workers in flight. Keep 1 unless parallel branches "
                         "are known not to share a resource (e.g. the GPU).")
    ap.add_argument("--poll", type=float, default=10.0, help="poll interval seconds")
    ap.add_argument("--startup-grace", type=float, default=20.0,
                    help="seconds to wait for a launched session to appear before "
                         "treating a missing session as a crash")
    ap.add_argument("--prefix", default="pmkit", help="tmux session name prefix")
    ap.add_argument("--claude-cmd", default="claude",
                    help="how to invoke an interactive worker (add flags/model here)")
    ap.add_argument("--launch-template", default=DEFAULT_LAUNCH,
                    help="tmux launch template; placeholders: {session} {cwd} "
                         "{claude_cmd} {prompt_file}")
    ap.add_argument("--dry-run", action="store_true", help="print launches, don't run them")
    ap.add_argument("--once", action="store_true", help="single tick (for testing)")
    ap.add_argument("--no-notify", action="store_true", help="skip Telegram final report")
    args = ap.parse_args()

    project = args.project.resolve()
    try:
        data = load_and_validate(args.roadmap)
    except GraphError as e:
        print(f"ERROR: invalid roadmap: {e}", file=sys.stderr)
        sys.exit(1)

    instr_path = project / "agents" / "instructions.md"
    if not instr_path.exists():
        print(f"ERROR: missing {instr_path} (run scaffold first)", file=sys.stderr)
        sys.exit(1)
    instructions = instr_path.read_text()
    tasks = data["tasks"]

    launched: dict[str, float] = {}
    announced_fail: set[str] = set()
    print(f"runner: {data['project']} roadmap {data['roadmap_id']} "
          f"({len(tasks)} tasks), max-concurrency={args.max_concurrency}")

    while True:
        state = compute_states(project, tasks, launched, args.prefix, args.startup_grace)

        running = sum(1 for s in state.values() if s == RUNNING)
        for t in tasks:
            if running >= args.max_concurrency:
                break
            if state[t["id"]] == READY and t["id"] not in launched:
                launch(project, t, args, instructions)
                launched[t["id"]] = time.monotonic()
                running += 1

        state = compute_states(project, tasks, launched, args.prefix, args.startup_grace)

        # one-time failure alerts
        if not args.no_notify:
            for tid, s in state.items():
                if s == FAILED and tid not in announced_fail:
                    announced_fail.add(tid)
                    try:
                        import notify
                        notify.send_message(f"PMKit: task {tid} FAILED — dependent tasks blocked.")
                    except Exception:  # noqa: BLE001
                        pass

        counts = {k: sum(1 for s in state.values() if s == k)
                  for k in (DONE, RUNNING, PENDING, READY, FAILED, BLOCKED)}
        print(f"tick: done={counts[DONE]} running={counts[RUNNING]} "
              f"ready={counts[READY]} pending={counts[PENDING]} "
              f"failed={counts[FAILED]} blocked={counts[BLOCKED]}")

        active = counts[RUNNING] + counts[READY] + counts[PENDING]
        if active == 0 or args.once:
            break
        time.sleep(args.poll)

    final_state = compute_states(project, tasks, launched, args.prefix, args.startup_grace)
    finalize(project, data, final_state, args)


if __name__ == "__main__":
    main()
