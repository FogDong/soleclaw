from pathlib import Path

from soleclaw.cli.configure import ConfigureWizard


def test_wizard_init(tmp_path: Path):
    wiz = ConfigureWizard(workspace=tmp_path)
    assert wiz.workspace == tmp_path


def test_wizard_build_config(tmp_path: Path):
    wiz = ConfigureWizard(workspace=tmp_path)
    config = wiz.build_config(model="claude-sonnet-4-6")
    assert config["agent"]["model"] == "claude-sonnet-4-6"
    assert config["agent"]["workspace"] == str(tmp_path)


def test_wizard_save_config(tmp_path: Path):
    wiz = ConfigureWizard(workspace=tmp_path)
    config = wiz.build_config(model="claude-sonnet-4-6")
    wiz.save_config(config)
    assert (tmp_path / "config.json").exists()


def test_wizard_build_config_with_telegram(tmp_path: Path):
    wiz = ConfigureWizard(workspace=tmp_path)
    config = wiz.build_config(
        model="claude-sonnet-4-6",
        telegram_enabled=True, telegram_token="123:ABC",
        telegram_allowed_users=["alice", "bob"],
    )
    tg = config["channels"]["telegram"]
    assert tg["enabled"] is True
    assert tg["token"] == "123:ABC"
    assert tg["allowed_users"] == ["alice", "bob"]


def test_wizard_build_config_no_telegram(tmp_path: Path):
    wiz = ConfigureWizard(workspace=tmp_path)
    config = wiz.build_config(model="claude-sonnet-4-6")
    assert "channels" not in config
