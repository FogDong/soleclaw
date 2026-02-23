from __future__ import annotations
import json
import shutil
from pathlib import Path


def install_tool(source_dir: Path, library_path: Path) -> None:
    manifest = json.loads((source_dir / "manifest.json").read_text())
    name = manifest["name"]
    dest = library_path / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source_dir, dest)


def remove_tool(name: str, library_path: Path) -> None:
    dest = library_path / name
    if dest.exists():
        shutil.rmtree(dest)


def list_tools(library_path: Path) -> list[str]:
    if not library_path.exists():
        return []
    tools = []
    for d in library_path.iterdir():
        if d.is_dir() and (d / "manifest.json").exists():
            manifest = json.loads((d / "manifest.json").read_text())
            tools.append(manifest["name"])
    return tools
