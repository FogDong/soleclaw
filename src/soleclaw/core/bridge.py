from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    create_sdk_mcp_server,
)
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

from ..config.schema import Config
from .context import ContextBuilder
from ..tools.sdk_tools import ALL_TOOLS, init_tools

log = logging.getLogger(__name__)


class SessionStore:
    """Maps logical keys (e.g. 'telegram:12345') to SDK session IDs."""

    def __init__(self, path: Path):
        self._path = path
        self._data: dict[str, str] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text())
            except Exception:
                pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def put(self, key: str, session_id: str) -> None:
        self._data[key] = session_id
        self._save()

    def remove(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def clear(self) -> int:
        n = len(self._data)
        self._data.clear()
        self._save()
        return n

    def list_all(self) -> dict[str, str]:
        return dict(self._data)


class SoleclawBridge:
    def __init__(self, workspace: Path, config: Config):
        os.environ.pop("CLAUDECODE", None)
        self._workspace = workspace
        self._config = config
        self._context = ContextBuilder(workspace)

        memory = self._init_memory(config)
        cron_store = self._init_cron(config)
        bus = self._init_bus()

        init_tools(
            workspace=workspace, memory=memory, cron_store=cron_store,
            bus=bus, cron_trigger_fn=self._run_cron_job,
        )
        self._memory = memory
        self._cron_store = cron_store
        self._bus = bus
        self._mcp = create_sdk_mcp_server(name="soleclaw", tools=ALL_TOOLS)
        self._sessions = SessionStore(workspace / "sessions.json")

    @property
    def sessions(self) -> SessionStore:
        return self._sessions

    def _init_memory(self, config: Config) -> Any:
        try:
            if config.viking.enabled:
                from ..memory.viking import VikingMemoryBackend
                return VikingMemoryBackend(Path(config.viking.path).expanduser())
            from ..memory.local import LocalMemoryBackend
            return LocalMemoryBackend(config.workspace_path / "memory")
        except Exception:
            log.warning("Memory init failed, continuing without memory")
            return None

    def _init_cron(self, config: Config) -> Any:
        if not config.cron.enabled:
            return None
        try:
            from ..cron.store import CronStore
            return CronStore(config.workspace_path / "cron" / "jobs.json")
        except Exception:
            log.warning("Cron init failed, continuing without cron")
            return None

    def _init_bus(self) -> Any:
        from ..bus.queue import MessageBus
        return MessageBus()

    @property
    def bus(self) -> Any:
        return self._bus

    @property
    def cron_store(self) -> Any:
        return self._cron_store

    async def _run_cron_job(self, job: Any) -> None:
        """Execute a cron job directly (manual trigger). Does not touch schedule."""
        try:
            if job.message_kind == "static":
                result = job.message
            else:
                from ..cron.service import CRON_PREAMBLE
                result = await self.oneshot(CRON_PREAMBLE + job.message)
            if result and job.channel and job.chat_id:
                from ..bus.events import OutboundMessage
                await self._bus.publish_outbound(
                    OutboundMessage(channel=job.channel, chat_id=job.chat_id, thread_id=job.thread_id, content=result)
                )
        except Exception:
            log.exception("Manual cron trigger failed: job %s", job.id)

    def _make_options(self, *, resume: str | None = None) -> ClaudeAgentOptions:
        tool_names = [f"mcp__soleclaw__{t.name}" for t in ALL_TOOLS]
        kwargs: dict[str, Any] = dict(
            system_prompt=self._context.build_system_prompt(),
            mcp_servers={"soleclaw": self._mcp},
            allowed_tools=tool_names,
            max_turns=self._config.agent.max_turns,
            permission_mode="bypassPermissions",
            cwd=str(self._workspace),
            model=self._config.agent.model,
        )
        if self._config.agent.max_budget_usd:
            kwargs["max_budget_usd"] = self._config.agent.max_budget_usd
        if resume:
            kwargs["resume"] = resume
        return ClaudeAgentOptions(**kwargs)

    async def connect(self, resume: str | None = None) -> ClaudeSDKClient:
        opts = self._make_options(resume=resume)
        client = ClaudeSDKClient(options=opts)
        await client.connect()
        return client

    async def chat(self, client: ClaudeSDKClient, message: str) -> tuple[str, str | None]:
        """Send message, return (text, session_id)."""
        await client.query(message)
        return await self._collect(client.receive_response())

    async def oneshot(self, message: str, *, session_key: str | None = None) -> str:
        """Single exchange. If session_key is given, resume/save session."""
        resume = self._sessions.get(session_key) if session_key else None
        client = await self.connect(resume=resume)
        try:
            await client.query(message)
            text, session_id = await self._collect(client.receive_response())
            if session_key and session_id:
                self._sessions.put(session_key, session_id)
            self._append_daily_log(message, text, session_key)
            return text
        finally:
            await client.disconnect()

    def _append_daily_log(self, user_msg: str, assistant_msg: str, session_key: str | None = None) -> None:
        try:
            memory_dir = self._workspace / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            daily = memory_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
            source = f" ({session_key})" if session_key else ""
            entry = f"\n### {datetime.now().strftime('%H:%M')}{source}\n\n**User:** {user_msg}\n\n**Assistant:** {assistant_msg}\n"
            if not daily.exists():
                daily.write_text(f"# {datetime.now().strftime('%Y-%m-%d')}\n{entry}")
            else:
                with open(daily, "a") as f:
                    f.write(entry)
        except Exception:
            log.debug("Failed to write daily log", exc_info=True)

    @staticmethod
    async def _collect(stream) -> tuple[str, str | None]:
        parts: list[str] = []
        session_id: str | None = None
        async for msg in stream:
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                session_id = msg.session_id
        return "".join(parts), session_id
