"""技能描述中文化单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.skills.description_i18n import (
    _needs_translation,
    _STATIC_ZH,
    translate_skill_descriptions,
)
from src.services.skills.registry import SkillRegistry, _save_state


class SkillDescriptionI18nTests(unittest.TestCase):
    def test_needs_translation(self) -> None:
        self.assertTrue(_needs_translation("Build full-paper Chinese-English side-by-side reader"))
        self.assertFalse(_needs_translation("生成全文中英文对照阅读稿"))

    def test_static_fallback_translate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp) / "user"
            skill_dir = skills_dir / "nature-reader"
            scripts = skill_dir / "scripts"
            scripts.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: nature-reader\ndescription: Build full-paper reader\n---\n",
                encoding="utf-8",
            )
            state_file = Path(tmp) / "state.json"
            _save_state({"disabled": []})

            reg = SkillRegistry.__new__(SkillRegistry)
            reg._skills = {}
            reg._loaded = True

            from src.services.skills import registry as reg_mod

            with patch.object(reg_mod, "_SKILLS_DIR", skills_dir), patch.object(
                reg_mod, "_STATE_FILE", state_file
            ), patch(
                "src.services.skills.description_i18n._get_chat_model",
                return_value=None,
            ):
                rec = reg_mod.SkillRecord(
                    id="nature-reader",
                    name="nature-reader",
                    description="Build full-paper reader",
                    path=skill_dir.resolve(),
                )
                reg._skills = {"nature-reader": rec}
                count = translate_skill_descriptions(reg, skill_ids=["nature-reader"])

            self.assertEqual(count, 1)
            self.assertEqual(rec.description, _STATIC_ZH["nature-reader"])


if __name__ == "__main__":
    unittest.main()
