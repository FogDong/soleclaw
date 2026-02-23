"""E2E tests for bootstrap flow — runs against real Claude API.

Usage:
    uv run pytest tests/test_e2e_bootstrap.py -v -s
"""
from __future__ import annotations
import logging
import pytest
from pathlib import Path

from soleclaw.core.bridge import SoleclawBridge
from soleclaw.core.bootstrap import run_bootstrap
from soleclaw.config.schema import Config

log = logging.getLogger(__name__)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    run_bootstrap(tmp_path)
    (tmp_path / "tool-library").mkdir(exist_ok=True)
    (tmp_path / "memory").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def bridge(workspace):
    cfg = Config(agent={"workspace": str(workspace), "model": "claude-sonnet-4-6"})
    return SoleclawBridge(workspace, cfg)


async def test_bootstrap_writes_user_name(bridge, workspace):
    result = await bridge.oneshot(
        "hi, my name is Fog. I'm in UTC+8 timezone.",
    )
    user_md = (workspace / "USER.md").read_text()
    assert "Fog" in user_md, f"USER.md should contain 'Fog', got:\n{user_md}"


async def test_bootstrap_response_is_conversational(bridge, workspace):
    result = await bridge.oneshot(
        "hi, my name is Fog",
    )
    assert result, "Expected non-empty response"
    assert len(result) < 5000, f"Response too long ({len(result)} chars)"
    for marker in ["AGENTS.md", "BOOTSTRAP_HEADER", "tool_choice", "system prompt"]:
        assert marker not in result, f"Response leaked internal detail: {marker}"
