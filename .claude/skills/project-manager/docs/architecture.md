# PMKit Architecture

PMKit turns a project into a dependency graph and executes each task as a Claude worker sub-agent, with a human gating the important moments. Three actors, with a deliberate split:

| Actor | What it is | Responsibility |
|-------|-----------|----------------|
| **PM agent** | Claude session running `SKILL.md` | All *judgment*: planning, specs, human gating, monitoring, crash recovery, final report. |
| **Runner** | Plain Python (`scripts/runner.py`) | All *mechanical execution*: derive ready tasks, launch workers, track completion. **No LLM calls.** |
| **Worker** | Claude session spawned per task | Does one task; contract in `worker-contract.md`. |

The point: keep the deterministic part deterministic — the runner decides nothing subjective, so it's trivial to reason about and restart. The PM's operational flow (four gated phases, launch/monitor/wrap-up/crash-recovery, CLAUDE.md & task-file rules) lives **only in `SKILL.md`**; these docs cover the internals beneath it.

## Generated project layout

`scripts/scaffold.py` stamps this structure into a target project:

```
<project>/
├── CLAUDE.md                     # PM-authored; auto-loads into every worker
├── agents/
│   ├── instructions.md           # worker contract (stamped from template)
│   ├── decisions.md              # single append-only decision log (stamped)
│   ├── roadmaps/
│   │   ├── <NNN>-<name>.yaml      # the task graph (PM-authored)
│   │   ├── <NNN>-<name>.png/.mmd  # rendered graph (MCP output)
│   │   └── <NNN>-final-report.md  # brief final report (PM-authored at wrap-up)
│   ├── tasks/
│   │   └── <id>-<name>.md         # one full brief per task (PM-authored)
│   ├── reports/
│   │   └── <id>-<name>.md         # one report per task (worker-authored)
│   └── .runner/                   # runner working dir (not authored by hand)
│       ├── runner.log             # tee'd stdout of the runner
│       ├── status                 # lifecycle: "running" | "complete"
│       ├── summary.json           # machine-readable final state
│       └── <id>.prompt.md         # generated launch prompt per task
└── docs/
    └── INDEX.md                   # doc index (workers append as they document)
```

## State without a state file

The runner keeps **no persistent state file** for task progress. Every tick it re-derives the full picture from two sources:

- **Disk**: does `agents/reports/<id>-<name>.md` exist, and what is its frontmatter `status`?
- **tmux**: is the `pmkit-<id>` session alive?

Plus one piece of in-memory-only bookkeeping: `launched` (a dict of task id → launch time *this run*), used only to detect a crash during the startup grace window.

This design makes restarts free: a re-launched runner honours finished reports, adopts live `pmkit-*` sessions as in-flight, and (re-)launches any task with neither a report nor a session. See `runner.md` for the exact state derivation.

## Data flow at a glance

```
PM agent ──writes──> roadmap YAML ──read by──> runner
                      task files   ──read by──> worker (via prompt)
                      CLAUDE.md    ──auto-loaded──> worker

runner ──spawns──> worker (tmux pmkit-<id>) ──writes──> report (status: ...)
                                              ──appends──> decisions.md
                                              ──appends──> docs/INDEX.md + docs

runner ──writes──> status file, summary.json
Monitor ──reads──> status + reports ──emits──> RUNNER_DONE / RUNNER_DEAD / REVIEW_PENDING
PM agent ──reads──> summary.json + reports + decisions.md ──writes──> final report
PM agent ──runs──> finalize.py (teardown)
```

See `runner.md`, `task-graph.md`, and `worker-contract.md` for each piece; `SKILL.md` for how the PM drives the run end to end.
