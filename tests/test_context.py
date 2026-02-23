import json
from pathlib import Path
from soleclaw.core.context import ContextBuilder, SYSTEM_HEADER, BOOTSTRAP_HEADER


def test_system_prompt_includes_tool_library(tmp_path):
    (tmp_path / "SOUL.md").write_text("# SOUL")
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    lib = tmp_path / "tool-library" / "todo_manager"
    lib.mkdir(parents=True)
    (lib / "manifest.json").write_text(json.dumps({
        "name": "todo_manager", "description": "Manage todo items",
        "version": "0.1.0", "parameters": {"type": "object", "properties": {}},
    }))
    (lib / "tool.py").write_text("async def execute(args): return {}")
    ctx = ContextBuilder(tmp_path)
    prompt = ctx.build_system_prompt()
    assert "todo_manager" in prompt
    assert "Manage todo items" in prompt
    assert "run_user_tool" in prompt


def test_system_prompt_no_tool_library(tmp_path):
    (tmp_path / "SOUL.md").write_text("# SOUL")
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    ctx = ContextBuilder(tmp_path)
    prompt = ctx.build_system_prompt()
    assert "User Tools" not in prompt


def test_system_prompt_sdk_tool_names(tmp_path):
    assert "Write" in SYSTEM_HEADER
    assert "Edit" in SYSTEM_HEADER
    assert "Read" in SYSTEM_HEADER
    assert "Bash" in SYSTEM_HEADER
    assert "write_file" not in SYSTEM_HEADER
    assert "edit_file" not in SYSTEM_HEADER
    assert "read_file" not in SYSTEM_HEADER


def test_bootstrap_header(tmp_path):
    (tmp_path / "SOUL.md").write_text("# SOUL")
    (tmp_path / "BOOTSTRAP.md").write_text("# BOOTSTRAP")
    ctx = ContextBuilder(tmp_path)
    prompt = ctx.build_system_prompt()
    assert "BOOTSTRAP" in prompt
    assert "Edit or Write" in BOOTSTRAP_HEADER
    assert "edit_file" not in BOOTSTRAP_HEADER
    assert "write_file" not in BOOTSTRAP_HEADER
