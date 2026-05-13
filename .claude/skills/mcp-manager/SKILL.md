---
name: mcp-manager
description: Add, remove, generate, or configure MCP servers and permissions in Claude Code. Use when user ask to work with MCPs.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit
effort: high
model: sonnet
---

# MCP Manager Skill

## Defaults

- **Scope**: user — unless user says "project" or "for this project"
- **Language for generated code**: Python (FastMCP); use TypeScript only if the target has a significantly better JS/TS SDK, or the project is TypeScript-heavy
- **Auto-allow permissions**: yes by default — add `mcp__<name>__*` to `permissions.allow` automatically
  - **Ask first** if the server exposes: filesystem write access, shell/command execution, defines many (>10) tools (context noise), or connections to critical production systems

## Config file locations

| Purpose | Path |
|---------|------|
| User MCP servers | `~/.mcp.json` (or `~/.claude.json`) → key `mcpServers` |
| Project MCP servers | `.mcp.json` at project root → key `mcpServers` |
| User permissions | `~/.claude/settings.json` → key `permissions` |
| Project permissions | `.claude/settings.json` → key `permissions` |
| User env vars | `~/.claude/settings.json` → key `env` |

## Code output locations

- User scope: `~/mcp-servers/<name>/`
- Project scope: `<cwd>/mcp-servers/<name>/`

## Permission syntax

```
mcp__servername__toolname    # specific tool
mcp__servername__*           # all tools from server (wildcard)
```

Server name in permission rules = the `mcpServers` key (hyphens are kept as-is; Claude Code handles them).

## Workflow

### Step 1 — Ask before diving in (if ambiguous)

Ask clarifying questions when any of these are unclear:
- What tools/capabilities the server should expose
- What API, service, or data source it connects to
- Any credentials or auth requirements

Do not ask about language or file location — decide those yourself.

### Step 2A — Creating a new MCP server (code generation)

1. Resolve ambiguities
2. Read the appropriate template: `templates/python-server.md` or `templates/typescript-server.md`
3. Generate code into the correct output path
4. Create dependency file (`requirements.txt` or `package.json`)
5. Register the server in the config file (Step 2B)
6. Auto-allow permissions (or ask if safety heuristic triggers)

### Step 2B — Registering an existing server

1. Determine transport: `stdio` for local binaries/scripts, `http` for remote URLs
2. Read and edit the correct config file (user or project scope)
3. Add entry under `mcpServers`
4. Auto-allow permissions (or ask if safety heuristic triggers)

### Step 2C — Removing a server

1. Remove from `mcpServers` in the correct config file
2. Remove matching rules from `permissions.allow` and `permissions.ask`

### Step 2D — Permissions only

Edit `permissions` in the appropriate `settings.json`. Add rules to `allow` or `ask`.

## Config reference

### stdio — Python script (user scope)

```json
{
  "mcpServers": {
    "my-server": {
      "type": "stdio",
      "command": "python3",
      "args": ["mcp-servers/my-server/main.py"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

### stdio — npx package

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

### http — remote server

```json
{
  "mcpServers": {
    "remote-api": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    }
  }
}
```

### Auto-allow all tools from a server

```json
{
  "permissions": {
    "allow": [
      "mcp__my-server__*"
    ]
  }
}
```

## Supporting templates

- `templates/python-server.md` — FastMCP starter, tool patterns, dependency setup
- `templates/typescript-server.md` — Node.js MCP SDK starter
