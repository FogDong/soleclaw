from __future__ import annotations
import importlib.util
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


async def run_tool(tool_path: Path, args: dict[str, Any]) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("tool_module", tool_path)
    if not spec or not spec.loader:
        return {"error": f"Cannot load tool from {tool_path}"}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    execute_fn = getattr(mod, "execute", None)
    if not execute_fn:
        return {"error": "tool.py missing execute() function"}
    log.debug("run_tool: %s args=%s", tool_path, args)
    result = await execute_fn(args)
    log.debug("run_tool result: %s", result)
    return result
