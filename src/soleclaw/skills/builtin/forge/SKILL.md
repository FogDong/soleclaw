---
name: forge
description: Manage your tool library — create, edit, list, and remove tools.
always: true
---

# Tool Builder

You have the `forge_tool` tool for managing your tool library.

**When talking to the user, say "build a tool" or "create a tool" — never say "forge".**

**Actions:** `create`, `list`, `remove`

## Workflow for Creating a New Tool

**You MUST follow these steps in order. Do NOT skip or combine steps.**

1. **Clarify** — Ask the user what they need. Pin down core use case, inputs/outputs, constraints. Keep it conversational. If their request is already specific, one or two confirming questions is enough.

2. **Spec** — **MANDATORY before calling forge_tool.** Call `Write` to create `tool-library/<name>/TASK.md` with:
   - What this tool does (one sentence)
   - Input parameters and their types
   - Expected output format
   - Edge cases or constraints
   - Example usage scenarios
   Then show the user a brief summary and ask: "Does this match what you need?"
   **You MUST write TASK.md and get user confirmation BEFORE proceeding to step 3.**

3. **Build** — Only after the user confirms the spec. Tell them you're starting AND call `forge_tool` in the **same turn**. Use `action="create"`, `name`, `description`, and the TASK.md content as `context`.

4. **Report** — When you receive the build result (via system notification), tell the user the tool is ready and show a working example.

**Rules:**
- Never call `forge_tool(action=create)` without writing TASK.md first.
- After user confirms the spec, your response MUST contain both text AND the `forge_tool` call. Never say "I'll build it" without calling the tool.

**The build runs in the background.** After calling `forge_tool`, you can keep chatting with the user. You'll be notified when the build finishes.

## Data Storage Convention

All tools that need persistence MUST use the shared database:
- Path: `{workspace}/data/store.db` (SQLite)
- Each tool creates its own table(s), prefixed with the tool name (e.g. `todo_items`, `todo_tags`)
- Use `aiosqlite` for async access
- Never store data in the tool's own directory — all persistent data goes to the shared db

This ensures tools can cross-reference data and the user has one place to back up.

## Other Actions

- `list` — Show all tools in your library.
- `remove` — Delete a tool by `name`. Use when a tool is broken or no longer needed.

## Tool File Structure

Every tool in `tool-library/<name>/` should have:
- `manifest.json` — name, description, version, parameters (JSON Schema)
- `tool.py` — `async def execute(args: dict) -> dict`
- `SKILL.md` — tells you when and how to use this tool (loaded into your context automatically)
- `TASK.md` — original spec (reference only)

**SKILL.md format:**
```
---
name: <tool-name>
description: <one-line description>
always: true
---
# <Tool Name>
<When to use — what user intents or scenarios trigger this tool>
<Usage: run_user_tool(name="<tool-name>", arguments='{"action": "..."}')>
<Constraints or tips>
```

If a tool is missing SKILL.md, create one based on its manifest.json and tool.py.

## Editing Existing Tools

When a tool needs a fix or enhancement, edit it directly — don't rebuild from scratch.

- **Fix behavior or add features:** `Edit` on `tool-library/<name>/tool.py`
- **Update schema** (parameters, description): `Edit` on `tool-library/<name>/manifest.json`
- **Update usage guidance:** `Edit` on `tool-library/<name>/SKILL.md`
- **Read current code first:** `Read` the tool.py to understand what's there before changing it

**When to edit vs rebuild:**
- User says "add a priority field to todos" → edit tool.py + manifest.json + SKILL.md
- User says "the bookmark tool is broken" → read tool.py, find the bug, edit
- User wants a completely different tool → rebuild with `forge_tool(action="create")`
