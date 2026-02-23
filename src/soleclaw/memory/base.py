from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryEntry:
    key: str
    content: str
    metadata: dict[str, Any]


class MemoryBackend(ABC):
    @abstractmethod
    async def get_context(self, query: str = "") -> str: ...

    @abstractmethod
    async def store(self, key: str, content: str, metadata: dict[str, Any]) -> None: ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]: ...

    async def on_message(self, role: str, content: str, session_key: str = "") -> None:
        pass

    async def commit(self, session_key: str = "") -> None:
        pass
