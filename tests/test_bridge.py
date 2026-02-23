from __future__ import annotations
import pytest
from pathlib import Path

from soleclaw.core.bridge import SoleclawBridge
from soleclaw.config.schema import Config


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "SOUL.md").write_text("# SOUL\nYou are soleclaw.")
    (tmp_path / "IDENTITY.md").write_text("# IDENTITY")
    (tmp_path / "USER.md").write_text("# USER")
    (tmp_path / "AGENTS.md").write_text("# AGENTS\nFollow instructions.")
    (tmp_path / "TOOLS.md").write_text("# TOOLS")
    (tmp_path / "HEARTBEAT.md").write_text("# HEARTBEAT")
    (tmp_path / "tool-library").mkdir()
    (tmp_path / "memory").mkdir()
    return tmp_path


@pytest.fixture
def config(workspace):
    return Config(agent={"workspace": str(workspace), "model": "claude-sonnet-4-6"})


def test_bridge_init(config, workspace):
    bridge = SoleclawBridge(workspace, config)
    assert bridge._context is not None
    assert bridge._mcp is not None
    assert bridge.bus is not None


def test_bridge_make_options(config, workspace):
    bridge = SoleclawBridge(workspace, config)
    opts = bridge._make_options()
    assert "soleclaw" in opts.system_prompt
    assert opts.max_turns == 20
    assert opts.cwd == str(workspace)
    assert opts.model == "claude-sonnet-4-6"
    assert opts.permission_mode == "bypassPermissions"
    assert any("forge_tool" in t for t in opts.allowed_tools)


def test_bridge_make_options_bootstrap(config, workspace):
    (workspace / "BOOTSTRAP.md").write_text("# BOOTSTRAP")
    bridge = SoleclawBridge(workspace, config)
    opts = bridge._make_options()
    assert "BOOTSTRAP" in opts.system_prompt


def test_bridge_cron_store(config, workspace):
    bridge = SoleclawBridge(workspace, config)
    assert bridge.cron_store is not None


def test_bridge_no_cron(workspace):
    config = Config(agent={"workspace": str(workspace)}, cron={"enabled": False})
    bridge = SoleclawBridge(workspace, config)
    assert bridge.cron_store is None
