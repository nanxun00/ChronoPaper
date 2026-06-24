"""Skill Agent 单元测试。"""
from pathlib import Path

from src.services.skills.agent.runner import _user_visible_prefix
from src.services.skills.agent.tool_parser import parse_tool_calls, strip_tool_calls
from src.services.skills.agent.tools import execute_read, resolve_skill_read_path


def test_user_visible_prefix_stops_at_tool_marker():
    partial = "正在查看参考文档。\n<function=read>"
    assert _user_visible_prefix(partial) == "正在查看参考文档。"
    full = partial + "\n<parameter=file_path>a.md</parameter>\n</function>"
    assert _user_visible_prefix(full) == "正在查看参考文档。"


def test_parse_mimo_read_call():
    text = """我先查看参考文档。
<function=read>
<parameter=file_path>static/fragments/backend/python.md</parameter>
</function>
"""
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "read"
    assert calls[0].arguments["file_path"] == "static/fragments/backend/python.md"


def test_strip_tool_calls():
    raw = "说明\n<function=read>\n<parameter=file_path>a.md</parameter>\n</function>"
    assert strip_tool_calls(raw) == "说明"


def test_resolve_skill_read_path_blocks_traversal(tmp_path: Path):
    skill = tmp_path / "my-skill"
    skill.mkdir()
    (skill / "ok.md").write_text("hi", encoding="utf-8")
    assert resolve_skill_read_path(skill, "ok.md") is not None
    assert resolve_skill_read_path(skill, "../../etc/passwd") is None
    assert resolve_skill_read_path(skill, "missing.md") is None


def test_execute_read_existing_file(tmp_path: Path):
    skill = tmp_path / "fig"
    skill.mkdir()
    rel = "refs/chart.md"
    target = skill / rel
    target.parent.mkdir(parents=True)
    target.write_text("# Chart rules", encoding="utf-8")
    res = execute_read(skill, rel)
    assert res.ok
    assert "Chart rules" in res.content
