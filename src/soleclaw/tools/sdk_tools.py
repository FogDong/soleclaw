from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

log = logging.getLogger(__name__)

_workspace: Path = Path()
_memory: Any = None
_cron_store: Any = None
_bus: Any = None
_cron_trigger_fn: Any = None
_channel_context: dict[str, str] = {}


def init_tools(
    workspace: Path,
    memory: Any = None,
    cron_store: Any = None,
    bus: Any = None,
    cron_trigger_fn: Any = None,
) -> None:
    global _workspace, _memory, _cron_store, _bus, _cron_trigger_fn
    _workspace = workspace
    _memory = memory
    _cron_store = cron_store
    _bus = bus
    _cron_trigger_fn = cron_trigger_fn


def set_channel_context(channel: str, chat_id: str, thread_id: str = "") -> None:
    global _channel_context
    _channel_context = {"channel": channel, "chat_id": chat_id, "thread_id": thread_id}


def _result(data: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}


@tool("forge_tool", "Build, list, or remove tools in the tool library", {
    "action": str, "name": str, "description": str, "context": str,
})
async def forge_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "create")
    name = args.get("name", "")
    library = _workspace / "tool-library"

    if action == "list":
        tools = []
        if library.exists():
            for d in sorted(library.iterdir()):
                mp = d / "manifest.json"
                if d.is_dir() and mp.exists():
                    try:
                        m = json.loads(mp.read_text())
                        tools.append({"name": m.get("name", d.name), "description": m.get("description", "")})
                    except Exception:
                        tools.append({"name": d.name, "description": "(invalid)"})
        return _result({"tools": tools})

    if action == "remove":
        if not name:
            return _result({"error": "remove requires name"})
        td = library / name
        if not td.exists():
            return _result({"error": f"Tool not found: {name}"})
        shutil.rmtree(td)
        return _result({"success": True, "removed": name})

    # create
    description = args.get("description", "")
    if not name or not description:
        return _result({"error": "create requires name and description"})
    context = args.get("context", "")
    td = library / name
    td.mkdir(parents=True, exist_ok=True)
    task_md = td / "TASK.md"
    if not task_md.exists() and context:
        task_md.write_text(f"# {name}\n\n{context}\n")

    from soleclaw.forge.engine import ForgeEngine
    engine = ForgeEngine(library_path=library)
    try:
        result = await engine.generate(name=name, description=description, context=context)
    except Exception as e:
        log.exception("forge failed: %s", name)
        result = {"error": str(e)}

    usage_hint = ""
    if result.get("success"):
        usage_hint = (
            f"\n\nTool '{name}' is now available. "
            f"Use run_user_tool(name='{name}', arguments='{{...}}') to call it."
        )
    return _result({**result, "usage_hint": usage_hint})


@tool("run_user_tool", "Run a user-created tool from the tool library", {
    "name": str, "arguments": str,
})
async def run_user_tool(args: dict[str, Any]) -> dict[str, Any]:
    from soleclaw.tools.library.registry import LibraryRegistry
    library = LibraryRegistry(_workspace / "tool-library")
    library.discover()
    name = args.get("name", "")
    try:
        parsed = json.loads(args.get("arguments", "{}"))
    except json.JSONDecodeError as e:
        return _result({"error": f"Invalid JSON arguments: {e}"})
    result = await library.execute(name, parsed)
    return _result(result)


@tool("memory_store", "Store a memory for long-term recall", {
    "key": str, "content": str,
})
async def memory_store(args: dict[str, Any]) -> dict[str, Any]:
    if not _memory:
        return _result({"error": "Memory backend not configured"})
    await _memory.store(args["key"], args["content"], {})
    return _result({"stored": True, "key": args["key"]})


@tool("memory_search", "Search memories by query", {
    "query": str,
})
async def memory_search(args: dict[str, Any]) -> dict[str, Any]:
    if not _memory:
        return _result({"error": "Memory backend not configured"})
    entries = await _memory.search(args["query"])
    return _result({"results": [{"key": e.key, "content": e.content} for e in entries]})


@tool("cron_schedule", "Schedule a recurring task.", {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Short name for the job"},
        "schedule_kind": {"type": "string", "description": "cron | every | at"},
        "schedule_value": {"type": "string", "description": "Cron expression, interval, or ISO timestamp"},
        "message": {"type": "string", "description": "Message or instruction to execute"},
        "message_kind": {"type": "string", "description": "agent (default) = LLM generates response; static = send message text directly"},
        "schedule_tz": {"type": "string", "description": "Timezone (default UTC)"},
        "channel": {"type": "string", "description": "Target channel. Only set if user explicitly specifies one; auto-detected otherwise"},
        "chat_id": {"type": "string", "description": "Target chat ID. Only set if user explicitly specifies one; auto-detected otherwise"},
        "thread_id": {"type": "string", "description": "Telegram topic/thread ID. Only set if user explicitly specifies one; auto-detected otherwise"},
    },
    "required": ["name", "schedule_kind", "schedule_value", "message"],
})
async def cron_schedule(args: dict[str, Any]) -> dict[str, Any]:
    if not _cron_store:
        return _result({"error": "Cron not configured"})
    from soleclaw.cron.types import CronJob
    from soleclaw.cron.service import compute_next_run
    job = CronJob(
        id=CronJob.new_id(), name=args["name"], message=args["message"],
        schedule_kind=args["schedule_kind"], schedule_value=args["schedule_value"],
        channel=args.get("channel") or _channel_context.get("channel", ""),
        chat_id=args.get("chat_id") or _channel_context.get("chat_id", ""),
        thread_id=args.get("thread_id") or _channel_context.get("thread_id", ""),
        message_kind=args.get("message_kind", ""),
        schedule_tz=args.get("schedule_tz", "UTC"),
    )
    job.next_run_at = compute_next_run(job)
    _cron_store.add(job)
    return _result({"success": True, "job_id": job.id, "next_run_at": job.next_run_at})


@tool("cron_list", "List all scheduled tasks", {})
async def cron_list(args: dict[str, Any]) -> dict[str, Any]:
    if not _cron_store:
        return _result({"error": "Cron not configured"})
    jobs = _cron_store.load()
    return _result({"jobs": [j.summary() for j in jobs]})


@tool("cron_update", "Update an existing scheduled task. Only include fields you want to change.", {
    "type": "object",
    "properties": {
        "job_id": {"type": "string", "description": "ID of the job to update"},
        "name": {"type": "string"},
        "message": {"type": "string"},
        "message_kind": {"type": "string", "description": "agent or static"},
        "schedule_kind": {"type": "string"},
        "schedule_value": {"type": "string"},
        "schedule_tz": {"type": "string"},
        "channel": {"type": "string"},
        "chat_id": {"type": "string"},
        "thread_id": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "required": ["job_id"],
})
async def cron_update(args: dict[str, Any]) -> dict[str, Any]:
    if not _cron_store:
        return _result({"error": "Cron not configured"})
    job_id = args.pop("job_id")
    updates = {k: v for k, v in args.items() if v is not None}
    if not updates:
        return _result({"error": "No fields to update"})
    if not _cron_store.update(job_id, **updates):
        return _result({"error": f"Job not found: {job_id}"})
    from soleclaw.cron.service import compute_next_run
    job = _cron_store.get(job_id)
    if job and ("schedule_kind" in updates or "schedule_value" in updates or "schedule_tz" in updates):
        job.next_run_at = compute_next_run(job)
        _cron_store.save(_cron_store.load())
    return _result({"success": True, "job_id": job_id})


@tool("cron_trigger", "Manually trigger a scheduled task to run immediately. Does not affect its normal schedule.", {"job_id": str})
async def cron_trigger(args: dict[str, Any]) -> dict[str, Any]:
    if not _cron_store:
        return _result({"error": "Cron not configured"})
    if not _cron_trigger_fn:
        return _result({"error": "Trigger not available (gateway not running?)"})
    job = _cron_store.get(args["job_id"])
    if not job:
        return _result({"error": f"Job not found: {args['job_id']}"})
    asyncio.create_task(_cron_trigger_fn(job))
    return _result({"success": True, "job_id": job.id, "message": "Job triggered in background"})


@tool("cron_delete", "Delete a scheduled task", {"job_id": str})
async def cron_delete(args: dict[str, Any]) -> dict[str, Any]:
    if not _cron_store:
        return _result({"error": "Cron not configured"})
    _cron_store.remove(args["job_id"])
    return _result({"success": True, "deleted": args["job_id"]})


@tool("message_send", "Send a message to a channel. Omit channel/chat_id to send to the current conversation.", {
    "content": str, "channel": str, "chat_id": str, "thread_id": str,
})
async def message_send(args: dict[str, Any]) -> dict[str, Any]:
    if not _bus:
        return _result({"error": "Message bus not configured"})
    channel = args.get("channel") or _channel_context.get("channel", "")
    chat_id = args.get("chat_id") or _channel_context.get("chat_id", "")
    thread_id = args.get("thread_id") or _channel_context.get("thread_id", "")
    if not channel or not chat_id:
        return _result({"error": "No target: provide channel/chat_id or send from a channel context"})
    from soleclaw.bus.events import OutboundMessage
    await _bus.publish_outbound(OutboundMessage(channel=channel, chat_id=chat_id, thread_id=thread_id, content=args["content"]))
    return _result({"sent": True, "channel": channel, "chat_id": chat_id})


ALL_TOOLS = [
    forge_tool, run_user_tool,
    memory_store, memory_search,
    cron_schedule, cron_list, cron_update, cron_trigger, cron_delete,
    message_send,
]
