# Worker Sub-agent Contract

A worker is an interactive Claude session the runner spawns per task (tmux `pmkit-<id>`). Its instructions are `templates/agents/instructions.md`, stamped by `scaffold.py` into each project as `agents/instructions.md` and prepended by the runner to every launch prompt. The worker's behaviour (its six phases, what it's given, how it documents) is **defined in that template** — edit it there. This doc covers only the parts the *runner code* depends on.

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

A single append-only file (stamped from `templates/agents/decisions.md`): one terse bullet per decision, with reasoning. Workers only append; nothing collates or rewrites it. The PM reads it at wrap-up. This replaced the old per-file ADR scheme (`agents/adr/*.md` collated into `agents/project.md`) — too much text for too little value; don't reintroduce per-decision files.

## Editing the contract

Edit the **template** (`templates/agents/instructions.md`), not a generated project's copy. The runner reads the *generated* `agents/instructions.md` at launch, so a project scaffolded before your change keeps its old contract until re-stamped with `scaffold.py --force` (see `scripts.md`).
