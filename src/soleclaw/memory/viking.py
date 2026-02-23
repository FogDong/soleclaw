from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .base import MemoryBackend, MemoryEntry

log = logging.getLogger(__name__)


class VikingMemoryBackend(MemoryBackend):
    """OpenViking-powered memory with auto session extraction, L0/L1 context, and semantic search."""

    def __init__(self, data_path: str | Path):
        import openviking  # noqa: F401 — fail fast if not installed
        self._path = str(data_path)
        self._client: Any = None
        self._sessions: dict[str, Any] = {}

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openviking import SyncOpenViking
            self._client = SyncOpenViking(path=self._path)
            self._client.initialize()
            try:
                self._client.mkdir("viking://user/memories")
            except Exception:
                pass
            log.debug("openviking initialized at %s", self._path)
        return self._client

    def _get_session(self, session_key: str) -> Any:
        if session_key not in self._sessions:
            client = self._ensure_client()
            sid = session_key or "default"
            session = client.session(session_id=sid)
            try:
                session.load()
            except Exception:
                log.debug("new viking session: %s", sid)
            self._sessions[session_key] = session
        return self._sessions[session_key]

    async def on_message(self, role: str, content: str, session_key: str = "") -> None:
        try:
            from openviking.message import TextPart
            session = self._get_session(session_key)
            session.add_message(role, parts=[TextPart(text=content)])
        except Exception:
            log.debug("viking on_message failed", exc_info=True)

    async def commit(self, session_key: str = "") -> None:
        session = self._sessions.get(session_key)
        if not session:
            return
        try:
            result = await asyncio.to_thread(session.commit)
            memories = result.get("memories_extracted", 0)
            if memories > 0:
                log.info("viking commit: extracted %d memories from %s", memories, session_key)
                await asyncio.to_thread(self._client.wait_processed, 30.0)
        except Exception:
            log.warning("viking commit failed for %s", session_key, exc_info=True)

    async def get_context(self, query: str = "") -> str:
        client = self._ensure_client()
        parts: list[str] = []

        # Always: user profile + preferences (L1 overview for detail)
        for uri in ("viking://user/memories/profile.md",
                     "viking://user/memories/preferences"):
            try:
                overview = client.overview(uri)
                if overview:
                    parts.append(overview)
            except Exception:
                pass

        # Query-relevant memories (L0 abstracts for token efficiency)
        if query:
            try:
                results = client.find(query, target_uri="viking://user/memories", limit=5)
                seen = set()
                for mem in getattr(results, "memories", []):
                    uri = getattr(mem, "uri", "")
                    abstract = getattr(mem, "abstract", "")
                    if abstract and uri not in seen:
                        seen.add(uri)
                        parts.append(abstract)
            except Exception:
                log.debug("viking find failed for query", exc_info=True)

        return "\n\n".join(parts)

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        client = self._ensure_client()
        entries: list[MemoryEntry] = []
        try:
            results = client.find(query, target_uri="viking://user/memories", limit=limit)
            for mem in getattr(results, "memories", []):
                uri = getattr(mem, "uri", "")
                abstract = getattr(mem, "abstract", "")
                score = getattr(mem, "score", 0.0)
                content = abstract
                try:
                    content = client.read(uri)
                except Exception:
                    pass
                entries.append(MemoryEntry(
                    key=uri,
                    content=content,
                    metadata={"score": score, "abstract": abstract},
                ))
        except Exception:
            log.debug("viking search failed", exc_info=True)
        return entries

    async def store(self, key: str, content: str, metadata: dict[str, Any]) -> None:
        # Viking memories are primarily auto-extracted via session.commit().
        # This is a fallback for explicit storage — writes a temp file and imports it.
        import tempfile
        client = self._ensure_client()
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(f"# {key}\n\n{content}\n")
                tmp_path = f.name
            client.add_resource(path=tmp_path, target=f"viking://user/memories/{key}", wait=True)
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            log.warning("viking store failed for %s", key, exc_info=True)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
