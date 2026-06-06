#!/usr/bin/env python3
"""PMKit runner — deterministic DAG executor (Option A).

Reads a task-graph YAML and drives it to completion. Each ready task is launched
as an interactive Claude session in its own tmux session (`pmkit-<id>`), so you can
attach and watch (or answer a worker's CLI question). The runner needs no LLM
judgment of its own — control flow is pure code.

State is reconstructed from disk + tmux each tick; there is no separate state file:

  DONE     report agents/reports/<id>-<name>.md exists with `status: success`
  REVIEW   report exists with `status: review` — a review-type task finished its
           work and is waiting for the user to validate it. Dependents stay
           PENDING (not blocked) until the user flips the report to success/failed.
  FAILED   report exists with status not in {success, review}, OR launched-this-run
           but the tmux session died with no report (crash), past a startup grace.
  BLOCKED  some dependency is FAILED or BLOCKED (transitively) -> never runs
  RUNNING  tmux session alive and no report yet (or within startup grace)
  READY    all deps DONE and not yet launched
  PENDING  deps not all DONE yet (includes deps still in REVIEW)

A task launches only when all its deps are DONE. On any failure, the dependent
sub-graph is blocked and never runs (no retries — by design). A task in REVIEW
keeps the runner alive (it polls) so that when the user validates it (editing the
report's `status:` to `success`), the next tick launches its dependents.

Because there's no state file, a restart re-derives everything: finished reports
are honored, live `pmkit-*` sessions are adopted as in-flight, and a task with no
report and no session is simply (re-)launched.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

from graph_utils import GraphError, load_and_validate

PENDING, READY, RUNNING, DONE, FAILED, BLOCKED, REVIEW = (
    "pending", "ready", "running", "done", "failed", "blocked", "review",
)
TERMINAL = {DONE, FAILED, BLOCKED}


def log(msg: str) -> None:
    """Timestamped, flushed log line. flush=True defeats tee/pipe buffering so
    `agents/.runner/runner.log` is populated live rather than only at exit."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def write_run_status(project: Path, status: str) -> None:
    """Record the runner's own lifecycle so a monitor can tell a clean finish from
    a crash. Written 'running' at startup and 'complete' on a clean exit; if the
    process dies (crash/kill) the file is left at 'running' — i.e. anything other
    than 'complete' when the tmux session is gone means the run did NOT finish."""
    d = project / "agents" / ".runner"
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status + "\n")


def ensure_trusted(project: Path) -> None:
    """Pre-accept Claude Code's first-run folder-trust dialog for the project.
    A detached worker hits that prompt before any tool runs and would hang on it
    forever (--dangerously-skip-permissions skips tool prompts, not this gate).
    Trust lives in ~/.claude.json under projects[<abs>].hasTrustDialogAccepted."""
    cfg = Path.home() / ".claude.json"
    try:
        data = json.loads(cfg.read_text()) if cfg.exists() else {}
        entry = data.setdefault("projects", {}).setdefault(str(project), {})
        if entry.get("hasTrustDialogAccepted") is True:
            return
        entry["hasTrustDialogAccepted"] = True
        entry.setdefault("allowedTools", [])
        cfg.write_text(json.dumps(data, indent=2))
        print(f"trust: pre-accepted folder-trust dialog for {project}")
    except Exception as e:  # never block a run on this
        print(f"WARNING: could not pre-accept folder trust ({e}); "
              "workers may hang on the trust prompt", file=sys.stderr)

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
        elif st == "review":
            state[tid] = REVIEW
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
            if state[tid] in TERMINAL or state[tid] in (RUNNING, REVIEW):
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
    prompt = (
        f"{instructions}\n\n"
        "---\n\n"
        f"You are assigned task `{task['id']}`.\n"
        f"Your task file: {task['file']}\n"
        f"Read it now and execute it following the phases above.\n"
        f"Write your report to agents/reports/{task['id']}-{task['name']}.md when done.\n"
    )
    if task.get("review"):
        prompt += (
            "\nIMPORTANT — this is a REVIEW task: its output must be validated by a "
            "human before the project proceeds. When your work is fully done and "
            "self-verified, set `status: review` (NOT `success`) in your report "
            "frontmatter. Use `status: failed` only if you could not complete the "
            "work. The user will inspect your output and either approve it (the "
            "project then continues) or send it back.\n"
        )
    return prompt


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
        log(f"[dry-run] launch {sess}: {cmd}")
        return
    subprocess.run(cmd, shell=True, check=True)
    log(f"LAUNCH  {task['id']}-{task['name']}  -> tmux {sess} "
        f"({claude_cmd.split()[0]} model={task.get('model','default')} "
        f"effort={task.get('effort','default')})")


# ---------- finalization ----------

def write_summary(project: Path, data: dict, state: dict) -> Path:
    """Write a machine-readable run summary for the PM agent to consume.

    The PM reads this (plus each task's report and agents/decisions.md) and writes
    the brief human-facing final report itself — the runner no longer authors prose.
    """
    tasks = data["tasks"]
    counts = {k: sum(1 for t in tasks if state[t["id"]] == k)
              for k in (DONE, REVIEW, FAILED, BLOCKED, RUNNING, READY, PENDING)}
    summary = {
        "project": data["project"],
        "roadmap_id": data["roadmap_id"],
        "counts": counts,
        "all_success": all(state[t["id"]] == DONE for t in tasks),
        "tasks": [
            {
                "id": t["id"],
                "name": t["name"],
                "status": state[t["id"]],
                "report": f"agents/reports/{t['id']}-{t['name']}.md",
                "review": bool(t.get("review")),
            }
            for t in tasks
        ],
    }
    path = project / "agents" / ".runner" / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return path


def finalize(project: Path, data: dict, state: dict, args) -> None:
    path = write_summary(project, data, state)
    print(f"wrote {path}")
    print("Run finished. The PM agent will write and send the final report; "
          "session teardown happens via finalize.py after the user approves it.")


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
    ap.add_argument("--claude-cmd", default="claude --dangerously-skip-permissions",
                    help="how to invoke an interactive worker (add flags/model here). "
                         "Defaults to skipping permission prompts, since a detached "
                         "tmux worker that hits a prompt hangs silently.")
    ap.add_argument("--launch-template", default=DEFAULT_LAUNCH,
                    help="tmux launch template; placeholders: {session} {cwd} "
                         "{claude_cmd} {prompt_file}")
    ap.add_argument("--dry-run", action="store_true", help="print launches, don't run them")
    ap.add_argument("--once", action="store_true", help="single tick (for testing)")
    ap.add_argument("--no-notify", action="store_true", help="skip Telegram final report")
    args = ap.parse_args()

    project = args.project.resolve()
    roadmap = args.roadmap if args.roadmap.is_absolute() else project / args.roadmap
    try:
        data = load_and_validate(roadmap)
    except GraphError as e:
        print(f"ERROR: invalid roadmap: {e}", file=sys.stderr)
        sys.exit(1)

    instr_path = project / "agents" / "instructions.md"
    if not instr_path.exists():
        print(f"ERROR: missing {instr_path} (run scaffold first)", file=sys.stderr)
        sys.exit(1)
    instructions = instr_path.read_text()
    tasks = data["tasks"]

    ensure_trusted(project)

    launched: dict[str, float] = {}
    announced_fail: set[str] = set()
    announced_review: set[str] = set()
    print(f"runner: {data['project']} roadmap {data['roadmap_id']} "
          f"({len(tasks)} tasks), max-concurrency={args.max_concurrency}")

    write_run_status(project, "running")

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

        # one-time alerts: failures (block dependents) and review-pending (await user)
        if not args.no_notify:
            for tid, s in state.items():
                if s == FAILED and tid not in announced_fail:
                    announced_fail.add(tid)
                    try:
                        import notify
                        notify.send_message(f"PMKit: task {tid} FAILED — dependent tasks blocked.")
                    except Exception:  # noqa: BLE001
                        pass
                elif s == REVIEW and tid not in announced_review:
                    announced_review.add(tid)
                    try:
                        import notify
                        notify.send_message(
                            f"PMKit: task {tid} is awaiting your validation (status: review). "
                            f"Approve it by setting status: success in its report (or failed to reject)."
                        )
                    except Exception:  # noqa: BLE001
                        pass

        counts = {k: sum(1 for s in state.values() if s == k)
                  for k in (DONE, RUNNING, PENDING, READY, FAILED, BLOCKED, REVIEW)}
        print(f"tick: done={counts[DONE]} running={counts[RUNNING]} "
              f"ready={counts[READY]} pending={counts[PENDING]} "
              f"review={counts[REVIEW]} failed={counts[FAILED]} blocked={counts[BLOCKED]}")

        # REVIEW counts as active: keep polling so an approved task's dependents launch.
        active = counts[RUNNING] + counts[READY] + counts[PENDING] + counts[REVIEW]
        if active == 0 or args.once:
            break
        time.sleep(args.poll)

    final_state = compute_states(project, tasks, launched, args.prefix, args.startup_grace)
    finalize(project, data, final_state, args)
    write_run_status(project, "complete")


if __name__ == "__main__":
    main()
