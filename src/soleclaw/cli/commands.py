from __future__ import annotations
import asyncio
from pathlib import Path

import typer
from rich.console import Console

from ..config.schema import Config

app = typer.Typer(name="soleclaw", help="soleclaw - Self-evolving AI assistant", no_args_is_help=True)
gw_app = typer.Typer(name="gateway", help="Manage the channel gateway", no_args_is_help=True)
sess_app = typer.Typer(name="session", help="Manage conversation sessions", no_args_is_help=True)
prompt_app = typer.Typer(name="prompt", help="View and edit system prompt files", no_args_is_help=True)
cfg_app = typer.Typer(name="configure", help="Configuration wizard", invoke_without_command=True)
app.add_typer(gw_app)
app.add_typer(sess_app)
app.add_typer(prompt_app)
app.add_typer(cfg_app)
console = Console()


# -- configure command -------------------------------------------------------

@cfg_app.callback()
def configure(
    ctx: typer.Context,
    config_path: Path | None = typer.Option(None, "--config", "-c"),
    workspace: Path | None = typer.Option(None, "--workspace", "-w"),
):
    """Interactive configuration wizard. Run without subcommand for full setup, or use 'slack'/'telegram' to configure a single channel."""
    if ctx.invoked_subcommand is not None:
        return
    from .configure import ConfigureWizard, select

    ws = workspace if isinstance(workspace, Path) else Path("~/.soleclaw").expanduser()
    wiz = ConfigureWizard(workspace=ws)
    cfg_file = config_path or Path("~/.soleclaw/config.json").expanduser()
    is_fresh = not cfg_file.exists()
    existing = Config.load(config_path)

    # -- 1. Model selection ----------------------------------------------------
    CLAUDE_MODELS = [
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
        {"id": "claude-haiku-3-5", "name": "Claude Haiku 3.5"},
    ]

    current_model = existing.agent.model
    if current_model and not is_fresh:
        keep = f"Keep current ({current_model})"
        mi = select("Model:", [keep, "Change model"])
        skip_model = mi == 0
    else:
        skip_model = False

    if skip_model:
        model_id = current_model
    else:
        labels = [f"{m['name']}  ({m['id']})" for m in CLAUDE_MODELS] + ["Custom input"]
        mi = select("Select model:", labels)
        if mi < len(CLAUDE_MODELS):
            model_id = CLAUDE_MODELS[mi]["id"]
        else:
            model_id = typer.prompt("Model ID (e.g. claude-sonnet-4-6)")

    # -- 2. Telegram channel (skippable) ---------------------------------------
    tg_cfg = existing.channels.telegram
    tg_token, tg_users = tg_cfg.token, tg_cfg.allowed_users
    tg_enabled = tg_cfg.enabled

    if tg_cfg.enabled and tg_cfg.token:
        masked = tg_cfg.token[:8] + "..." if len(tg_cfg.token) > 8 else "***"
        ti = select("Telegram:", [f"Keep current ({masked})", "Reconfigure", "Disable"])
        if ti == 0:
            pass
        elif ti == 2:
            tg_enabled, tg_token, tg_users = False, "", []
        else:
            tg_enabled, tg_token, tg_users = _prompt_telegram()
    else:
        ei = select("Enable Telegram channel?", ["Yes", "No"])
        if ei == 0:
            tg_enabled, tg_token, tg_users = _prompt_telegram()

    # -- 3. Slack channel (skippable) --------------------------------------------
    sl_cfg = existing.channels.slack
    sl_enabled = sl_cfg.enabled
    sl_bot_token, sl_app_token = sl_cfg.bot_token, sl_cfg.app_token
    sl_channels, sl_users = sl_cfg.channels, sl_cfg.allowed_users

    if sl_cfg.enabled and sl_cfg.bot_token:
        masked = sl_cfg.bot_token[:8] + "..." if len(sl_cfg.bot_token) > 8 else "***"
        si = select("Slack:", [f"Keep current ({masked})", "Reconfigure", "Disable"])
        if si == 0:
            pass
        elif si == 2:
            sl_enabled, sl_bot_token, sl_app_token, sl_channels, sl_users = False, "", "", [], []
        else:
            sl_enabled, sl_bot_token, sl_app_token, sl_channels, sl_users = _prompt_slack()
    else:
        ei = select("Enable Slack channel?", ["Yes", "No"])
        if ei == 0:
            sl_enabled, sl_bot_token, sl_app_token, sl_channels, sl_users = _prompt_slack()

    # -- Save ------------------------------------------------------------------
    config = wiz.build_config(
        model=model_id,
        telegram_enabled=tg_enabled, telegram_token=tg_token,
        telegram_allowed_users=tg_users,
        slack_enabled=sl_enabled, slack_bot_token=sl_bot_token,
        slack_app_token=sl_app_token, slack_channels=sl_channels,
        slack_allowed_users=sl_users,
    )
    wiz.save_config(config)
    console.print(f"\n[green]Config saved to {ws / 'config.json'}[/green]")

    # -- Bootstrap (USER.md / SOUL.md) -----------------------------------------
    from ..core.bootstrap import needs_bootstrap, run_bootstrap
    if needs_bootstrap(ws):
        run_bootstrap(ws)

    # -- Offer to start gateway ------------------------------------------------
    if tg_enabled or sl_enabled:
        from ..core.pidfile import is_gateway_running
        if is_gateway_running(ws):
            console.print("[dim]Gateway is already running.[/dim]")
        else:
            gi = select("Start gateway now?", ["Yes", "No"])
            if gi == 0:
                gateway_start(config_path=config_path)


def _prompt_telegram() -> tuple[bool, str, list[str]]:
    token = typer.prompt("Telegram bot token (from @BotFather)", hide_input=True)
    users_raw = typer.prompt("Allowed usernames (comma-separated, empty=all)", default="")
    users = [u.strip().lstrip("@") for u in users_raw.split(",") if u.strip()]
    return True, token, users


def _prompt_slack() -> tuple[bool, str, str, list[str], list[str]]:
    bot_token = typer.prompt("Slack Bot Token (xoxb-...)", hide_input=True)
    app_token = typer.prompt("Slack App-Level Token (xapp-...)", hide_input=True)
    channels_raw = typer.prompt("Channel IDs to watch (comma-separated, empty=all)", default="")
    channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
    users_raw = typer.prompt("Allowed user IDs (comma-separated, empty=all)", default="")
    users = [u.strip() for u in users_raw.split(",") if u.strip()]
    return True, bot_token, app_token, channels, users


def _update_config(config_path: Path | None, updates: dict) -> None:
    """Load existing config, merge updates, save."""
    import json
    cfg_file = config_path or Path("~/.soleclaw/config.json").expanduser()
    data = {}
    if cfg_file.exists():
        data = json.loads(cfg_file.read_text())
    for key, val in updates.items():
        if "." in key:
            parts = key.split(".")
            d = data
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = val
        else:
            data[key] = val
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    console.print(f"[green]Config saved to {cfg_file}[/green]")


def _clear_sessions(config_path: Path | None, prefix: str) -> int:
    cfg = Config.load(config_path)
    sessions_path = cfg.workspace_path / "sessions.json"
    from ..core.bridge import SessionStore
    store = SessionStore(sessions_path)
    return store.remove_prefix(f"{prefix}:")


@cfg_app.command("telegram")
def configure_telegram(
    config_path: Path | None = typer.Option(None, "--config", "-c"),
    reset: bool = typer.Option(False, "--reset", help="Clear Telegram config and sessions"),
):
    """Configure Telegram channel only."""
    if reset:
        _update_config(config_path, {"channels.telegram": {"enabled": False, "token": "", "allowed_users": []}})
        n = _clear_sessions(config_path, "telegram")
        console.print(f"[yellow]Telegram config reset, {n} session(s) cleared[/yellow]")
        return
    from .configure import select
    existing = Config.load(config_path)
    tg_cfg = existing.channels.telegram

    if tg_cfg.enabled and tg_cfg.token:
        masked = tg_cfg.token[:8] + "..." if len(tg_cfg.token) > 8 else "***"
        ti = select("Telegram:", [f"Keep current ({masked})", "Reconfigure", "Disable"])
        if ti == 0:
            return
        elif ti == 2:
            _update_config(config_path, {"channels.telegram": {"enabled": False, "token": "", "allowed_users": []}})
            return
    enabled, token, users = _prompt_telegram()
    _update_config(config_path, {"channels.telegram": {"enabled": enabled, "token": token, "allowed_users": users}})


_SLACK_SETUP_GUIDE = """\
[bold]Slack Setup Guide[/bold]

1. Create a Slack app at [link=https://api.slack.com/apps]api.slack.com/apps[/link]

2. [bold]Socket Mode[/bold] (Settings > Socket Mode)
   - Toggle ON
   - Generate an App-Level Token with scope: [cyan]connections:write[/cyan]
   - Copy the token (xapp-...)

3. [bold]OAuth & Permissions[/bold] (Features > OAuth & Permissions)
   Add these Bot Token Scopes:
   - [cyan]chat:write[/cyan]         — send messages & thread replies
   - [cyan]reactions:write[/cyan]    — add emoji reactions
   - [cyan]channels:history[/cyan]   — read messages in public channels
   Then click "Install to Workspace" and copy the Bot Token (xoxb-...)

4. [bold]Event Subscriptions[/bold] (Features > Event Subscriptions)
   - Toggle ON
   - Under "Subscribe to bot events", add: [cyan]message.channels[/cyan]

5. [bold]Invite the bot[/bold] to the channels you want it to watch
"""


@cfg_app.command("slack")
def configure_slack(
    config_path: Path | None = typer.Option(None, "--config", "-c"),
    reset: bool = typer.Option(False, "--reset", help="Clear Slack config and sessions"),
):
    """Configure Slack channel only."""
    if reset:
        _update_config(config_path, {"channels.slack": {"enabled": False, "bot_token": "", "app_token": "", "channels": [], "allowed_users": []}})
        n = _clear_sessions(config_path, "slack")
        console.print(f"[yellow]Slack config reset, {n} session(s) cleared[/yellow]")
        return
    from .configure import select
    existing = Config.load(config_path)
    sl_cfg = existing.channels.slack

    if sl_cfg.enabled and sl_cfg.bot_token:
        masked = sl_cfg.bot_token[:8] + "..." if len(sl_cfg.bot_token) > 8 else "***"
        si = select("Slack:", [f"Keep current ({masked})", "Reconfigure", "Disable"])
        if si == 0:
            return
        elif si == 2:
            _update_config(config_path, {"channels.slack": {"enabled": False, "bot_token": "", "app_token": "", "channels": [], "allowed_users": []}})
            return
    console.print()
    console.print(_SLACK_SETUP_GUIDE)
    enabled, bot_token, app_token, channels, users = _prompt_slack()
    _update_config(config_path, {"channels.slack": {"enabled": enabled, "bot_token": bot_token, "app_token": app_token, "channels": channels, "allowed_users": users}})


# -- main commands -----------------------------------------------------------

@app.command()
def agent(
    message: str | None = typer.Argument(None, help="Single message (non-interactive)"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
):
    """Chat with the agent."""
    cfg_path = config_path or Path("~/.soleclaw/config.json").expanduser()
    if not cfg_path.exists():
        console.print("[yellow]No config found. Running configure wizard...[/yellow]")
        configure(config_path=config_path)
    cfg = Config.load(config_path)
    from ..core.bootstrap import needs_bootstrap, run_bootstrap
    if needs_bootstrap(cfg.workspace_path):
        run_bootstrap(cfg.workspace_path)
    asyncio.run(_agent_async(cfg, message))


async def _agent_async(cfg: Config, message: str | None):
    from ..core.bridge import SoleclawBridge

    bridge = SoleclawBridge(cfg.workspace_path, cfg)

    if message:
        result = await bridge.oneshot(message)
        console.print(result)
        return

    from prompt_toolkit import PromptSession
    resume = bridge.sessions.get("cli")
    client = await bridge.connect(resume=resume)
    try:
        session = PromptSession()
        console.print("[bold]soleclaw[/bold] - type /quit to exit")
        while True:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: session.prompt("you> ")
                )
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.strip() in ("/quit", "/exit"):
                break
            if not user_input.strip():
                continue
            text, sid = await bridge.chat(client, user_input.strip())
            if sid:
                bridge.sessions.put("cli", sid)
            console.print(text)
    finally:
        await client.disconnect()


@sess_app.command("clear")
def session_clear(
    session_key: str = typer.Argument(None, help="Session to clear (e.g. telegram:5384135493). Omit for all."),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
):
    """Clear conversation history."""
    from ..core.bridge import SessionStore
    cfg = Config.load(config_path)
    store = SessionStore(cfg.workspace_path / "sessions.json")

    if session_key:
        if store.remove(session_key):
            console.print(f"[green]Cleared session: {session_key}[/green]")
        else:
            console.print(f"[yellow]Session not found: {session_key}[/yellow]")
    else:
        n = store.clear()
        console.print(f"[green]Cleared {n} session(s).[/green]")


@sess_app.command("list")
def session_list(config_path: Path | None = typer.Option(None, "--config", "-c")):
    """List all sessions."""
    from ..core.bridge import SessionStore
    cfg = Config.load(config_path)
    store = SessionStore(cfg.workspace_path / "sessions.json")
    sessions = store.list_all()
    if not sessions:
        console.print("No sessions.")
        return
    for key, sid in sorted(sessions.items()):
        console.print(f"  {key}  → {sid[:16]}...")


@app.command()
def status(config_path: Path | None = typer.Option(None, "--config", "-c")):
    """Show runtime and configuration status."""
    from ..core.pidfile import is_gateway_running, read_pid

    cfg = Config.load(config_path)
    ws = cfg.workspace_path

    console.print(f"[bold]Workspace:[/bold] {ws}")
    console.print(f"[bold]Model:[/bold]     {cfg.agent.model}")

    # Gateway
    if is_gateway_running(ws):
        console.print(f"[bold]Gateway:[/bold]  [green]running[/green] (PID {read_pid(ws)})")
    else:
        console.print("[bold]Gateway:[/bold]  [dim]stopped[/dim]")

    # Channels
    tg = cfg.channels.telegram
    if tg.enabled:
        masked = tg.token[:8] + "..." if len(tg.token) > 8 else "***"
        users = ", ".join(tg.allowed_users) if tg.allowed_users else "all"
        console.print(f"[bold]Telegram:[/bold] enabled (token={masked}, users={users})")
    else:
        console.print("[bold]Telegram:[/bold] [dim]disabled[/dim]")

    # Viking
    if cfg.viking.enabled:
        console.print(f"[bold]Viking:[/bold]   [green]enabled[/green] ({cfg.viking.path})")
    else:
        console.print("[bold]Viking:[/bold]   [dim]disabled[/dim]")

    # Identity
    has_soul = (ws / "SOUL.md").exists()
    has_user = (ws / "USER.md").exists()
    if has_soul and has_user:
        console.print("[bold]Identity:[/bold] [green]configured[/green] (SOUL.md + USER.md)")
    else:
        console.print("[bold]Identity:[/bold] [yellow]not set up[/yellow] (run: soleclaw agent)")


# -- prompt commands ---------------------------------------------------------

_FILE_ALIASES: dict[str, str] = {
    "soul": "SOUL.md", "identity": "IDENTITY.md", "user": "USER.md",
    "agents": "AGENTS.md", "tools": "TOOLS.md", "memory": "MEMORY.md",
    "bootstrap": "BOOTSTRAP.md",
}


def _resolve_file(name: str) -> str:
    return _FILE_ALIASES.get(name.lower(), name)


@prompt_app.command("show")
def prompt_show(config_path: Path | None = typer.Option(None, "--config", "-c")):
    """Print the assembled system prompt."""
    from ..core.context import ContextBuilder
    cfg = Config.load(config_path)
    ctx = ContextBuilder(cfg.workspace_path)
    console.print(ctx.build_system_prompt())


@prompt_app.command("files")
def prompt_files(config_path: Path | None = typer.Option(None, "--config", "-c")):
    """List all files that compose the system prompt."""
    from ..core.context import ContextBuilder
    cfg = Config.load(config_path)
    ws = cfg.workspace_path
    ctx = ContextBuilder(ws)

    console.print("[bold]Workspace files:[/bold]")
    for fname in ctx.BOOTSTRAP_FILES:
        p = ws / fname
        status = "[green]ok[/green]" if p.exists() else "[dim]missing[/dim]"
        console.print(f"  {fname:20s} {status}")

    console.print("\n[bold]Skills (always-on):[/bold]")
    for name in ctx._skills.get_always_skills():
        meta = ctx._skills.get_metadata(name)
        source = ""
        for s, d in ctx._skills._skill_dirs():
            if d.name == name:
                source = f"[dim]({s})[/dim]"
                break
        console.print(f"  {name:20s} {meta.get('description', '')} {source}")

    lib = ws / "tool-library"
    if lib.exists():
        import json as _json
        tools = [d.name for d in sorted(lib.iterdir())
                 if d.is_dir() and (d / "manifest.json").exists()]
        if tools:
            console.print("\n[bold]Tool library:[/bold]")
            for t in tools:
                has_skill = (lib / t / "SKILL.md").exists()
                skill_status = "[green]skill[/green]" if has_skill else "[yellow]no skill[/yellow]"
                console.print(f"  {t:20s} {skill_status}")


@prompt_app.command("edit")
def prompt_edit(
    file: str = typer.Argument(..., help="File to edit (e.g. soul, agents, user, or SOUL.md)"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
):
    """Open a system prompt file in $EDITOR."""
    import os, subprocess
    cfg = Config.load(config_path)
    fname = _resolve_file(file)
    target = cfg.workspace_path / fname
    if not target.exists():
        console.print(f"[yellow]{fname} does not exist at {target}[/yellow]")
        raise typer.Exit(1)
    editor = os.environ.get("EDITOR", "vi")
    subprocess.run([editor, str(target)])


@prompt_app.command("diff")
def prompt_diff(
    file: str = typer.Argument(None, help="File to diff (omit for all)"),
    config_path: Path | None = typer.Option(None, "--config", "-c"),
):
    """Show diff between current files and bootstrap templates."""
    import difflib
    from ..core.bootstrap import (
        DEFAULT_SOUL, USER_TEMPLATE, IDENTITY_TEMPLATE,
        AGENTS_TEMPLATE, TOOLS_TEMPLATE, MEMORY_TEMPLATE,
    )

    templates = {
        "SOUL.md": DEFAULT_SOUL, "USER.md": USER_TEMPLATE,
        "IDENTITY.md": IDENTITY_TEMPLATE, "AGENTS.md": AGENTS_TEMPLATE,
        "TOOLS.md": TOOLS_TEMPLATE, "MEMORY.md": MEMORY_TEMPLATE,
    }

    cfg = Config.load(config_path)
    ws = cfg.workspace_path
    targets = {_resolve_file(file): templates[_resolve_file(file)]} if file else templates

    any_diff = False
    for fname, template in targets.items():
        if fname not in templates:
            console.print(f"[yellow]No template for {fname}[/yellow]")
            continue
        current_path = ws / fname
        if not current_path.exists():
            console.print(f"[dim]{fname}: not found[/dim]")
            continue
        current = current_path.read_text()
        if current == template:
            console.print(f"[dim]{fname}: unchanged[/dim]")
            continue
        any_diff = True
        diff = difflib.unified_diff(
            template.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile=f"{fname} (template)",
            tofile=f"{fname} (current)",
        )
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                console.print(f"[green]{line.rstrip()}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                console.print(f"[red]{line.rstrip()}[/red]")
            else:
                console.print(line.rstrip())

    if not any_diff:
        console.print("[dim]No differences found.[/dim]")


# -- gateway commands --------------------------------------------------------

@gw_app.command("start")
def gateway_start(
    config_path: Path | None = typer.Option(None, "--config", "-c"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
):
    """Start the gateway (background by default)."""
    cfg = Config.load(config_path)
    _stop_existing_gateway(cfg)

    if foreground:
        _setup_gateway_logging()
        asyncio.run(_gateway_async(cfg))
    else:
        _daemonize(cfg)


@gw_app.command("stop")
def gateway_stop(config_path: Path | None = typer.Option(None, "--config", "-c")):
    """Stop the running gateway."""
    from ..core.pidfile import is_gateway_running

    cfg = Config.load(config_path)
    if not is_gateway_running(cfg.workspace_path):
        console.print("[yellow]No gateway running.[/yellow]")
        return
    _stop_existing_gateway(cfg)
    console.print("[green]Gateway stopped.[/green]")


@gw_app.command("restart")
def gateway_restart(config_path: Path | None = typer.Option(None, "--config", "-c")):
    """Restart the gateway."""
    cfg = Config.load(config_path)
    _stop_existing_gateway(cfg)
    _daemonize(cfg)


def _stop_existing_gateway(cfg: Config) -> None:
    from ..core.pidfile import is_gateway_running, read_pid, remove_pid
    import os, signal, time

    if is_gateway_running(cfg.workspace_path):
        old_pid = read_pid(cfg.workspace_path)
        console.print(f"[yellow]Stopping existing gateway (PID {old_pid})...[/yellow]")
        try:
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(1)
        except OSError:
            pass
        remove_pid(cfg.workspace_path)


def _setup_gateway_logging():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _daemonize(cfg: Config):
    import os, sys

    log_file = cfg.workspace_path / "gateway.log"
    pid = os.fork()
    if pid > 0:
        console.print(f"[green]Gateway started in background (PID {pid})[/green]")
        console.print(f"[dim]Log: {log_file}[/dim]")
        return

    os.setsid()
    sys.stdin.close()
    out = open(log_file, "a")
    os.dup2(out.fileno(), sys.stdout.fileno())
    os.dup2(out.fileno(), sys.stderr.fileno())

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(out)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(_gateway_async(cfg))


async def _gateway_async(cfg: Config):
    import logging as _logging
    from ..core.bridge import SoleclawBridge
    from ..channels.manager import ChannelManager

    gw_log = _logging.getLogger("soleclaw.gateway")
    bridge = SoleclawBridge(cfg.workspace_path, cfg)

    cron_service = None
    if cfg.cron.enabled and bridge.cron_store:
        from ..cron.service import CronService
        cron_service = CronService(store=bridge.cron_store, bridge=bridge, bus=bridge.bus)

    manager = ChannelManager(bridge.bus)
    if cfg.channels.telegram.enabled:
        from ..channels.telegram import TelegramChannel
        manager.add(TelegramChannel(
            bus=bridge.bus, token=cfg.channels.telegram.token,
            allowed_users=cfg.channels.telegram.allowed_users,
        ))

    if cfg.channels.slack.enabled:
        from ..channels.slack import SlackChannel
        manager.add(SlackChannel(
            bus=bridge.bus, bot_token=cfg.channels.slack.bot_token,
            app_token=cfg.channels.slack.app_token,
            watch_channels=cfg.channels.slack.channels,
            allowed_users=cfg.channels.slack.allowed_users,
        ))

    if not manager._channels:
        console.print("[red]No channels enabled. Run: soleclaw configure[/red]")
        return

    async def _process_inbound():
        while True:
            msg = await bridge.bus.consume_inbound()
            gw_log.info("inbound [%s:%s] %s", msg.channel, msg.chat_id, msg.content)
            try:
                session_key = f"{msg.channel}:{msg.chat_id}"
                typing_active = True

                async def _keep_typing():
                    while typing_active:
                        await manager.send_typing(msg.channel, msg.chat_id, msg.thread_id)
                        await asyncio.sleep(4)

                typing_task = asyncio.create_task(_keep_typing())
                try:
                    from ..tools.sdk_tools import set_channel_context
                    set_channel_context(msg.channel, msg.chat_id, msg.thread_id, msg.metadata.get("message_ts", ""))
                    result = await bridge.oneshot(msg.content, session_key=session_key)
                finally:
                    typing_active = False
                    typing_task.cancel()
                gw_log.info("outbound [%s:%s] %s", msg.channel, msg.chat_id, result or "")
                if result:
                    from ..bus.events import OutboundMessage
                    await bridge.bus.publish_outbound(
                        OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, thread_id=msg.thread_id, content=result)
                    )
            except Exception:
                gw_log.exception("Error processing inbound message")

    from ..core.pidfile import write_pid, remove_pid
    write_pid(cfg.workspace_path)
    gw_log.info("Gateway started (PID %d) with %d channel(s)", __import__('os').getpid(), len(manager._channels))
    try:
        tasks = [_process_inbound(), manager.run()]
        if cron_service:
            tasks.append(cron_service.run())
            gw_log.info("CronService enabled")
        await asyncio.gather(*tasks)
    finally:
        remove_pid(cfg.workspace_path)
        gw_log.info("Gateway stopped")
