import pytest
from pathlib import Path
from soleclaw.memory.local import LocalMemoryBackend


@pytest.mark.asyncio
async def test_get_context_reads_memory_md(tmp_path: Path):
    mem = LocalMemoryBackend(tmp_path)
    (tmp_path / "MEMORY.md").write_text("# Memory\n\n- User name is Alice\n")
    ctx = await mem.get_context()
    assert "Alice" in ctx


@pytest.mark.asyncio
async def test_get_context_empty_when_no_file(tmp_path: Path):
    mem = LocalMemoryBackend(tmp_path)
    ctx = await mem.get_context()
    assert ctx == ""


@pytest.mark.asyncio
async def test_store_appends_to_daily_log(tmp_path: Path):
    mem = LocalMemoryBackend(tmp_path)
    await mem.store("pref1", "User prefers dark mode", {"type": "preference"})
    logs = list((tmp_path / "memory").glob("*.md"))
    assert len(logs) == 1
    content = logs[0].read_text()
    assert "dark mode" in content
    assert "pref1" in content


@pytest.mark.asyncio
async def test_search_finds_in_memory_md(tmp_path: Path):
    mem = LocalMemoryBackend(tmp_path)
    (tmp_path / "MEMORY.md").write_text("# Memory\n\nUser likes Python\n")
    results = await mem.search("Python")
    assert len(results) == 1
    assert "Python" in results[0].content


@pytest.mark.asyncio
async def test_search_finds_in_daily_logs(tmp_path: Path):
    mem = LocalMemoryBackend(tmp_path)
    daily = tmp_path / "memory" / "2026-01-15.md"
    daily.write_text("# 2026-01-15\n\n## meeting\nDiscussed API redesign\n")
    results = await mem.search("API redesign")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_creates_directories(tmp_path: Path):
    workspace = tmp_path / "new_workspace"
    mem = LocalMemoryBackend(workspace)
    assert workspace.exists()
    assert (workspace / "memory").exists()
