# Claude Code Skills Reference

All skills installed in the current system, grouped by source. Invoke via `/skill-name` or `Skill tool`.

---

## Superpowers Plugin (`superpowers:*`)

Workflow discipline skills — enforce best practices before/during coding.

| Skill | When to use | Example |
|---|---|---|
| `superpowers:using-superpowers` | Auto-loaded at session start; establishes skill lookup behavior | *(auto-invoked)* |
| `superpowers:brainstorming` | Before any creative work — features, components, new behavior | "Let's add retry logic to the API client" |
| `superpowers:writing-plans` | After brainstorm, before touching code — turns spec into bite-sized tasks | "Write a plan to refactor the auth module" |
| `superpowers:executing-plans` | Load a written plan and execute it with review checkpoints | "Execute the plan in `.claude/plans/auth-refactor.md`" |
| `superpowers:test-driven-development` | Before writing implementation code for any feature or bugfix | "Implement the `retry_on_failure` decorator" |
| `superpowers:systematic-debugging` | When hitting a bug, test failure, or unexpected behavior | "My test passes locally but fails in CI" |
| `superpowers:verification-before-completion` | Before claiming work is done / before committing or PRing | "I think the bug is fixed, let me verify" |
| `superpowers:requesting-code-review` | After finishing a feature or before merging | "Review what I just implemented" |
| `superpowers:receiving-code-review` | When processing code review feedback — enforce rigor, not blind compliance | "Apply these review comments" |
| `superpowers:subagent-driven-development` | Execute a plan's tasks in current session using isolated subagents | "Run the plan tasks using subagents" |
| `superpowers:dispatching-parallel-agents` | 2+ independent tasks with no shared state | "Refactor module A and write docs for module B simultaneously" |
| `superpowers:using-git-worktrees` | Start feature work needing isolation; before executing plans | "Work on this feature without polluting main workspace" |
| `superpowers:finishing-a-development-branch` | Implementation complete, all tests pass, ready to integrate | "I'm done with the feature branch" |
| `superpowers:writing-skills` | Create, edit, or verify skills before deploying | "Write a skill for our deployment workflow" |

**Deprecated aliases** (redirect to above):
- `superpowers:brainstorm` → `superpowers:brainstorming`
- `superpowers:write-plan` → `superpowers:writing-plans`
- `superpowers:execute-plan` → `superpowers:executing-plans`

---

## Project-Specific Skills

| Skill | When to use | Example |
|---|---|---|
| `vla-steering-scaffold` | Starting a new VLA steering/adaptation research project from scratch | "Scaffold a new VLA project with Hydra config and env adapters" |

---

## Built-in / Core Skills

These appear in every session's system-reminder automatically.

| Skill | When to use | Example |
|---|---|---|
| `update-config` | Configure `settings.json` for automated behaviors, hooks, permissions, env vars | "Whenever I run tests, show a summary" |
| `keybindings-help` | Customize keyboard shortcuts in `~/.claude/keybindings.json` | "Rebind Ctrl+S to submit" |
| `simplify` | Review changed code for reuse, quality, efficiency; fix issues found | "Simplify the code I just wrote" |
| `fewer-permission-prompts` | Scan transcripts and add read-only tool allowlists to reduce prompts | "Stop asking me about every `ls` command" |
| `loop` | Run a prompt or slash command on a recurring interval | `/loop 5m /security-review` |
| `schedule` | Create/manage remote agents on cron schedules | "Run a dependency audit every Monday morning" |
| `claude-api` | Build, debug, optimize Claude API / Anthropic SDK apps; migrate models | "Add prompt caching to my Anthropic SDK script" |
| `init` | Initialize a new `CLAUDE.md` with codebase documentation | "Set up CLAUDE.md for this repo" |
| `review` | Review a pull request | "Review PR #42" |
| `security-review` | Security review of pending branch changes | "Check my changes for vulnerabilities" |

---

## Plugin-Dev Skills (`claude-plugins-official`)

For building Claude Code plugins, skills, agents, hooks, and MCP servers.

| Skill | When to use | Example |
|---|---|---|
| `plugin-structure` | Scaffold a new plugin, understand directory layout and `plugin.json` | "Create a new Claude Code plugin" |
| `skill-development` | Add a skill to a plugin; structure SKILL.md with progressive disclosure | "Add a skill to my plugin" |
| `command-development` | Create slash commands with YAML frontmatter and dynamic arguments | "Add a `/deploy` slash command" |
| `agent-development` | Create subagents with system prompts, triggering conditions, tools | "Add a code-review subagent to my plugin" |
| `hook-development` | Create PreToolUse/PostToolUse/Stop hooks for event-driven automation | "Block dangerous shell commands via a hook" |
| `mcp-integration` | Integrate MCP servers into a plugin via `.mcp.json` | "Connect my plugin to an external REST API via MCP" |
| `plugin-settings` | Store per-project plugin config using `.local.md` YAML frontmatter | "Make my plugin's API key configurable per project" |
| `skill-creator` | Create, optimize, or benchmark skills; run evals | "Measure how reliably my skill triggers" |

---

## MCP Server Dev Skills

| Skill | When to use | Example |
|---|---|---|
| `build-mcp-server` | Entry point for all MCP server development — determines deployment model | "Build an MCP server that wraps the GitHub API" |
| `build-mcp-app` | Add interactive UI widgets / inline components to an MCP server | "Add a form dialog to my MCP server" |
| `build-mcpb` | Package an MCP server with bundled runtime (Node/Python) for distribution | "Ship my MCP server as a single installable file" |

---

## Utility Skills

| Skill | When to use | Example |
|---|---|---|
| `frontend-design` | Build production-grade web components/pages with high design quality | "Build a dashboard page for this app" |
| `session-report` | Generate an HTML report of session token usage, cache hits, subagents | "Show me a report of today's Claude usage" |
| `playground` | Create interactive single-file HTML explorers with live preview | "Make a playground for tuning my prompt" |
| `math-olympiad` | Solve IMO/Putnam/USAMO/AIME competition math with adversarial verification | "Prove this olympiad inequality" |
| `claude-md-improver` | Audit and improve `CLAUDE.md` files across a repo | "Audit all CLAUDE.md files in this monorepo" |
| `claude-automation-recommender` | Analyze codebase and recommend hooks, subagents, skills, MCP servers | "What automations should I add for this project?" |
| `writing-hookify-rules` | Write hookify rule syntax for automated hook behaviors | "Add a hookify rule to lint on every file save" |

---

## External Channel Skills

For messaging integrations (only available when the respective plugin is configured).

| Skill | When to use |
|---|---|
| `imessage:configure` | Check/setup iMessage channel |
| `imessage:access` | Manage iMessage allowlists and pairing |
| `discord:configure` | Setup Discord bot token and channel |
| `discord:access` | Manage Discord access policy |
| `telegram:configure` | Setup Telegram bot token and channel |
| `telegram:access` | Manage Telegram access policy |
