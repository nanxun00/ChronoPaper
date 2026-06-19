"""生成脚本校验单元测试。"""
from __future__ import annotations

import unittest

from src.services.skills.code_validator import validate_generated_code


class SkillCodeValidatorTests(unittest.TestCase):
    def test_allow_simple_pptx_script(self) -> None:
        code = """
from pathlib import Path
from pptx import Presentation

out = Path("output")
out.mkdir(parents=True, exist_ok=True)
prs = Presentation()
prs.slides.add_slide(prs.slide_layouts[0])
prs.save(out / "demo.pptx")
"""
        result = validate_generated_code(code)
        self.assertTrue(result.ok, result.errors)

    def test_reject_subprocess(self) -> None:
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = validate_generated_code(code)
        self.assertFalse(result.ok)
        self.assertTrue(any("subprocess" in e for e in result.errors))

    def test_reject_os_system(self) -> None:
        code = "import os\nos.system('echo hi')"
        result = validate_generated_code(code)
        self.assertFalse(result.ok)

    def test_reject_eval(self) -> None:
        code = 'eval("1+1")'
        result = validate_generated_code(code)
        self.assertFalse(result.ok)

    def test_reject_syntax_error(self) -> None:
        result = validate_generated_code("def foo(:\n  pass")
        self.assertFalse(result.ok)
        self.assertTrue(any("语法" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
