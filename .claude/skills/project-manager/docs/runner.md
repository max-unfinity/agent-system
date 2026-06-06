# The Runner (`scripts/runner.py`)

A deterministic DAG executor. Reads a roadmap YAML and drives it to completion, launching each ready task as an interactive Claude session in its own tmux session (`pmkit-<id>`). No LLM judgment of its own — control flow is pure code.

## Task states

Seven states (constants near the top of the file):

| State | Meaning |
|-------|---------|
| `PENDING` | Not all deps are DONE yet (includes deps still in REVIEW). |
| `READY` | All deps DONE; not yet launched this run. |
| `RUNNING` | tmux session alive and no report yet, **or** within the startup grace window. |
| `DONE` | Report exists with `status: success`. |
| `REVIEW` | Report exists with `status: review` — a review task finished its work and awaits user validation. Dependents stay PENDING (not blocked); the runner keeps polling. |
| `FAILED` | Report exists with status not in {success, review}, **or** launched-this-run but the session died with no report (crash) past the startup grace. |
| `BLOCKED` | Some dependency is FAILED or BLOCKED (transitively) — never runs. |

`TERMINAL = {DONE, FAILED, BLOCKED}`. REVIEW is deliberately *not* terminal: it can still become DONE (user approves → `success`) or FAILED (user rejects → `failed`).

## State derivation — `compute_states()`

Called every tick. Two stages:

1. **Per-task direct read.** For each task, in priority order:
   - report `status: success` → `DONE`
   - report `status: review` → `REVIEW`
   - report exists, any other status → `FAILED`
   - else tmux `pmkit-<id>` alive → `RUNNING`
   - else launched this run → `RUNNING` if within `startup-grace`, else `FAILED` (crash with no report)
   - else `None` (resolve via deps next)
2. **Fixpoint over deps.** Repeatedly settle the `None` tasks: a task whose deps include any FAILED/BLOCKED becomes `BLOCKED`; a task whose deps are all DONE becomes `READY`; otherwise `PENDING`. Tasks already in TERMINAL, RUNNING, or REVIEW are skipped (they're settled).

`read_status()` parses the report's YAML frontmatter; a malformed/missing-frontmatter report is treated as `failed` loudly (never silently ignored).

## Launching — `launch()` / `build_prompt()` / `task_claude_cmd()`

- `build_prompt()` concatenates `agents/instructions.md` + a per-task tail naming the task id, its file, and where to write the report. **If the task has `review: true`**, it appends an instruction telling the worker to report `status: review` (not `success`) when done. The prompt is written to `agents/.runner/<id>.prompt.md`.
- `task_claude_cmd()` applies per-task overrides: appends `--model <model>` and/or `--effort <effort>` to the base `--claude-cmd`.
- `launch()` fills `DEFAULT_LAUNCH` (`tmux new-session -d -s {session} -c {cwd} '{claude_cmd} "$(cat {prompt_file})"'`) and runs it. The `"$(cat ...)"` form passes arbitrary prompt content safely (no re-splitting/quote reinterpretation).

The base command defaults to `claude --dangerously-skip-permissions` — a detached tmux worker that hits a permission prompt would hang silently, so prompts are skipped by design.

`ensure_trusted()` runs once at startup (in `main()`, before the loop): it sets `projects[<abs>].hasTrustDialogAccepted = true` in `~/.claude.json`. Claude Code shows a first-run "trust this folder" dialog that `--dangerously-skip-permissions` does **not** cover, so without this every worker in a fresh project hangs on it.

## The main loop — `main()`

1. Load + validate the roadmap (`load_and_validate`); exit non-zero on a bad graph.
2. Require `agents/instructions.md` to exist (else error — scaffold first).
3. `write_run_status(project, "running")`.
4. Each tick:
   - compute states; launch READY tasks up to `--max-concurrency`;
   - recompute; fire **one-time** alerts: `FAILED` → Telegram "task blocked", `REVIEW` → Telegram "awaiting validation" (tracked in `announced_fail` / `announced_review` sets);
   - print a `tick:` count line (includes `review=`);
   - **active** = RUNNING + READY + PENDING + REVIEW. If `active == 0` (or `--once`), break.
   - else `sleep(--poll)`.
5. On exit: recompute final state, `finalize()`, `write_run_status(project, "complete")`.

REVIEW counts as active so the loop keeps polling while a task waits for the user; once they flip the report to `success`, the next tick sees DONE and launches dependents.

## Lifecycle status file

`write_run_status()` writes `agents/.runner/status`:
- `running` — written at startup.
- `complete` — written after a clean finish.

If the process crashes or is killed, the file is **left at `running`** (or absent). So: a vanished `pmkit-runner` session with `status: complete` is a clean finish; anything else is a real crash. This is what lets the PM's Monitor tell `RUNNER_DONE` from `RUNNER_DEAD` (Monitor command in `SKILL.md` Phase 4). No separate `crashed` value on purpose — absence of `complete` *is* the crash signal, robust to hard kills that can't run cleanup.

## Finalization — `finalize()` / `write_summary()`

The runner does **not** write a prose report. `write_summary()` emits `agents/.runner/summary.json` for the PM agent to consume:

```json
{
  "project": "...", "roadmap_id": "001",
  "counts": {"done": N, "review": N, "failed": N, "blocked": N, "running": N, "ready": N, "pending": N},
  "all_success": true,
  "tasks": [{"id","name","status","report","review"}, ...]
}
```

The PM reads this + the per-task reports + `agents/decisions.md` and writes the brief final report itself. ADR collation and `agents/project.md` generation were removed — decisions now live in the single `agents/decisions.md`, appended by workers.

## CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--project` | `.` | Project root. |
| `--roadmap` | *(required)* | Path to roadmap YAML. |
| `--max-concurrency` | `1` | Max workers in flight. Raise only when parallel branches don't share a resource (e.g. the GPU). |
| `--poll` | `10.0` | Tick interval, seconds. |
| `--startup-grace` | `20.0` | Grace before a launched-but-missing session counts as a crash. |
| `--prefix` | `pmkit` | tmux session name prefix. |
| `--claude-cmd` | `claude --dangerously-skip-permissions` | Base worker invocation. Add global flags/model here. |
| `--launch-template` | `DEFAULT_LAUNCH` | tmux launch template; placeholders `{session} {cwd} {claude_cmd} {prompt_file}`. |
| `--dry-run` | off | Print launches, don't run them. |
| `--once` | off | Single tick (testing). |
| `--no-notify` | off | Skip all Telegram messages. |

## Testing the runner

`--dry-run` prints launch commands without spawning; `--once` runs a single tick. Full control-flow test recipe (fake reports, no real workers) in `development.md`.
