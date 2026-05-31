# Monitoring & Run Lifecycle

How the PM agent observes a run from outside the runner and brings it to a clean close. This is the part that changed most recently — read it alongside `runner.md`.

## The lifecycle status file

`agents/.runner/status`, written by the runner's `write_run_status()`:

- `running` — at startup.
- `complete` — after a clean finish (last thing `main()` does).

A crash or `kill` leaves it at `running` (or absent). There is no `crashed` value on purpose: **absence of `complete` is the crash signal**, which survives hard kills that can't run cleanup. This is the foundation for telling success from crash.

## The combined Monitor

The PM arms one persistent Monitor (command in `SKILL.md` Phase 4). It loops every 15s and emits at most a handful of events, breaking on the terminal one:

| Event | Condition | PM reaction |
|-------|-----------|-------------|
| `REVIEW_PENDING <report>` | A report has `status: review` (deduped via a `seen` set, so once per report). | Validate the review task (see below). Non-terminal — the monitor keeps running. |
| `RUNNER_DONE` | `pmkit-runner` session gone **and** `status` == `complete`. | Wrap-up. Terminal — monitor breaks. |
| `RUNNER_DEAD` | `pmkit-runner` session gone **and** `status` != `complete`. Includes the last 30 log lines. | Crash recovery. Terminal — monitor breaks. |

This fixes the old behaviour where the monitor watched only `tmux has-session` and emitted `RUNNER_DEAD` on **every** finish — a clean completion looked identical to a crash. Now the status file disambiguates them.

> Note for Monitor authors: each stdout line becomes a notification; the monitor must cover *all* terminal states, not just the happy path — which is why both DONE and DEAD are emitted from the same session-gone branch.

## Review-task flow

1. Worker on a `review: true` task reports `status: review` (the runner injects this instruction into its prompt).
2. Runner holds the task in `REVIEW`: dependents stay PENDING (not blocked), and REVIEW counts as "active" so the runner keeps polling rather than exiting.
3. Runner sends a one-time Telegram alert; the Monitor emits `REVIEW_PENDING`; `status.py` shows "AWAITING YOUR VALIDATION".
4. PM inspects the output + report, presents to the user.
5. **Approve** → edit the report `status: review` → `success`; next tick → DONE → dependents launch. **Reject** → set `failed` (dependents BLOCKED), or delete the report and relaunch the task to redo it.

## Wrap-up (on `RUNNER_DONE`)

The runner writes no prose report — the PM does:
1. Read `agents/.runner/summary.json` (per-task state + counts + `all_success`), skim `agents/reports/`, read `agents/decisions.md`.
2. Write a **brief** `agents/roadmaps/<NNN>-final-report.md` — what got built, per-task outcome (flag failed/blocked), key decisions, anything the user should know. A few short paragraphs.
3. Send it via the Telegram MCP and present in-session.
4. **Wait for user approval of the final report.**
5. On approval, run `finalize.py` to tear down all `pmkit-*` sessions (and run any future post-run steps).

## Crash recovery (on `RUNNER_DEAD`)

Up to 3 attempts: read `runner.log`, diagnose, fix, relaunch (same command — the log is overwritten), re-run the startup health check, re-arm the Monitor. After 3 failures, stop and report to the user with the log and findings. Because the runner derives state from disk + tmux, relaunching safely resumes: finished reports are honoured, live sessions adopted, unstarted tasks (re-)launched.
