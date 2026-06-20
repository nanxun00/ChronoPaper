"""产物质检单元测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.skills.artifact_inspection.inspectors.pptx import inspect_pptx
from src.services.skills.pptx_quality import parse_target_slide_count


class ArtifactInspectionTests(unittest.TestCase):
    def test_parse_slide_count(self) -> None:
        self.assertEqual(parse_target_slide_count("规划13张PPT"), 13)

    def test_inspect_missing_pptx(self) -> None:
        result = inspect_pptx(Path("nonexistent/deck.pptx"), query="13张")
        self.assertFalse(result.ok)


class LazyDeckValidationTests(unittest.TestCase):
    def test_reject_five_slide_template_script(self) -> None:
        from src.services.skills.code_validator import validate_generated_code

        script_path = ROOT / "data/skills/user/nature-paper2ppt/.generated/run_ROVwLoAXXVEHLuTq.py"
        if not script_path.is_file():
            self.skipTest("sample generated script missing")
        code = script_path.read_text(encoding="utf-8")
        result = validate_generated_code(
            code,
            skill_id="nature-paper2ppt",
            query="规划13张PPT",
        )
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
