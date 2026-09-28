---
name: prune
description: Export a project's past Claude sessions (pruned to the conversation) into one resumable session, give the resume command, and optionally start it in tmux with a prompt.
argument-hint: "[natural-language request, or --since YYYY-MM-DD] [--user-only] [prompt]"
disable-model-invocation: false
---

# Prune: export past sessions into a resumable session

Two tools sit next to this file. `prune.py` prunes one session by id. `export.py` (imports `prune.py`) gathers every session of a project started on or after a date, prunes each to the human's and agent's messages, and writes one new session for `claude --resume`. Both have `--help`. Never pass `--md`, never pass `--frame-file`.

Today: !`date +%F`

Projects with transcripts (cwd — sessions, last activity):
!`python3 ~/.claude/skills/prune/projects.py`

## Parameters

The arguments are usually free-form natural language; flags may appear too. Extract from them:
- **project** — which of the projects above. Match loosely by name ("ovalbee", "this one" = current cwd). Pass its real cwd path to `export.py`.
- **since** — a date (`--since`). Resolve relative phrases ("since Monday", "last 3 days") against today.
- **user-only** — whether only the human's messages are wanted ("только мои сообщения", "without agent replies").
- **prompt** — the task for the new session: everything in the request that is addressed to the future session rather than describing the export. May be absent.

If the request names one session (by title or id), prune just that one. If neither project nor since is given, offer to prune only the current session (first option, recommended) or to pick a project and date. Its id is `$CLAUDE_CODE_SESSION_ID` in Bash. If only one of project/since is given, or either is ambiguous, ask for the missing one, offering the listed projects (most recent first) and a few concrete dates.

## Flow

No dry run and no confirmation before exporting: the export only adds a new transcript, nothing is overwritten.

1. Export right away with `--out new-session`; stdout is the new session id:
   - project: `export.py <project> --since <date> [--user-only] --out new-session`, the per-session list and KB totals go to stderr;
   - one session (the current one, or one the user named): `prune.py <id> [--human-only] --out new-session --cwd <its project dir>` — the Bash cwd may have drifted. A session named by its title is found by the `"aiTitle"` / `"customTitle"` records in `~/.claude/projects/<project-slug>/*.jsonl`.
2. Report: sessions taken (date, turns, name), skipped empty ones, pruned KB, and the command for the user to run themselves: `cd <project> && claude --resume <sid>`.
3. Then ask with AskUserQuestion whether to launch it in tmux and with which prompt. Offer the prompt extracted from the arguments, if any, as the first option; "no prompt" and "don't launch" as the others.
4. On a launch, follow the `start-claude` skill's policy (name, flags, report), with these differences:
   - start tmux in the project dir: `tmux new-session -d -s <name> -c <project> ...` — `--resume` only finds sessions of the cwd's project;
   - append `--resume <sid>` and, if there is a prompt, the prompt as the positional argument. Write the prompt to a file in the scratchpad and pass it as `"$(cat <file>)"` inside the `bash -lc '...'` string, so quotes, `$` and newlines survive;
   - the trust-folder and skip-permissions dialogs often do not appear. After ~2s capture the pane (`tmux capture-pane -pt <name>`) and send the dismissing keys only for a dialog actually on screen; blind keys land in the prompt box.
