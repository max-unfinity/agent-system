# Backlog

## IDEA-001. Claude Reincarnation / Context Refresh

Idea: let Claude summarize its current context, save to a file, and spawn a fresh session that reads it — effectively "reincarnating" with a clean context window but retained knowledge and a scope.

### Design
- **Trigger:** both manual (`/reincarnate` skill) and auto (Claude suggests when context gets heavy) - MCP.
- **Environment:** tmux — new session replaces the current pane
- **Context file:** project context, main goal, context files to read first, current tasks: what to do and what is done, decisions made, files created/modified, remaining work, session-specific user preferences, etc.

---

