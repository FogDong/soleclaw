from __future__ import annotations
import json
import pytest
from pathlib import Path

from soleclaw.tools.sdk_tools import (
    init_tools, forge_tool, run_user_tool,
    memory_store, memory_search, cron_schedule, cron_list, cron_delete,
    message_send, ALL_TOOLS,
)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "tool-library").mkdir()
    init_tools(workspace=tmp_path)
    return tmp_path


def _parse(result):
    return json.loads(result["content"][0]["text"])


async def test_forge_tool_missing_fields(workspace):
    result = await forge_tool.handler({"name": "", "description": ""})
    assert "error" in _parse(result)


async def test_forge_tool_list_empty(workspace):
    result = await forge_tool.handler({"action": "list"})
    data = _parse(result)
    assert data["tools"] == []


async def test_forge_tool_remove_not_found(workspace):
    result = await forge_tool.handler({"action": "remove", "name": "nope"})
    assert "error" in _parse(result)


async def test_run_user_tool_not_found(workspace):
    result = await run_user_tool.handler({"name": "nonexistent", "arguments": "{}"})
    assert "error" in _parse(result)


async def test_run_user_tool_bad_json(workspace):
    result = await run_user_tool.handler({"name": "x", "arguments": "not json"})
    assert "error" in _parse(result)


async def test_memory_store_not_configured(workspace):
    result = await memory_store.handler({"key": "k", "content": "v"})
    assert "error" in _parse(result)


async def test_memory_search_not_configured(workspace):
    result = await memory_search.handler({"query": "test"})
    assert "error" in _parse(result)


async def test_cron_list_not_configured(workspace):
    result = await cron_list.handler({})
    assert "error" in _parse(result)


async def test_cron_list_with_store(workspace):
    from soleclaw.cron.store import CronStore
    store = CronStore(workspace / "cron" / "jobs.json")
    init_tools(workspace=workspace, cron_store=store)
    result = await cron_list.handler({})
    data = _parse(result)
    assert "jobs" in data
    init_tools(workspace=workspace)  # reset


async def test_message_send(workspace):
    from soleclaw.bus.queue import MessageBus
    bus = MessageBus()
    init_tools(workspace=workspace, bus=bus)
    result = await message_send.handler({"channel": "test", "chat_id": "1", "content": "hi"})
    data = _parse(result)
    assert data["sent"] is True
    init_tools(workspace=workspace)  # reset


async def test_message_send_not_configured(workspace):
    result = await message_send.handler({"channel": "test", "chat_id": "1", "content": "hi"})
    assert "error" in _parse(result)


def test_all_tools_count():
    assert len(ALL_TOOLS) == 11
