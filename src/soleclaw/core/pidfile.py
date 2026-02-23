from __future__ import annotations

import os
import signal
from pathlib import Path


def write_pid(workspace: Path) -> Path:
    p = workspace / "gateway.pid"
    p.write_text(str(os.getpid()))
    return p


def remove_pid(workspace: Path) -> None:
    p = workspace / "gateway.pid"
    p.unlink(missing_ok=True)


def read_pid(workspace: Path) -> int | None:
    p = workspace / "gateway.pid"
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except (ValueError, OSError):
        return None


def is_gateway_running(workspace: Path) -> bool:
    pid = read_pid(workspace)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        remove_pid(workspace)
        return False
