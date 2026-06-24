"""Skill 脚本执行器单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.skills.script_runner import list_skill_scripts, run_skill_script


class SkillScriptRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "demo-skill"
        scripts = self.root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "hello.py").write_text(
            'import sys\nprint("ok", sys.argv[1])\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_list_scripts(self) -> None:
        paths = list_skill_scripts(self.root)
        self.assertEqual(paths, ["scripts/hello.py"])

    def test_run_script_success(self) -> None:
        result = run_skill_script(self.root, "scripts/hello.py", ["world"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok world", result.stdout)

    def test_reject_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            run_skill_script(self.root, "scripts/../hello.py", [])

    def test_reject_outside_scripts(self) -> None:
        (self.root / "evil.py").write_text("print(1)", encoding="utf-8")
        with self.assertRaises(ValueError):
            run_skill_script(self.root, "evil.py", [])

    def test_reject_shell_metachar_in_args(self) -> None:
        with self.assertRaises(ValueError):
            run_skill_script(self.root, "scripts/hello.py", ["a;rm"])


if __name__ == "__main__":
    unittest.main()
