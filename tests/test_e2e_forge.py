"""E2E tests for forge flow — runs against real Claude API.

Usage:
    uv run pytest tests/test_e2e_forge.py -v -s
"""
from __future__ import annotations
import logging
import pytest
from pathlib import Path

from soleclaw.core.bridge import SoleclawBridge
from soleclaw.config.schema import Config

log = logging.getLogger(__name__)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "SOUL.md").write_text("# SOUL\nYou are soleclaw, a helpful AI assistant.")
    (tmp_path / "IDENTITY.md").write_text("# IDENTITY\n- Name: soleclaw\n- Emoji: 🐾")
    (tmp_path / "USER.md").write_text("# USER\n- Name: Fog")
    (tmp_path / "AGENTS.md").write_text("# AGENTS\nFollow user instructions. Use tools to take action.")
    (tmp_path / "TOOLS.md").write_text("# TOOLS\nNo notes yet.")
    (tmp_path / "HEARTBEAT.md").write_text("# HEARTBEAT\n")
    (tmp_path / "MEMORY.md").write_text("# MEMORY\n")
    (tmp_path / "tool-library").mkdir()
    (tmp_path / "memory").mkdir()
    return tmp_path


@pytest.fixture
def bridge(workspace):
    cfg = Config(agent={"workspace": str(workspace), "model": "claude-sonnet-4-6"})
    return SoleclawBridge(workspace, cfg)


async def test_forge_proposes_tool(bridge):
    result = await bridge.oneshot(
        "help me track my todos",
    )
    assert result, "Expected a response"
    result_lower = result.lower()
    assert any(w in result_lower for w in ["tool", "build", "create"]), \
        f"Response should propose building a tool: {result[:300]}"


async def test_forge_response_not_empty(bridge):
    result = await bridge.oneshot(
        "I need a way to manage bookmarks. Can you build me a tool?",
    )
    assert result, "Expected non-empty response"
    assert len(result) < 5000, f"Response too long ({len(result)} chars)"
