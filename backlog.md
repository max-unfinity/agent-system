# Backlog

## IDEA-001. Claude Reincarnation / Context Refresh

Idea: let Claude summarize its current context, save to a file, and spawn a fresh session that reads it — effectively "reincarnating" with a clean context window but retained knowledge and a scope.

### Design
- **Trigger:** both manual (`/reincarnate` skill) and auto (Claude suggests when context gets heavy) - MCP.
- **Environment:** tmux — new session replaces the current pane
- **Context file:** project context, main goal, context files to read first, current tasks: what to do and what is done, decisions made, files created/modified, remaining work, session-specific user preferences, etc.

---

## IDEA-003. claude-remote.service should auto-restart Claude on exit

Problem discovered 2026-06-06: I accidentally exited the always-on remote-control Claude session and expected the systemd service to bring it back automatically. It did not. The Claude remote-control process stayed dead until manually restarted (`sudo systemctl restart claude-remote.service`).

### Root cause

The unit `/etc/systemd/system/claude-remote.service` is a **fire-once launcher, not a supervisor**:

```ini
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/tmux new-session -d -s claude "/home/max_eliseev/.local/bin/claude --verbose --remote-control g5090-green"
ExecStartPost=/bin/sh -c 'sleep 3 && /usr/bin/tmux send-keys -t claude Enter'
ExecStop=/usr/bin/tmux kill-session -t claude
KillMode=none
# NO Restart= directive
```

- `tmux new-session -d` forks and exits immediately, so systemd's `ExecStart` only ever tracked the short-lived tmux launch command — never the `claude` grandchild process inside the session.
- `Type=oneshot` + `RemainAfterExit=yes` latch the unit to `active (exited)` forever, regardless of whether Claude is alive. This is why `systemctl status` looked healthy even though the session was dead (stale tmux socket left at `/tmp/tmux-1008/default`, `tmux ls` reported "no server running").
- No `Restart=` directive, and oneshot+detached-tmux can't auto-restart anyway because systemd has no handle on the actual process.

So: exit Claude → tmux window command ends → tmux session `claude` closes → tmux server dies → systemd notices nothing.

### Proposed fix (design decision pending)

Two options, pick one:

**A. Foreground + Restart (simplest, most reliable).** Drop tmux entirely; run Claude as the service's main process so systemd supervises and restarts it.
```ini
[Service]
Type=simple
ExecStart=/home/max_eliseev/.local/bin/claude --verbose --remote-control g5090-green
Restart=always
RestartSec=2
# remove RemainAfterExit, KillMode, ExecStop, ExecStartPost
```
Trade-off: lose `tmux attach` for manual interaction with the session.

**B. Keep tmux + Restart.** Wrapper that runs Claude in tmux and blocks (e.g. `tmux new-session -d ... \; wait`, or a pipe-pane/health approach) so systemd can supervise and restart while preserving manual attach. More moving parts. Alternative variant: keep the oneshot launcher but add a `.timer` or health-check unit that restarts the service when the `claude` tmux session is gone.

### Open questions
- Is manual `tmux attach` interactivity actually needed? If not, go with A.
- Do we want backoff/rate-limiting on restart to avoid crash loops (`StartLimitIntervalSec` / `StartLimitBurst`)?
- The `ExecStartPost` send-keys Enter hack — still needed in the new design, or was it working around a startup prompt?

---

## IDEA-002. Distributed Claude — SSH Remote Execution Skill

Idea: скилл, позволяющий Claude автоматически выполнять задачи на удалённых нодах через SSH. Основной use case — GPU-задачи: если GPU на текущем инстансе занята, Claude сам выбирает свободную ноду и запускает там новую Claude Code сессию с полным контекстом задачи.

### Design

- **Реализация:** Claude Code skill.
- **Конфиг нод:** отдельный файл с описанием доступных нод (hostname/IP, SSH credentials, доступные ресурсы — прежде всего GPU).
- **Discovery:** скилл умеет сам проверять состояние нод — какие GPU свободны/заняты, доступность ноды.
- **Автоматический выбор:** если GPU занята на текущей ноде, Claude автоматически находит свободную ноду и переносит задачу туда.
- **Передача контекста:** на удалённой ноде запускается новый процесс Claude Code через SSH, ему передаётся prompt с полной задачей и всем необходимым контекстом.
- **Синхронизация результатов:** зависит от задачи, решается в рамках скилла. Можно описать инструкции для конкретных сценариев (например, копирование Docker-образов между инстансами, rsync данных и результатов).
- **Файловая система:** ноды НЕ шарят FS — данные и артефакты нужно явно копировать через rsync/scp.

### Open Questions
- Формат конфиг-файла нод (YAML? JSON?).
- Как именно передавать большой контекст на удалённую сессию (prompt file? CLAUDE.md? набор файлов?).
- Нужен ли обратный канал: чтобы удалённая сессия могла отчитаться о результатах в исходную сессию (или достаточно проверять вручную / через discovery).
- Приоритизация нод (например, предпочитать ноды с более мощными GPU).

---

