# PMKit Architecture

PMKit turns a project into a dependency graph of tasks and executes each task as a Claude worker sub-agent, with a human gating the important moments. There are two distinct actors with a deliberate division of labour.

## The two actors

| Actor | What it is | Responsibility |
|-------|-----------|----------------|
| **PM agent** | A Claude session running `SKILL.md` | All *judgment*: planning, reducing uncertainty, writing specs, human gating, monitoring, crash recovery, writing the final report. |
| **Runner** | A plain Python process (`scripts/runner.py`) | All *mechanical execution*: derive which tasks are ready, launch workers, track completion. **No LLM calls** — pure control flow. |

The key idea: keep the deterministic parts deterministic. The runner never needs to "decide" anything subjective, so it can be plain code that's trivial to reason about and restart. Everything requiring intelligence lives in the PM agent or in the worker sub-agents.

A third actor, the **worker sub-agent**, is an interactive Claude session the runner spawns per task; its contract is `worker-contract.md`.

## The four-phase flow (PM agent)

Defined in `SKILL.md`, each phase gated on explicit user confirmation:

1. **Roadmap** (conversation only) — name the goal, enumerate tasks, drive out unknowns, set dependencies, pick model/effort per task, flag review tasks.
2. **Task Graph** — scaffold the project, write the roadmap YAML, render + validate it (via the `pmkit-render` MCP), iterate until approved.
3. **Preparation** — write `CLAUDE.md` (shared context) and one task file per node.
4. **Execution & monitoring** — launch the runner in tmux, health-check, arm a Monitor, handle review/done/crash events, write the final report, finalize.

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

See `runner.md`, `task-graph.md`, `worker-contract.md`, and `monitoring-and-lifecycle.md` for each piece.
