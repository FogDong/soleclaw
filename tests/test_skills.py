from pathlib import Path
from soleclaw.skills.loader import SkillsLoader


def test_parse_frontmatter(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: A test skill\nalways: false\n---\n\n# Body\nHello")
    loader = SkillsLoader(workspace_skills=tmp_path / "skills")
    meta = loader.get_metadata("test-skill")
    assert meta["name"] == "test-skill"
    assert meta["always"] == "false"


def test_list_skills(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: desc\n---\n\nBody")
    loader = SkillsLoader(workspace_skills=tmp_path / "skills")
    skills = loader.list_skills()
    assert any(s["name"] == "my-skill" for s in skills)


def test_build_summary(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "s1"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: s1\ndescription: skill one\n---\n\nBody")
    loader = SkillsLoader(workspace_skills=tmp_path / "skills")
    summary = loader.build_summary()
    assert "s1" in summary
    assert "skill one" in summary
