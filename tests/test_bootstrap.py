from pathlib import Path
from soleclaw.core.bootstrap import needs_bootstrap, run_bootstrap


def test_needs_bootstrap_true(tmp_path):
    assert needs_bootstrap(tmp_path) is True


def test_needs_bootstrap_false(tmp_path):
    (tmp_path / "SOUL.md").write_text("# Soul\n")
    assert needs_bootstrap(tmp_path) is False


def test_run_bootstrap_creates_files(tmp_path):
    run_bootstrap(tmp_path)

    assert (tmp_path / "SOUL.md").exists()
    assert "genuinely helpful" in (tmp_path / "SOUL.md").read_text()

    assert (tmp_path / "USER.md").exists()
    user = (tmp_path / "USER.md").read_text()
    assert "About Your Human" in user

    assert (tmp_path / "IDENTITY.md").exists()
    assert "Who Am I?" in (tmp_path / "IDENTITY.md").read_text()

    assert (tmp_path / "MEMORY.md").exists()
    assert (tmp_path / "memory").is_dir()

    assert (tmp_path / "AGENTS.md").exists()
    assert "Action Bias" in (tmp_path / "AGENTS.md").read_text()
    assert "Self-Evolution" in (tmp_path / "AGENTS.md").read_text()

    assert (tmp_path / "TOOLS.md").exists()
    assert (tmp_path / "BOOTSTRAP.md").exists()


def test_bootstrap_no_cli_prompts(tmp_path):
    run_bootstrap(tmp_path)
    user = (tmp_path / "USER.md").read_text()
    assert "About Your Human" in user
    assert "Alice" not in user
