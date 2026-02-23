from pathlib import Path
from soleclaw.config.schema import Config, AgentConfig


def test_config_defaults():
    cfg = Config()
    assert cfg.agent.model == "claude-sonnet-4-6"
    assert cfg.agent.max_turns == 20
    assert not hasattr(cfg, "providers")


def test_config_no_provider_config():
    import soleclaw.config.schema as schema
    assert not hasattr(schema, "ProviderConfig")
    assert not hasattr(schema, "ProvidersConfig")


def test_config_load_missing_file(tmp_path):
    cfg = Config.load(tmp_path / "nonexistent.json")
    assert cfg.agent.model == "claude-sonnet-4-6"


def test_config_load_existing(tmp_path):
    import json
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"agent": {"model": "claude-opus-4-6", "max_turns": 10}}))
    cfg = Config.load(p)
    assert cfg.agent.model == "claude-opus-4-6"
    assert cfg.agent.max_turns == 10


def test_workspace_path():
    cfg = Config(agent={"workspace": "/tmp/test-ws"})
    assert cfg.workspace_path == Path("/tmp/test-ws")
