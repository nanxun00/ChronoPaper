"""paper2ppt 页数解析与校验测试。"""
from __future__ import annotations

import unittest

from src.services.skills.pptx_quality import (
    min_required_slides,
    parse_target_slide_count,
)
from src.services.skills.code_validator import validate_generated_code


class PptxQualityTests(unittest.TestCase):
    def test_parse_slide_count_from_query(self) -> None:
        self.assertEqual(parse_target_slide_count("帮我做13张PPT"), 13)
        self.assertEqual(parse_target_slide_count("规划了 13 张幻灯片"), 13)
        self.assertEqual(parse_target_slide_count("随便做个ppt"), 12)

    def test_min_required_slides(self) -> None:
        self.assertEqual(min_required_slides(13), 11)
        self.assertEqual(min_required_slides(10), 10)

    def test_reject_lazy_five_slide_template(self) -> None:
        code = open(
            "data/skills/user/nature-paper2ppt/.generated/run_ROVwLoAXXVEHLuTq.py",
            encoding="utf-8",
        ).read()
        result = validate_generated_code(
            code,
            skill_id="nature-paper2ppt",
            query="规划13张PPT",
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("幻灯片" in e or "占位" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
