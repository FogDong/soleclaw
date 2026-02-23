from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from ..tools.library.schema import validate_manifest


def validate_generated_tool(tool_dir: Path) -> list[str]:
    errors = []
    manifest_path = tool_dir / "manifest.json"
    tool_path = tool_dir / "tool.py"

    if not manifest_path.exists():
        errors.append("Missing manifest.json")
        return errors
    if not tool_path.exists():
        errors.append("Missing tool.py")
        return errors

    manifest = json.loads(manifest_path.read_text())
    errors.extend(validate_manifest(manifest))

    spec = importlib.util.spec_from_file_location("_check", tool_path)
    if not spec or not spec.loader:
        errors.append("Cannot load tool.py")
        return errors
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        errors.append(f"tool.py import error: {e}")
        return errors

    if not hasattr(mod, "execute"):
        errors.append("tool.py missing execute() function")

    return errors
