"""生成脚本执行单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.skills.generated_runner import (
    execute_generated_code,
    run_generated_script,
    should_attempt_codegen,
    write_generated_script,
)
from src.services.skills.registry import SkillRecord


class SkillGeneratedRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "demo-skill"
        self.root.mkdir(parents=True)
        self.record = SkillRecord(
            id="nature-paper2ppt",
            name="nature-paper2ppt",
            description="demo",
            path=self.root.resolve(),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_should_attempt_codegen_for_paper2ppt(self) -> None:
        self.assertTrue(
            should_attempt_codegen("帮我做组会PPT", self.record, builtin_ran=False)
        )

    def test_should_not_codegen_when_builtin_ran(self) -> None:
        self.assertFalse(
            should_attempt_codegen("做PPT", self.record, builtin_ran=True)
        )

    def test_write_and_run_generated_script(self) -> None:
        code = """
from pathlib import Path
Path("output").mkdir(parents=True, exist_ok=True)
(Path("output") / "hello.txt").write_text("ok", encoding="utf-8")
"""
        script = write_generated_script(self.root, "run-1", code)
        result = run_generated_script(self.root, script)
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.root / "output" / "hello.txt").is_file())

    def test_execute_collects_artifacts(self) -> None:
        code = """
from pathlib import Path
Path("output").mkdir(parents=True, exist_ok=True)
(Path("output") / "deck.md").write_text("# slides", encoding="utf-8")
"""
        with patch("src.services.skills.generated_runner.collect_skill_artifacts") as mock_collect:
            mock_collect.return_value = [
                {
                    "name": "deck.md",
                    "url": "/uploads/skills/u1/r1/output/deck.md",
                    "kind": "file",
                    "size": 8,
                }
            ]
            rec = execute_generated_code(
                self.record,
                code,
                "写大纲",
                run_id="r1",
                user_id="u1",
            )
        self.assertEqual(rec.result.returncode, 0)
        self.assertEqual(len(rec.artifacts or []), 1)
        mock_collect.assert_called_once()

    def test_reject_invalid_code(self) -> None:
        rec = execute_generated_code(
            self.record,
            "import subprocess\nsubprocess.run(['x'])",
            "恶意",
            run_id="r2",
            user_id="u1",
        )
        self.assertIsNotNone(rec.validation_errors)
        self.assertNotEqual(rec.result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
