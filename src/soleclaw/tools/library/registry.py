from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

from .runner import run_tool
from .schema import validate_manifest

log = logging.getLogger(__name__)


DISALLOWED_TOP_LEVEL = {"oneOf", "anyOf", "allOf", "enum", "not", "if", "then", "else"}


def _sanitize_parameters(params: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in params.items() if k not in DISALLOWED_TOP_LEVEL}
    clean.setdefault("type", "object")
    return clean


class GeneratedTool:
    def __init__(self, directory: Path, manifest: dict[str, Any]):
        self.directory = directory
        self.manifest = manifest

    @property
    def name(self) -> str:
        return self.manifest["name"]

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.manifest["description"],
                "parameters": _sanitize_parameters(self.manifest["parameters"]),
            },
        }


class LibraryRegistry:
    def __init__(self, library_path: Path):
        self.library_path = library_path
        self._tools: dict[str, GeneratedTool] = {}

    def discover(self) -> None:
        self._tools.clear()
        if not self.library_path.exists():
            return
        for d in self.library_path.iterdir():
            if not d.is_dir():
                continue
            manifest_path = d / "manifest.json"
            tool_path = d / "tool.py"
            if not manifest_path.exists() or not tool_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text())
            errors = validate_manifest(manifest)
            if errors:
                log.warning("Skipping %s: %s", d.name, errors)
                continue
            self._tools[manifest["name"]] = GeneratedTool(d, manifest)
            log.info("Loaded generated tool: %s", manifest["name"])

    def has(self, name: str) -> bool:
        return name in self._tools

    def get_definitions(self) -> list[dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown generated tool: {name}"}
        tool_path = tool.directory / "tool.py"
        return await run_tool(tool_path, params)
