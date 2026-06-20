"""技能 Agent 工具：仅限技能目录内的安全读文件。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.skills.loader import _read_fragment, _truncate

_MAX_READ_CHARS = 16_000


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, str]


@dataclass
class ToolResult:
    name: str
    ok: bool
    summary: str
    content: str = ""


def resolve_skill_read_path(skill_root: Path, rel_path: str) -> Path | None:
    """解析并校验相对路径，禁止目录穿越。"""
    raw = (rel_path or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/"):
        return None

    skill_root = skill_root.resolve()
    if len(raw) > 2 and raw[1] == ":":
        try:
            raw = Path(raw).resolve().relative_to(skill_root).as_posix()
        except ValueError:
            return None

    if raw.startswith("../"):
        base = skill_root.parent
        rel = raw[3:]
    else:
        if ".." in raw.split("/"):
            return None
        base = skill_root
        rel = raw

    target = (base / rel).resolve()
    shared_root = skill_root.parent / "_shared"
    if not (_is_under(target, skill_root) or _is_under(target, shared_root)):
        return None
    if not target.is_file():
        return None
    return target


def _is_under(path: Path, root: Path) -> bool:
    if not root.exists():
        return False
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def execute_read(skill_root: Path, rel_path: str) -> ToolResult:
    """read 工具：读取技能包内 markdown/yaml 等文本。"""
    name = "read"
    rel = (rel_path or "").strip()
    if not rel:
        return ToolResult(name, False, "缺少 file_path 参数")

    # 绝对路径尝试转为相对 skill_root
    if len(rel) > 2 and rel[1] == ":":
        try:
            rel = Path(rel).resolve().relative_to(skill_root.resolve()).as_posix()
        except ValueError:
            return ToolResult(name, False, f"禁止读取技能目录外文件：{rel_path}")

    text = _read_fragment(skill_root, rel)
    if not text:
        resolved = resolve_skill_read_path(skill_root, rel)
        if resolved is None:
            return ToolResult(name, False, f"文件不存在或路径非法：{rel}")
        try:
            text = resolved.read_text(encoding="utf-8").strip()
        except OSError as exc:
            return ToolResult(name, False, f"读取失败：{exc}")

    if len(text) > _MAX_READ_CHARS:
        text = _truncate(text, _MAX_READ_CHARS)
    return ToolResult(
        name,
        True,
        f"已读取 {rel}（{len(text)} 字符）",
        content=text,
    )


def execute_tool(skill_root: Path, call: ToolCall) -> ToolResult:
    if call.name.lower() == "read":
        return execute_read(skill_root, call.arguments.get("file_path", ""))
    return ToolResult(call.name, False, f"未知工具：{call.name}")


def format_tool_results(results: list[ToolResult]) -> str:
    parts: list[str] = ["## 工具执行结果（仅供你继续推理，勿原样复述给用户）"]
    for res in results:
        parts.append(f"\n### {res.name}: {res.summary}")
        if res.content:
            parts.append(res.content)
        elif not res.ok:
            parts.append(f"（失败）{res.summary}")
    parts.append(
        "\n请根据以上内容与用户问题继续。"
        "若无需再读文件，请用中文直接回复用户（勿再输出 <function=...>）。"
    )
    return "\n".join(parts)
