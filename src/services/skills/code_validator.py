"""对 LLM 生成的技能脚本做 AST 静态校验（进程级沙箱的第一道门）。"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

MAX_CODE_BYTES = 48 * 1024
MAX_CODE_LINES = 800

_PAGE_PNG_PATTERN = re.compile(r"_p\d{3}\.png", re.IGNORECASE)
_ADD_SLIDE_RE = re.compile(r"\.add_slide\s*\(")
_READ_FIRST_N_PAGES_RE = re.compile(r"range\s*\(\s*min\s*\(\s*5\s*,", re.IGNORECASE)
_PAPER2PPT_PLACEHOLDER_PHRASES = (
    "方法1：具体",
    "方法2：创新",
    "本文研究的主要问题和意义",
    "当前领域存在的挑战或空白",
    "主要实验发现",
    "研究的主要目标",
    "本文采用的主要技术路线",
)
_FULLPAGE_SLIDE_HINTS = (
    "add_full_image_slide",
    "width=Inches(13.333), height=Inches(7.5)",
    "width=prs.slide_width, height=prs.slide_height",
)

_BLOCKED_MODULES = frozenset(
    {
        "subprocess",
        "socket",
        "multiprocessing",
        "ctypes",
        "pickle",
        "shelve",
        "telnetlib",
        "ftplib",
        "smtplib",
        "http",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "paramiko",
        "pty",
        "fcntl",
        "resource",
        "signal",
        "mmap",
        "importlib",
    }
)

_BLOCKED_CALLS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "input",
        "breakpoint",
    }
)

_BLOCKED_OS_ATTRS = frozenset(
    {
        "system",
        "popen",
        "spawn",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "fork",
        "kill",
        "remove",
        "unlink",
        "rmdir",
        "removedirs",
        "chmod",
        "chown",
    }
)

_BLOCKED_SHUTIL_ATTRS = frozenset({"rmtree", "move", "chown", "copytree"})

_HARD_ERROR_RE = re.compile(
    r"禁止 (import|调用 (eval|exec|compile|__import__|input|breakpoint)|"
    r"os\.(system|popen|spawn|fork|kill|execl|execle|execlp|execlpe|execv|execve|execvp|execvpe|spawn))"
)
_REVIEWABLE_ERROR_RE = re.compile(
    r"禁止 (os\.(remove|unlink|rmdir|removedirs|chmod|chown)|shutil\.|动态访问 os\.(remove|unlink|rmdir|chmod|chown))"
)


@dataclass
class CodeValidationResult:
    ok: bool
    errors: list[str]
    hard_block_errors: list[str] | None = None
    reviewable_errors: list[str] | None = None
    quality_errors: list[str] | None = None

    @property
    def needs_user_approval(self) -> bool:
        return bool(self.reviewable_errors) and not self.hard_block_errors

    @property
    def is_hard_block(self) -> bool:
        return bool(self.hard_block_errors)


def classify_validation_errors(errors: list[str]) -> tuple[list[str], list[str], list[str]]:
    """将校验错误分为：硬拦截 / 可审查放行 / 质量规则。"""
    hard: list[str] = []
    reviewable: list[str] = []
    quality: list[str] = []
    for err in errors:
        if (
            _HARD_ERROR_RE.search(err)
            or err.startswith("语法错误")
            or err.startswith("代码超过")
        ):
            hard.append(err)
        elif _REVIEWABLE_ERROR_RE.search(err):
            reviewable.append(err)
        else:
            quality.append(err)
    return hard, reviewable, quality


class _CodeValidator(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._check_module(node.module, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in _BLOCKED_CALLS:
            self.errors.append(f"第 {node.lineno} 行：禁止调用 {name}()")
        if name == "getattr" and len(node.args) >= 2:
            const = _str_constant(node.args[1])
            if const in _BLOCKED_OS_ATTRS:
                self.errors.append(f"第 {node.lineno} 行：禁止动态访问 os.{const}")
        if name.startswith("os.") and name.split(".", 1)[1] in _BLOCKED_OS_ATTRS:
            self.errors.append(f"第 {node.lineno} 行：禁止 os.{name.split('.', 1)[1]}")
        if name.startswith("shutil.") and name.split(".", 1)[1] in _BLOCKED_SHUTIL_ATTRS:
            self.errors.append(f"第 {node.lineno} 行：禁止 shutil.{name.split('.', 1)[1]}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        root = _attr_root_name(node)
        if root == "os" and node.attr in _BLOCKED_OS_ATTRS:
            self.errors.append(f"第 {node.lineno} 行：禁止 os.{node.attr}")
        if root == "shutil" and node.attr in _BLOCKED_SHUTIL_ATTRS:
            self.errors.append(f"第 {node.lineno} 行：禁止 shutil.{node.attr}")
        self.generic_visit(node)

    def _check_module(self, module: str, lineno: int) -> None:
        root = module.split(".", 1)[0]
        if root in _BLOCKED_MODULES:
            self.errors.append(f"第 {lineno} 行：禁止 import {module}")


def validate_generated_code(
    code: str,
    *,
    skill_id: str | None = None,
    query: str = "",
    allow_reviewable: bool = False,
) -> CodeValidationResult:
    """校验生成脚本是否可安全执行。allow_reviewable=True 时忽略可审查的高危项（用户已批准）。"""
    errors: list[str] = []
    text = (code or "").strip()
    if not text:
        return CodeValidationResult(False, ["代码为空"])

    if len(text.encode("utf-8")) > MAX_CODE_BYTES:
        errors.append(f"代码超过 {MAX_CODE_BYTES} 字节上限")
    if text.count("\n") + 1 > MAX_CODE_LINES:
        errors.append(f"代码超过 {MAX_CODE_LINES} 行上限")

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return CodeValidationResult(False, [f"语法错误：{exc.msg} (line {exc.lineno})"])

    visitor = _CodeValidator()
    visitor.visit(tree)
    errors.extend(visitor.errors)
    errors.extend(_check_pptx_screenshot_patterns(text))
    if skill_id == "nature-paper2ppt":
        errors.extend(_check_paper2ppt_code_quality(text, query))

    hard, reviewable, quality = classify_validation_errors(errors)
    effective = hard + quality
    if not allow_reviewable:
        effective = errors
    return CodeValidationResult(
        ok=not effective,
        errors=errors,
        hard_block_errors=hard,
        reviewable_errors=reviewable,
        quality_errors=quality,
    )


def _check_paper2ppt_code_quality(code: str, query: str) -> list[str]:
    """拒绝页数过少、只读前 5 页、模板占位内容的 paper2ppt 脚本。"""
    from src.services.skills.pptx_quality import min_required_slides, parse_target_slide_count

    errors: list[str] = []
    target = parse_target_slide_count(query)
    min_slides = min_required_slides(target)
    slide_calls = len(_ADD_SLIDE_RE.findall(code))
    if slide_calls < min_slides:
        errors.append(
            f"脚本仅创建约 {slide_calls} 张幻灯片，少于要求的 {min_slides} 张；"
            f"请按论文写 {target} 张左右的结构化内容页"
        )
    if _READ_FIRST_N_PAGES_RE.search(code):
        errors.append("禁止只读取 PDF 前 5 页；请读取全文或至少摘要+方法+结果+讨论")
    placeholder_hits = [p for p in _PAPER2PPT_PLACEHOLDER_PHRASES if p in code]
    if len(placeholder_hits) >= 2:
        errors.append(
            "检测到模板占位文案（"
            + "、".join(placeholder_hits[:3])
            + "）；bullet 须来自论文具体内容"
        )
    return errors


def _check_pptx_screenshot_patterns(code: str) -> list[str]:
    """拒绝把 PDF 整页预览拼成 PPT 的偷懒脚本。"""
    errors: list[str] = []
    page_png_hits = len(_PAGE_PNG_PATTERN.findall(code))
    if page_png_hits >= 3:
        errors.append(
            "检测到批量引用 PDF 整页预览 PNG（*_pNNN.png）；"
            "请改为结构化幻灯片（标题+bullet），仅插入论文配图"
        )
    for hint in _FULLPAGE_SLIDE_HINTS:
        if hint in code:
            errors.append(f"禁止整页贴图模式（{hint}）；请写结构化 slide 内容")
            break
    return errors


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _attr_root_name(node)
    return ""


def _attr_root_name(node: ast.Attribute) -> str:
    cur: ast.expr = node
    parts: list[str] = []
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    parts.reverse()
    return ".".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


def _str_constant(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
