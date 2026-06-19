"""对 LLM 生成的技能脚本做 AST 静态校验（进程级沙箱的第一道门）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass

MAX_CODE_BYTES = 48 * 1024
MAX_CODE_LINES = 800

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
        "tempfile",
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


@dataclass
class CodeValidationResult:
    ok: bool
    errors: list[str]


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


def validate_generated_code(code: str) -> CodeValidationResult:
    """校验生成脚本是否可安全执行。"""
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

    return CodeValidationResult(ok=not errors, errors=errors)


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
