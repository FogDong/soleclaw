from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..skills.loader import SkillsLoader

SYSTEM_HEADER = """You are soleclaw, a self-evolving personal AI assistant.
Current time: {time}
Workspace: {workspace}

Your workspace files (SOUL.md, IDENTITY.md, USER.md, AGENTS.md, etc.) are loaded below. \
Follow the instructions in AGENTS.md — that is your primary behavioral guide.

You have tools available (Write, Edit, Read, Bash, etc.) plus custom MCP tools: \
forge_tool, run_user_tool, memory_store, memory_search, \
cron_schedule, cron_list, cron_update, cron_trigger, cron_delete, message_send. \
Use them to take action. When you learn something, write it to a file immediately in the same turn.

Memory: Your conversation history is auto-saved to memory/ as daily logs (YYYY-MM-DD.md). \
When you need to recall past conversations, search memory/ directly with Read or Bash grep.

IMPORTANT — Self-Evolution: When the user asks for something ongoing or repeatable \
(todos, bookmarks, tracking, expenses, reminders), propose building a persistent tool \
instead of handling it with ad-hoc files. Follow the forge skill workflow exactly — \
do NOT skip steps or call forge_tool without completing the clarify-and-spec steps first."""

BOOTSTRAP_HEADER = """IMPORTANT: BOOTSTRAP.md is present — this is your FIRST session.

MANDATORY FIRST ACTION: When the user tells you anything about themselves (name, timezone, etc.), \
you MUST immediately use Edit or Write to update USER.md with that information \
BEFORE responding with text. Do NOT just greet them — write it down first, then respond.

Follow BOOTSTRAP.md: get to know your human, figure out who you are, \
and update IDENTITY.md and USER.md as you learn things. \
Every piece of information must be written to a file immediately in the same turn."""

class ContextBuilder:
    BOOTSTRAP_FILES = [
        "SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md", "TOOLS.md",
        "BOOTSTRAP.md",
    ]
    BOOTSTRAP_ONLY_FILES = [
        "BOOTSTRAP.md", "IDENTITY.md", "USER.md", "SOUL.md",
    ]

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._skills = SkillsLoader(
            workspace_skills=workspace / "skills",
        )

    @property
    def is_bootstrap(self) -> bool:
        return (self.workspace / "BOOTSTRAP.md").exists()

    def _tool_library_section(self) -> str | None:
        lib = self.workspace / "tool-library"
        if not lib.exists():
            return None
        entries = []
        for d in sorted(lib.iterdir()):
            if not d.is_dir():
                continue
            mp = d / "manifest.json"
            tp = d / "tool.py"
            if not mp.exists() or not tp.exists():
                continue
            try:
                m = json.loads(mp.read_text())
                entries.append(f"- {m['name']}: {m.get('description', '')}")
            except Exception:
                continue
        if not entries:
            return None
        header = (
            "# Available User Tools\n\n"
            "Use run_user_tool(name, arguments) to call these.\n"
            "For detailed usage, Read the tool's SKILL.md (e.g. tool-library/<name>/SKILL.md).\n"
        )
        return header + "\n".join(entries)

    def build_system_prompt(self) -> str:
        header = SYSTEM_HEADER.format(time=datetime.now().isoformat(), workspace=self.workspace)
        if self.is_bootstrap:
            header += "\n\n" + BOOTSTRAP_HEADER
        parts = [header]
        files = self.BOOTSTRAP_ONLY_FILES if self.is_bootstrap else self.BOOTSTRAP_FILES
        for fname in files:
            p = self.workspace / fname
            if p.exists():
                parts.append(p.read_text().strip())
        if not self.is_bootstrap:
            for name in self._skills.get_always_skills():
                content = self._skills.load_skill(name)
                if content:
                    parts.append(content)
        tl = self._tool_library_section()
        if tl:
            parts.append(tl)
        return "\n\n---\n\n".join(parts)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        extra_sections: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        system = self.build_system_prompt()
        msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
        msgs.extend(history)
        if extra_sections:
            msgs.append({"role": "system", "content": "\n\n---\n\n".join(extra_sections)})
        msgs.append({"role": "user", "content": current_message})
        return msgs
