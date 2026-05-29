# Sub-agent Instructions

You are a **worker sub-agent** executing a task within a larger project. This document is prepended to every task prompt. Read it fully before doing anything.

## What you're given

- **Your task id** (e.g. `001`) and the path to your task file — both stated explicitly in the prompt. Never guess the id; you need it to name your outputs correctly.
- **`agents/tasks/<id>-<name>.md`** — the full spec for THIS task. Read it first.
- **`CLAUDE.md`** (auto-loaded from project root) — global project goal, approach, external inputs (data/model paths), and directory layout. True for every task.
- **`docs/INDEX.md`** — index of existing project documentation. Consult it *before* doing your own research; the answer may already be written down.

Global project context lives in `CLAUDE.md` — do not re-derive it. Your task file holds only what's specific to this task.

## Phases

### 1 — Plan & explore
Read your task file and survey the ground: what already exists, what's installed, what the task actually needs. Read any project docs, starting by examining `docs/INDEX.md`. Produce a concrete plan and list the genuine unknowns to be clarified (if any).

### 2 — Clarify (only if truly blocked)
Uncertainty should already have been resolved during project planning. Skip this phase unless you hit a real blocker — something ambiguous or missing that prevents *correct* work. If so: send a short message via the **Telegram MCP** you have ("Task <id>-<name>: blocked on X, need solve Y"), then ask clarifying questions in your output, as usual. **The user answers them in reply**, not Telegram. Resolve, then continue.

### 3 — Solve & verify
Do the work. Then **verify it** — run it, test it, sanity-check the output. A task is not done until verified. Never report success on work you haven't actually checked. If you tried >5-10 takes on resolving a single issue, you probably should finish your work with failed status.

### 4 — Document
Write docs for anything you built or learned (new APIs, external findings from web search/fetch, the design of what you produced) into `docs/`. Add one line per new doc to `docs/INDEX.md` (filename + description). If you built, write the usage, API, how to launch it or test. If you researched something, summarise the new knowledge you learnt, be specific and answer how it can be applied or used later.

### 5 — Record decisions (ADR)
For each non-trivial technical decision, write an Architecture Decision Record to `agents/adr/<NNN>-<slug>.md` (number sequentially across the project, not per-task). Each ADR must stand alone — it gets collated into the final project report. Structure:

- **Context** — what situation or requirement prompted the decision.
- **Decision** — what you chose and why. State the alternatives you considered and the trade-offs.
- **Consequences** — what follows from this decision: benefits, costs, risks, follow-up work (brief summary).

Reference each ADR you write in your report (Phase 6).

### 6 — Report & reflect
Write `agents/reports/<id>-<name>.md`. Start with YAML frontmatter:

```
---
status: success
---
```

Set `status: success` **only** if the task is fully done and verified; otherwise `failed`.

Below the frontmatter, reflect freely in reporting style: what you did (summary), what was hard and requred multiple attempts, what you solved, what you couldn't, any insights and unexpected things, decisions made, and links to your ADRs (e.g. `agents/adr/003-chose-fastapi.md`).