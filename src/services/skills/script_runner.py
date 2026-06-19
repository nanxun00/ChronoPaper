"""在技能目录内安全执行 scripts/*.py（进程级约束，非 Docker 沙箱）。"""
from __future__ import annotations

import re
import subprocess
import sys
import os
from dataclasses import dataclass
from pathlib import Path

from src.utils.logging_config import setup_logger

logger = setup_logger("SkillScriptRunner")

DEFAULT_TIMEOUT_SEC = 120
MAX_OUTPUT_BYTES = 64 * 1024
_BLOCKED_ARG_RE = re.compile(r"[;&|`$<>]")
_NETWORK_ALLOWED_SCRIPTS = frozenset(
    {
        "academic_search.py",
        "format-converter.py",
        "nature_citation.py",
        "preflight.py",
    }
)


@dataclass
class ScriptRunResult:
    script: str
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_context_block(self) -> str:
        parts = [
            f"脚本: {self.script}",
            f"命令: {' '.join(self.argv)}",
            f"退出码: {self.returncode}",
        ]
        if self.timed_out:
            parts.append("状态: 超时")
        if self.stdout.strip():
            parts.append(f"stdout:\n{self.stdout.strip()}")
        if self.stderr.strip():
            parts.append(f"stderr:\n{self.stderr.strip()}")
        return "\n".join(parts)


def list_skill_scripts(skill_root: Path) -> list[str]:
    """返回技能包内可执行脚本相对路径，如 scripts/academic_search.py。"""
    scripts_dir = skill_root / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [
        f"scripts/{p.name}"
        for p in sorted(scripts_dir.glob("*.py"))
        if p.is_file()
    ]


def _validate_args(args: list[str]) -> list[str]:
    cleaned: list[str] = []
    for arg in args or []:
        text = str(arg)
        if _BLOCKED_ARG_RE.search(text):
            raise ValueError(f"参数含非法字符: {text}")
        cleaned.append(text)
    return cleaned


def _resolve_script(skill_root: Path, script_rel: str) -> Path:
    rel = script_rel.replace("\\", "/").lstrip("/")
    if not rel.startswith("scripts/"):
        raise ValueError(f"仅允许执行 scripts/ 下的脚本: {script_rel}")
    if ".." in Path(rel).parts:
        raise ValueError(f"非法脚本路径: {script_rel}")

    skill_root = skill_root.resolve()
    script = (skill_root / rel).resolve()
    try:
        script.relative_to(skill_root)
    except ValueError as exc:
        raise ValueError(f"脚本路径越界: {script_rel}") from exc
    if script.suffix != ".py" or not script.is_file():
        raise ValueError(f"脚本不存在或类型不支持: {script_rel}")
    return script


def run_skill_script(
    skill_root: Path,
    script_rel: str,
    args: list[str] | None = None,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_network: bool | None = None,
) -> ScriptRunResult:
    """
    在 skill_root 下执行 python scripts/xxx.py [args...]。
    不使用 shell=True，cwd 锁定在技能目录。
    """
    skill_root = skill_root.resolve()
    script = _resolve_script(skill_root, script_rel)
    cli_args = _validate_args(args or [])

    if allow_network is None:
        allow_network = script.name in _NETWORK_ALLOWED_SCRIPTS

    argv = [sys.executable, str(script), *cli_args]
    env = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PATH": os.environ.get("PATH", ""),
    }
    if allow_network:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "OPENALEX_MAILTO", "CROSSREF_MAILTO"):
            val = os.environ.get(key)
            if val:
                env[key] = val

    logger.info("Run skill script %s args=%s network=%s", script_rel, cli_args, allow_network)
    timed_out = False
    try:
        proc = subprocess.run(
            argv,
            cwd=str(skill_root),
            capture_output=True,
            timeout=timeout_sec,
            shell=False,
            env=env,
        )
        stdout = _truncate_output(proc.stdout)
        stderr = _truncate_output(proc.stderr)
        return ScriptRunResult(
            script=script_rel,
            argv=argv,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = _truncate_output(exc.stdout or b"")
        stderr = _truncate_output(exc.stderr or b"")
        stderr = (stderr + "\n(执行超时)").strip()
        return ScriptRunResult(
            script=script_rel,
            argv=argv,
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
        )


def _truncate_output(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        text = text.encode("utf-8")[: MAX_OUTPUT_BYTES - 80].decode("utf-8", errors="replace")
        text += "\n…（输出已截断）"
    return text
