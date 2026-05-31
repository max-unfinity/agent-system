# Worker Sub-agent Contract

A worker is an interactive Claude session the runner spawns per task (tmux `pmkit-<id>`). Its instructions come from `templates/agents/instructions.md`, which `scaffold.py` stamps into each project as `agents/instructions.md` and the runner prepends to every launch prompt. This doc summarises that contract so changes to it are deliberate.

## What the worker is given

- Its **task id** and **task-file path** (stated explicitly in the launch prompt — never guessed; the id names its outputs).
- `agents/tasks/<id>-<name>.md` — the full spec for THIS task.
- `CLAUDE.md` — auto-loaded global context (goal, approach, external inputs, layout). True for every task; not to be re-derived.
- `docs/INDEX.md` — index of existing project docs; consult before doing fresh research.

## The six phases

1. **Plan & explore** — read the task file, survey what exists, read `docs/INDEX.md`, produce a concrete plan and list genuine unknowns.
2. **Clarify (only if truly blocked)** — uncertainty should be resolved at planning time; only stop on a real blocker. If so: send a short Telegram note, then ask in output (the *user* answers in reply, not via Telegram).
3. **Solve & verify** — do the work, then actually verify it (run/test/sanity-check). Not done until verified. After ~5–10 failed attempts on one issue, finish with `failed`.
4. **Document** — write docs for anything built or learned into `docs/`, and add one line per new doc to `docs/INDEX.md`.
5. **Record decisions** — **append one bullet** to `agents/decisions.md` per non-trivial decision: what + why, 2–4 sentences, INDEX.md-style. No separate files, no long Context/Decision/Consequences sections, no rewriting existing entries.
6. **Report & reflect** — write `agents/reports/<id>-<name>.md`.

## Report frontmatter — the runner's contract

The report **must** start with YAML frontmatter whose `status` the runner reads:

```
---
status: success
---
```

| `status` | Worker uses it when… | Runner effect |
|----------|----------------------|---------------|
| `success` | Task fully done and verified (the default for ordinary tasks). | `DONE`; dependents become READY. |
| `failed` | Could not complete correctly. | `FAILED`; dependents BLOCKED. |
| `review` | **Only when the prompt said this is a review task** — work done + self-verified, but a human must validate. | `REVIEW`; dependents stay PENDING; runner keeps polling until the user flips it to `success`/`failed`. |

Anything else (or malformed frontmatter) → treated as `failed`, loudly. Below the frontmatter the worker reflects freely (what it did, what was hard, decisions logged) — kept focused, since the PM reads it to write the brief final report.

## The decisions log (`agents/decisions.md`)

Replaces the old multi-file ADR scheme. A single append-only file stamped from `templates/agents/decisions.md`. One bullet per decision, terse, with the reasoning. Workers append; nothing collates or rewrites it. The PM reads it at wrap-up to summarise key decisions.

> History: previously each decision was its own `agents/adr/<NNN>-<slug>.md` file, collated by the runner into `agents/project.md`. Both were removed — too much text for too little value. If you reintroduce structured decisions, do it without per-decision files.

## Templates and scaffold

`scripts/scaffold.py` stamps three template files into a new project:
- `templates/agents/instructions.md` → `agents/instructions.md` (overwrite only with `--force`).
- `templates/agents/decisions.md` → `agents/decisions.md` (never overwritten).
- `templates/docs/INDEX.md` → `docs/INDEX.md` (never overwritten).

When you change the worker contract, edit the **template**, not a generated project's copy. The runner reads the *generated* `agents/instructions.md` at launch, so a project scaffolded before your change keeps its old contract unless re-stamped with `--force`.
