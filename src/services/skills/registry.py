"""Skill 注册表：扫描目录、解析 SKILL.md、管理启用状态。"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.utils.logging_config import setup_logger

logger = setup_logger("SkillRegistry")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SKILLS_DIR = _PROJECT_ROOT / "data" / "skills" / "user"
_STATE_FILE = _PROJECT_ROOT / "data" / "skills" / "state.json"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass
class SkillRecord:
    id: str
    name: str
    description: str
    path: Path
    version: str = ""
    enabled: bool = True
    source: str = "user"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "source": self.source,
        }


def _parse_skill_md(skill_md: Path) -> tuple[dict[str, Any], str]:
    text = skill_md.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
    body = text
    m = _FRONTMATTER_RE.match(text)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = text[m.end() :]
    return meta, body.strip()


def _load_state() -> dict[str, Any]:
    if not _STATE_FILE.exists():
        return {"disabled": []}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"disabled": []}


def _save_state(state: dict[str, Any]) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


_SKIP_ZIP_PARTS = {".git", "__MACOSX", "node_modules"}


def _discover_skill_dirs(root: Path) -> list[Path]:
    """在解压目录中查找含 SKILL.md 的技能包目录（支持 nature-skills 仓库嵌套结构）。"""
    found: dict[str, Path] = {}
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in _SKIP_ZIP_PARTS for part in skill_md.parts):
            continue
        skill_dir = skill_md.parent
        if skill_dir.name == "_shared":
            continue
        found.setdefault(skill_dir.name, skill_dir)
    return list(found.values())


def _discover_shared_dir(root: Path) -> Path | None:
    candidates = [
        p
        for p in root.rglob("_shared")
        if p.is_dir() and p.name == "_shared" and not any(part in _SKIP_ZIP_PARTS for part in p.parts)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: len(p.parts))


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


class SkillRegistry:
    _instance: SkillRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._skills: dict[str, SkillRecord] = {}
        self._loaded = False

    @classmethod
    def instance(cls) -> SkillRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        if not cls._instance._loaded:
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        disabled = set(_load_state().get("disabled") or [])
        found: dict[str, SkillRecord] = {}

        if _SKILLS_DIR.is_dir():
            for child in sorted(_SKILLS_DIR.iterdir()):
                if not child.is_dir():
                    continue
                if child.name == "_shared":
                    continue
                skill_md = child / "SKILL.md"
                if not skill_md.is_file():
                    continue
                try:
                    meta, _ = _parse_skill_md(skill_md)
                except OSError as exc:
                    logger.warning("Skip skill %s: %s", child.name, exc)
                    continue
                sid = str(meta.get("name") or child.name).strip()
                if not sid:
                    continue
                desc = str(meta.get("description") or "").strip()
                found[sid] = SkillRecord(
                    id=sid,
                    name=sid,
                    description=desc,
                    path=child.resolve(),
                    version=str(meta.get("version") or ""),
                    enabled=sid not in disabled,
                    source="user",
                )

        with self._lock:
            self._skills = found
            self._loaded = True
        logger.info("SkillRegistry loaded %d skills", len(found))
        self._apply_description_i18n()

    def _apply_description_i18n(self) -> None:
        from src.services.skills.description_i18n import apply_descriptions_to_registry

        apply_descriptions_to_registry(self)

    def _translate_descriptions(self, skill_ids: list[str] | None = None) -> None:
        from src.services.skills.description_i18n import translate_skill_descriptions

        translate_skill_descriptions(self, skill_ids=skill_ids)

    def list_all(self) -> list[SkillRecord]:
        return sorted(self._skills.values(), key=lambda s: s.id)

    def list_enabled(self) -> list[SkillRecord]:
        return [s for s in self.list_all() if s.enabled]

    def get(self, skill_id: str) -> SkillRecord | None:
        return self._skills.get(skill_id)

    def set_enabled(self, skill_id: str, enabled: bool) -> SkillRecord | None:
        rec = self._skills.get(skill_id)
        if not rec:
            return None
        state = _load_state()
        disabled = set(state.get("disabled") or [])
        if enabled:
            disabled.discard(skill_id)
        else:
            disabled.add(skill_id)
        state["disabled"] = sorted(disabled)
        _save_state(state)
        rec.enabled = enabled
        return rec

    def install_zip(self, zip_path: Path) -> list[SkillRecord]:
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        installed_ids: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    if ".." in Path(name).parts:
                        raise ValueError(f"非法路径: {name}")
                zf.extractall(tmp_root)

            skill_dirs = _discover_skill_dirs(tmp_root)
            if not skill_dirs:
                raise ValueError(
                    "zip 中未找到含 SKILL.md 的技能目录。"
                    "可上传单个技能目录、skills/ 文件夹，或完整的 nature-skills 仓库压缩包。"
                )

            shared = _discover_shared_dir(tmp_root)
            if shared:
                _copy_tree(shared, _SKILLS_DIR / "_shared")

            for skill_dir in skill_dirs:
                meta, _ = _parse_skill_md(skill_dir / "SKILL.md")
                skill_id = str(meta.get("name") or skill_dir.name).strip()
                if not skill_id:
                    continue
                _copy_tree(skill_dir, _SKILLS_DIR / skill_dir.name)
                installed_ids.append(skill_id)

        if not installed_ids:
            raise ValueError("zip 中未找到可安装的技能")

        self.reload()
        self._translate_descriptions(installed_ids)
        id_set = set(installed_ids)
        return [rec for rec in self.list_all() if rec.id in id_set]

def get_skill_registry() -> SkillRegistry:
    return SkillRegistry.instance()
