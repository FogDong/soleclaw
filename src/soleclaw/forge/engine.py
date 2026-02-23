from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from .validator import validate_generated_tool

log = logging.getLogger(__name__)

FORGE_PROMPT = """Create a tool in {tool_dir}/ with these files:

1. manifest.json - with name, description, version, parameters (JSON Schema)
2. tool.py - with an async function: async def execute(args: dict) -> dict
3. formatter.py (optional) - with: def format(data: dict) -> str

Requirements:
- Name: {name}
- Description: {description}

{task_section}

Rules:
- tool.py execute() must return a dict of structured data, NEVER formatted text
- Include input validation
- Data persistence: use the shared SQLite database at {data_db}
  - Use `aiosqlite` for async access
  - Table names must be prefixed with the tool name (e.g. {name}_items)
  - Create tables with IF NOT EXISTS on first use
  - NEVER store persistent data in the tool's own directory
"""


class ForgeEngine:
    def __init__(self, library_path: Path, max_retries: int = 3):
        self.library_path = library_path
        self.max_retries = max_retries

    async def generate(self, name: str, description: str, context: str = "") -> dict[str, Any]:
        self.library_path.mkdir(parents=True, exist_ok=True)
        tool_dir = self.library_path / name

        try:
            from claude_agent_sdk import ClaudeAgentOptions, query
        except ImportError:
            return {"error": "claude-agent-sdk not installed. Run: uv pip install claude-agent-sdk"}

        task_md = tool_dir / "TASK.md"
        task_section = ""
        if task_md.exists():
            task_section = f"Task specification (TASK.md):\n{task_md.read_text().strip()}"
        elif context:
            task_section = f"User context:\n{context}"

        data_dir = self.library_path.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        data_db = data_dir / "store.db"

        prompt = FORGE_PROMPT.format(
            tool_dir=tool_dir, name=name, description=description,
            task_section=task_section, data_db=data_db,
        )

        errors = []
        for attempt in range(self.max_retries):
            log.info("Forge attempt %d/%d for %s", attempt + 1, self.max_retries, name)
            options = ClaudeAgentOptions(
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                permission_mode="acceptEdits",
                cwd=str(self.library_path),
            )

            try:
                async for message in query(prompt=prompt, options=options):
                    log.debug("forge sdk message: %s", type(message).__name__)
            except Exception as e:
                backoff = min(30, 5 * (2 ** attempt))
                log.warning("Forge SDK error on attempt %d: %s (retry in %ds)", attempt + 1, e, backoff)
                await asyncio.sleep(backoff)
                continue

            errors = validate_generated_tool(tool_dir)
            if not errors:
                log.info("Forge success: %s", name)
                return {"success": True, "name": name, "path": str(tool_dir)}

            log.warning("Forge validation failed: %s errors=%s", name, errors)
            prompt = f"The generated tool has errors: {errors}\nPlease fix them in {tool_dir}/"

        return {"error": f"Failed to generate tool after {self.max_retries} attempts", "last_errors": errors}
