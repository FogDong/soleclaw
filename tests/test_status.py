import json
import os
from pathlib import Path


def _make_config(tmp_path, **overrides):
    data = {
        "agent": {"workspace": str(tmp_path), "model": "claude-sonnet-4-6"},
        "channels": {"telegram": {"enabled": True, "token": "123456:ABC", "allowed_users": ["alice"]}},
    }
    data.update(overrides)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))
    return p


def test_status_shows_gateway_running(tmp_path, capsys):
    cfg_path = _make_config(tmp_path)
    (tmp_path / "gateway.pid").write_text(str(os.getpid()))
    (tmp_path / "SOUL.md").write_text("# soul")
    (tmp_path / "USER.md").write_text("# user")

    from soleclaw.cli.commands import status
    status(config_path=cfg_path)

    out = capsys.readouterr().out
    assert "running" in out
    assert str(os.getpid()) in out


def test_status_shows_gateway_stopped(tmp_path, capsys):
    cfg_path = _make_config(tmp_path)
    (tmp_path / "SOUL.md").write_text("# soul")
    (tmp_path / "USER.md").write_text("# user")

    from soleclaw.cli.commands import status
    status(config_path=cfg_path)

    out = capsys.readouterr().out
    assert "stopped" in out


def test_status_shows_identity_not_set(tmp_path, capsys):
    cfg_path = _make_config(tmp_path)

    from soleclaw.cli.commands import status
    status(config_path=cfg_path)

    out = capsys.readouterr().out
    assert "not set up" in out


def test_status_shows_telegram_info(tmp_path, capsys):
    cfg_path = _make_config(tmp_path)

    from soleclaw.cli.commands import status
    status(config_path=cfg_path)

    out = capsys.readouterr().out
    assert "123456:A" in out
    assert "alice" in out
