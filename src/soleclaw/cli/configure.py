from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

try:
    import termios as _termios
    _saved_tty = _termios.tcgetattr(sys.stdin.fileno())
except Exception:
    _termios = None  # type: ignore[assignment]
    _saved_tty = None


def _tty_reset():
    if _termios and _saved_tty is not None:
        _termios.tcsetattr(sys.stdin.fileno(), _termios.TCSANOW, _saved_tty)
        _termios.tcflush(sys.stdin.fileno(), _termios.TCIFLUSH)
    sys.stdout.write("\033[?2004l\033[?25h")
    sys.stdout.flush()


def _tty_run(app: Application):
    run = app.run
    if not _termios or _saved_tty is None:
        return run()
    _tty_reset()
    try:
        return run()
    finally:
        _tty_reset()


def select(title: str, options: list[str], default: int = 0) -> int:
    idx = [default]
    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        idx[0] = (idx[0] - 1) % len(options)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        idx[0] = (idx[0] + 1) % len(options)

    @kb.add("enter")
    def _enter(event):
        event.app.exit(result=idx[0])

    @kb.add("c-c")
    def _quit(event):
        raise KeyboardInterrupt

    def _get_text():
        lines = [("bold", f" {title}\n\n")]
        for i, opt in enumerate(options):
            if i == idx[0]:
                lines.append(("ansigreen bold", f"  > {opt}\n"))
            else:
                lines.append(("", f"    {opt}\n"))
        return lines

    app: Application[int] = Application(
        layout=Layout(Window(FormattedTextControl(_get_text))),
        key_bindings=kb,
        full_screen=False,
    )
    return _tty_run(app)


class ConfigureWizard:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def build_config(
        self, model: str,
        telegram_enabled: bool = False, telegram_token: str = "",
        telegram_allowed_users: list[str] | None = None,
        slack_enabled: bool = False, slack_bot_token: str = "",
        slack_app_token: str = "", slack_channels: list[str] | None = None,
        slack_allowed_users: list[str] | None = None,
    ) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "agent": {
                "workspace": str(self.workspace),
                "model": model,
            },
        }
        channels: dict[str, Any] = {}
        if telegram_enabled:
            channels["telegram"] = {
                "enabled": True,
                "token": telegram_token,
                "allowed_users": telegram_allowed_users or [],
            }
        if slack_enabled:
            channels["slack"] = {
                "enabled": True,
                "bot_token": slack_bot_token,
                "app_token": slack_app_token,
                "channels": slack_channels or [],
                "allowed_users": slack_allowed_users or [],
            }
        if channels:
            cfg["channels"] = channels
        return cfg

    def save_config(self, config: dict[str, Any]) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        path = self.workspace / "config.json"
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
