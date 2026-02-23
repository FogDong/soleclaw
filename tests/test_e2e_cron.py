"""E2E tests for cron flow — runs against real Claude API.

Tests the full flow: user asks for a reminder → cron job created with
correct channel auto-detection → user asks to change target → updated.

Usage:
    uv run pytest tests/test_e2e_cron.py -v -s
"""
from __future__ import annotations
import json
import logging
import pytest
from pathlib import Path

from soleclaw.core.bridge import SoleclawBridge
from soleclaw.core.bootstrap import run_bootstrap
from soleclaw.config.schema import Config
from soleclaw.tools.sdk_tools import set_channel_context

log = logging.getLogger(__name__)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    run_bootstrap(tmp_path)
    (tmp_path / "tool-library").mkdir(exist_ok=True)
    (tmp_path / "memory").mkdir(exist_ok=True)
    (tmp_path / "cron").mkdir(exist_ok=True)
    # Remove BOOTSTRAP.md so we get full system prompt (AGENTS.md, skills, etc.)
    (tmp_path / "BOOTSTRAP.md").unlink(missing_ok=True)
    # Fill in USER.md so the agent knows the user
    (tmp_path / "USER.md").write_text("# USER\n- Name: Fog\n- Timezone: America/Los_Angeles")
    return tmp_path


@pytest.fixture
def bridge(workspace):
    cfg = Config(agent={"workspace": str(workspace), "model": "claude-sonnet-4-6"}, cron={"enabled": True})
    return SoleclawBridge(workspace, cfg)


def _load_jobs(workspace: Path) -> list[dict]:
    jobs_file = workspace / "cron" / "jobs.json"
    if not jobs_file.exists():
        return []
    return json.loads(jobs_file.read_text()).get("jobs", [])


async def test_cron_schedule_and_update(bridge, workspace):
    """Step 1: Schedule a reminder, verify auto-channel. Step 2: Change target."""

    # -- Step 1: User asks for a daily reminder via Telegram --
    set_channel_context("telegram", "12345")
    session_key = "test:cron"
    result = await bridge.oneshot(
        "remind me to drink water every day at 9am",
        session_key=session_key,
    )
    assert result, "Expected a response"

    jobs = _load_jobs(workspace)
    assert len(jobs) >= 1, f"Expected at least 1 cron job, got {len(jobs)}"

    # Find the water-related job
    job = next((j for j in jobs if "water" in j["name"].lower() or "drink" in j["name"].lower()
                or "water" in j.get("message", "").lower()), None)
    assert job is not None, f"No water reminder job found in: {[j['name'] for j in jobs]}"
    assert job["channel"] == "telegram", f"Expected channel='telegram', got {job['channel']!r}"
    assert job["chat_id"] == "12345", f"Expected chat_id='12345', got {job['chat_id']!r}"
    job_id = job["id"]

    # -- Step 2: User asks to redirect to a different group chat (same session) --
    result2 = await bridge.oneshot(
        "change the water reminder to send to chat 67890 instead",
        session_key=session_key,
    )
    assert result2, "Expected a response"

    jobs2 = _load_jobs(workspace)
    updated = next((j for j in jobs2 if j["id"] == job_id), None)
    assert updated is not None, f"Job {job_id} disappeared after update"
    assert updated["chat_id"] == "67890", f"Expected chat_id='67890', got {updated['chat_id']!r}"


async def test_cron_schedule_explicit_channel(bridge, workspace):
    """User explicitly specifies telegram chat_id when scheduling."""

    set_channel_context("telegram", "99999")
    result = await bridge.oneshot(
        "set up a daily standup reminder at 10am and send it to telegram chat 55555",
    )
    assert result, "Expected a response"

    jobs = _load_jobs(workspace)
    assert len(jobs) >= 1, f"Expected at least 1 cron job, got {len(jobs)}"

    job = next((j for j in jobs if "standup" in j["name"].lower()
                or "standup" in j.get("message", "").lower()), None)
    assert job is not None, f"No standup job found in: {[j['name'] for j in jobs]}"
    assert job["channel"] == "telegram", f"Expected channel='telegram', got {job['channel']!r}"
    assert job["chat_id"] == "55555", f"Expected chat_id='55555', got {job['chat_id']!r}"
