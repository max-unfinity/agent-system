---
name: start-claude
description: Start a new Claude Code session in a detached tmux session with --remote-control enabled. Trigger on phrases like "start new claude", "new claude", "start claude session with remote control in tmux", "run claude with skip permissions".
allowed-tools: Bash
---

# Starting a new Claude session in tmux

Standing policy for ad-hoc Claude sessions (separate from the `claude-remote` systemd service which owns the fixed `claude` session).

## Default command

```
tmux new-session -d -s <session-name> "claude --verbose --remote-control <session-name>"
```

Then, after a 2-second sleep, send Enter to dismiss the initial trust-folder prompt:

```
sleep 2 && tmux send-keys -t <session-name> Enter
```

After starting, report the session name and `tmux attach -t <session-name>`.

## Skip-permissions mode

If the user says "skip permissions" / "with skip permissions" / "dangerously skip permissions", append `--dangerously-skip-permissions` to the claude invocation, and use this two-step confirmation instead of the single Enter:

```
sleep 2 && tmux send-keys -t <session-name> Enter           # trust folder
sleep 1 && tmux send-keys -t <session-name> Down Enter      # accept skip-permissions warning
```

## Session name

Format: `claude-<slug>-<HHMMSS>` where `<slug>` is a short, memorable label.

Pick `<slug>` in this order:
1. If the user described what the session is for (e.g. "new claude for debugging the auth flow"), derive a 1-3 word slug from that intent (e.g. `auth-debug`).
2. Otherwise infer from the current conversation context (recent file, feature, or task being discussed).
3. If no signal at all, fall back to just `claude-<HHMMSS>` with no slug.

Keep slugs lowercase, hyphen-separated, ≤20 chars total. `<HHMMSS>` is `$(date +%H%M%S)` and guarantees uniqueness.

## Overrides

If the user passes specific flags or options, use those and skip the corresponding defaults. `--verbose` and `--remote-control` are defaults — drop them only if the user explicitly asks for a non-remote-control session.
