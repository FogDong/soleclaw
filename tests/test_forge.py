import json
from pathlib import Path
from soleclaw.forge.validator import validate_generated_tool
from soleclaw.forge.lifecycle import install_tool, list_tools, remove_tool


def test_validate_good_tool(tmp_path: Path):
    tool_dir = tmp_path / "good-tool"
    tool_dir.mkdir()
    (tool_dir / "manifest.json").write_text(json.dumps({
        "name": "good-tool", "description": "works", "version": "1.0.0",
        "parameters": {"type": "object", "properties": {}},
    }))
    (tool_dir / "tool.py").write_text("async def execute(args: dict) -> dict:\n    return {'ok': True}\n")
    (tool_dir / "SKILL.md").write_text("---\nname: good-tool\ndescription: works\nalways: false\n---\n# Good Tool\nUse when needed.\n")
    errors = validate_generated_tool(tool_dir)
    assert len(errors) == 0


def test_validate_missing_execute(tmp_path: Path):
    tool_dir = tmp_path / "bad-tool"
    tool_dir.mkdir()
    (tool_dir / "manifest.json").write_text(json.dumps({
        "name": "bad-tool", "description": "broken", "version": "1.0.0",
        "parameters": {"type": "object", "properties": {}},
    }))
    (tool_dir / "tool.py").write_text("x = 1\n")
    errors = validate_generated_tool(tool_dir)
    assert any("execute" in e for e in errors)


def test_lifecycle_install_and_list(tmp_path: Path):
    lib = tmp_path / "tool-library"
    src = tmp_path / "src-tool"
    src.mkdir()
    (src / "manifest.json").write_text(json.dumps({
        "name": "my-tool", "description": "test", "version": "1.0.0",
        "parameters": {"type": "object", "properties": {}},
    }))
    (src / "tool.py").write_text("async def execute(args): return {}\n")

    install_tool(src, lib)
    tools = list_tools(lib)
    assert "my-tool" in tools

    remove_tool("my-tool", lib)
    tools = list_tools(lib)
    assert "my-tool" not in tools
