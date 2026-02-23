---
name: memory
description: Persistent file-based memory system
always: true
---

# Memory

You have a persistent, file-based memory system. Your memory lives in two places:

- **MEMORY.md** — Curated long-term facts. Always loaded into your context.
- **memory/*.md** — Daily conversation logs (`memory/YYYY-MM-DD.md`), auto-saved after each exchange. NOT loaded into context. Search them when needed.

## Reading Memory

- MEMORY.md is already in your system prompt.
- To search daily logs: use `Bash` to run `grep -i "keyword" memory/*.md`, or `Read` a specific file.
- You can also use `memory_search` to search across all memory files.

## Writing Memory

Use `Write` to create or replace a memory file:
- Rewrite MEMORY.md when facts change significantly (preserve existing facts unless outdated).

Use `Edit` to update memory in place:
- Add a new fact to MEMORY.md without rewriting the whole file.

Daily logs are auto-saved by the system — you don't need to write them manually.

## What to Store in MEMORY.md

- User information (name, timezone, preferences, communication style)
- Important decisions and their reasoning
- Project context, architecture, tech stack
- Recurring patterns and habits
- Relationships (people, roles)

## When to Update Memory

- User tells you something about themselves → update MEMORY.md
- User states a preference → update MEMORY.md
- Important decision made → update MEMORY.md
- You learn something useful for future sessions → MEMORY.md

## Memory Recall

Before answering questions about prior work, decisions, dates, people, or preferences:
1. Check MEMORY.md (already in your context).
2. If not found, search daily logs with `Read` or `grep`.
3. If still unsure, say you checked but don't have that information.
