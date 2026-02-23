import json
from pathlib import Path
from soleclaw.tools.library.registry import LibraryRegistry
from soleclaw.tools.library.schema import validate_manifest


def test_validate_manifest_valid():
    manifest = {
        "name": "test-tool",
        "description": "A test tool",
        "version": "1.0.0",
        "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
    }
    errors = validate_manifest(manifest)
    assert len(errors) == 0


def test_validate_manifest_missing_fields():
    errors = validate_manifest({"name": "test"})
    assert len(errors) > 0


async def test_library_registry_discover(tmp_path: Path):
    tool_dir = tmp_path / "tool-library" / "my-tool"
    tool_dir.mkdir(parents=True)
    (tool_dir / "manifest.json").write_text(json.dumps({
        "name": "my-tool",
        "description": "does stuff",
        "version": "1.0.0",
        "parameters": {"type": "object", "properties": {}},
    }))
    (tool_dir / "tool.py").write_text(
        "async def execute(args: dict) -> dict:\n    return {'ok': True}\n"
    )

    reg = LibraryRegistry(tmp_path / "tool-library")
    reg.discover()
    assert reg.has("my-tool")
    result = await reg.execute("my-tool", {})
    assert result["ok"] is True
