---
name: skill-manager
description: Create, modify, or remove a Claude Code skill, use when the user asks to work with your skills.
allowed-tools: Bash Read Write Edit
argument-hint: <create|modify|remove> [skill-name]
---

## Skill locations

| Scope    | Path                                       |
| -------- | ------------------------------------------ |
| Personal | `~/.claude/skills/<name>/SKILL.md`         |
| Project  | `.claude/skills/<name>/SKILL.md`           |

Default to project scope unless the user says otherwise. Each skill is a directory; `SKILL.md` is the entrypoint. Supporting files (templates, scripts, reference docs) go in the same directory and are referenced from `SKILL.md`.

## Frontmatter — non-obvious fields

- **`description`** — the only part loaded every session; drives auto-invocation. Front-load the trigger case. Use natural-language phrases the user would actually type. Combined with `when_to_use`, capped at 1,536 chars in the index. **Keep it short — 1–2 sentences max.**
- **`when_to_use`** — extra trigger phrases, appended to `description`. **Omit unless the user explicitly asks for it.**
- **`disable-model-invocation: true`** — prevents Claude from auto-triggering.
- **`user-invocable: false`** — hides from `/` menu; Claude-only background knowledge. Skip this by default.
- **`allowed-tools`** — pre-approves tools for this skill's scope so Claude doesn't pause mid-task.
- **`context: fork`** — add it when the skill can be run in isolation by a spawned subagent. It won't have access to your conversation history, which reduces costs and context noise. Suggest this for skills that can be framed as standalone tasks.
- **`argument-hint`** — shown in autocomplete for a user; e.g. `[issue-number]`.
- **`effort`** — override reasoning depth. Options: `low`, `medium`, `high`, `xhigh`, `max`. Suggest an effort level for the user. Suggest `xhigh` or `max` for tasks that involves many steps, intelligent decisions, long-horizon planning; suggest `low` for simple mechanical tasks without need for thinking. Skip if unsure.
- **`model`** — override model for this skill. Options: `opus`, `sonnet`, `haiku`. Suggest `opus` for complex tasks with intelligent decision-making; `sonnet` for most tasks; `haiku` for simple tasks. Skip if unsure.

## Principles for a well-written skill

**Non-obvious content only.** DO NOT write anything Claude can infer from general knowledge, (e.g, common programming practices, common bash commands and examples), ask the user to frame user preferences instead. In SKILL.md only encode project-specific conventions, constraints that exist outside common practice, and user-defined preferences. The skill is a customized extension of Claude's general capabilities.

**Inject live context at load time.** Use `` !`command` `` to inline shell output before Claude sees the skill (initialization of knowledge and context that Claude will use). The command output replaces the placeholder, so Claude receives actual data, not the command itself. Use this if the skill obviously requires context or data that can be obtained programmatically.

**Write standing instructions, not one-time steps.** Skill content persists for the session. Frame as durable policy ("always X"), not imperative action ("now do X").

**Match invocation control to side-effect risk.** Anything that creates, modifies, sends, or destroys should have `disable-model-invocation: true`.

**Supporting files.** Skills can include multiple files in their directory. This keeps `SKILL.md` focused on the essentials while letting Claude access details *only when needed*. Rarely, when the skill requires detailed docs, API specifications, or example collections - they don't need to load into context every time the skill runs. Reference supporting files and their content description so Claude will decide when to load them. Docs can be divided into multiple files - pages, each with a specific focus, to find only the relevant one.

## Before writing a skill

You may ask questions to help framing what the skill should do and *how to do it effectively* (think on this to create effective skill solutions), which user-oriented practices must be considered, and ask for additional knowledge and context to add into the skill (if applicable). Before writing the skill, preview the skill's frontmatter to the user and ask confirmation.

## Removing a skill

To remove a skill, delete its root directory (skill-name).
