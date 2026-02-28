from __future__ import annotations
from pathlib import Path
from typing import Any


class SkillsLoader:
    def __init__(self, workspace_skills: Path | None = None, builtin_skills: Path | None = None, tool_library: Path | None = None):
        self.workspace_skills = workspace_skills
        self.builtin_skills = builtin_skills or Path(__file__).parent / "builtin"
        self.tool_library = tool_library

    def list_skills(self) -> list[dict[str, Any]]:
        skills = []
        seen: set[str] = set()
        for source, path in self._skill_dirs():
            if path.name in seen:
                continue
            seen.add(path.name)
            meta = self._parse_frontmatter(path / "SKILL.md")
            if meta:
                skills.append({"name": meta.get("name", path.name), "source": source, "path": str(path), **meta})
        return skills

    def get_metadata(self, name: str) -> dict[str, Any]:
        for _, path in self._skill_dirs():
            if path.name == name:
                return self._parse_frontmatter(path / "SKILL.md") or {}
        return {}

    def load_skill(self, name: str) -> str | None:
        for _, path in self._skill_dirs():
            if path.name == name:
                skill_file = path / "SKILL.md"
                if skill_file.exists():
                    return skill_file.read_text()
        return None

    def get_always_skills(self) -> list[str]:
        return [s["name"] for s in self.list_skills() if s.get("always") == "true"]

    def build_summary(self) -> str:
        lines = ["<skills>"]
        for s in self.list_skills():
            lines.append(f'  <skill name="{s["name"]}" description="{s.get("description", "")}" path="{s["path"]}" />')
        lines.append("</skills>")
        return "\n".join(lines)

    def _skill_dirs(self):
        if self.tool_library and self.tool_library.exists():
            for d in sorted(self.tool_library.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    yield "tool", d
        if self.workspace_skills and self.workspace_skills.exists():
            for d in sorted(self.workspace_skills.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    yield "workspace", d
        if self.builtin_skills and self.builtin_skills.exists():
            for d in sorted(self.builtin_skills.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    yield "builtin", d

    @staticmethod
    def _parse_frontmatter(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        lines = path.read_text().split("\n")
        if not lines or lines[0].strip() != "---":
            return None
        meta: dict[str, Any] = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        return meta
