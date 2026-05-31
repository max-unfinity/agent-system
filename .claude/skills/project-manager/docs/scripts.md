# Supporting Scripts

All live in `scripts/`. `runner.py` has its own doc (`runner.md`); this covers the rest. They share one dependency note (below).

## Shared dependency / environment note

`runner.py`, `status.py`, and `render_server.py` import `graph_utils`, which imports `yaml` and `jsonschema`; `notify.py` imports `requests`. These are **not** in the system Python. They live in the venv created by `mcp/setup.sh` (default `$HOME/max-eliseev-venv`), which is put on PATH via `~/.bashrc` / `~/.claude/settings.json` env. `status.py` and `finalize.py` `import` from `runner.py`/`graph_utils.py`, so run them with the **same interpreter as the runner**. `finalize.py` itself only uses the stdlib, but keep the habit. (`requirements.txt` pins `pyyaml`, `jsonschema`, `requests`, and `mcp`.)

## `scaffold.py` — create a project skeleton

```
python scaffold.py --project /path/to/project [--force]
```

Creates `agents/{roadmaps,tasks,reports}` and `docs/`, then stamps `instructions.md`, `decisions.md`, and `docs/INDEX.md` from `templates/`. Idempotent — existing files are skipped; `--force` overwrites only `instructions.md`. Note there is no longer an `agents/adr/` directory (removed with the ADR scheme).

## `status.py` — health check / live snapshot

```
python status.py --project <dir> --roadmap agents/roadmaps/<NNN>-<name>.yaml [--prefix pmkit] [--lines 15]
```

Prints, in one shot:
- runner **lifecycle** (`running` / `complete` / "no status file");
- whether the `pmkit-runner` session is ALIVE and which worker sessions are alive;
- **per-task state** (reusing the runner's `compute_states` with `launched={}`, `grace=0` — a pure disk+tmux snapshot) plus a counts line;
- an **AWAITING YOUR VALIDATION** line if any task is in `review`;
- the tail of `runner.log`.

This is the PM agent's one-command "is everything OK?" after launch, and any time thereafter.

## `finalize.py` — teardown after approval

```
python finalize.py --project <dir> [--prefix pmkit] [--dry-run]
```

Lists tmux sessions whose name starts with `<prefix>-` (so `pmkit-runner` and `pmkit-<id>` workers, but **not** unrelated sessions like `claude-pmkit-comfyui-*`, which don't start with `pmkit-`) and kills each. `--dry-run` lists without killing. Run by the PM agent **only after the user approves the final report** — it's the single deliberate teardown point, and the marked spot where future post-run work (archiving, packaging, deploy) would be added.

## `notify.py` — Telegram bot helper

The runner is plain code and can't use the Telegram MCP (that's for LLM agents), so it talks to the Bot API directly. Credentials load from env (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`) or the `.secrets` file next to the skill root.

- `send_message(text)` — failure/review alerts during a run.
- `send_document(path, caption)` — currently unused by the runner (the PM sends the final report via the Telegram MCP), kept for direct use / CLI.
- CLI: `python notify.py --message "..."` or `--document path --caption "..."`.

Every runner call site wraps `notify` in a try/except so a notification failure never kills the run; `--no-notify` skips them entirely.
