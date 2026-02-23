from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .base import MemoryBackend, MemoryEntry


class LocalMemoryBackend(MemoryBackend):
    """File-based memory: MEMORY.md (long-term facts) + memory/YYYY-MM-DD.md (daily logs)."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_file = workspace / "MEMORY.md"
        self.memory_dir = workspace / "memory"
        workspace.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    async def store(self, key: str, content: str, metadata: dict[str, Any]) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self.memory_dir / f"{today}.md"
        entry = f"\n## {key}\n{content}\n"
        with open(daily, "a") as f:
            if not daily.exists() or daily.stat().st_size == 0:
                f.write(f"# {today}\n")
            f.write(entry)

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        query_lower = query.lower()
        results: list[MemoryEntry] = []
        for path in self._all_memory_files():
            text = path.read_text()
            if query_lower in text.lower():
                results.append(MemoryEntry(key=path.name, content=text, metadata={"path": str(path)}))
                if len(results) >= limit:
                    break
        return results

    async def get_context(self, query: str = "") -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text()
        return ""

    def _all_memory_files(self) -> list[Path]:
        files = []
        if self.memory_file.exists():
            files.append(self.memory_file)
        if self.memory_dir.exists():
            files.extend(sorted(self.memory_dir.glob("*.md"), reverse=True))
        return files
