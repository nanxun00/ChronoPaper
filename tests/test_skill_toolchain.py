"""技能工具链依赖探测。"""
from __future__ import annotations

import unittest

from src.services.skills.toolchain import check_skill_toolchain


class SkillToolchainTests(unittest.TestCase):
    def test_core_packages_importable(self) -> None:
        report = check_skill_toolchain()
        if report.missing:
            self.fail("缺少技能依赖：\n" + "\n".join(report.missing))


if __name__ == "__main__":
    unittest.main()
