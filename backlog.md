# Backlog

## IDEA-001. Claude Reincarnation / Context Refresh

Idea: let Claude summarize its current context, save to a file, and spawn a fresh session that reads it — effectively "reincarnating" with a clean context window but retained knowledge and a scope.

### Design
- **Trigger:** both manual (`/reincarnate` skill) and auto (Claude suggests when context gets heavy) - MCP.
- **Environment:** tmux — new session replaces the current pane
- **Context file:** project context, main goal, context files to read first, current tasks: what to do and what is done, decisions made, files created/modified, remaining work, session-specific user preferences, etc.

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

