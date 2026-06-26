"""Skill 脚本规划：nature-citation 固定内置脚本、禁止 codegen。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.skills.generated_runner import should_attempt_codegen
from src.services.skills.registry import SkillRecord
from src.services.skills.script_planner import (
    _infer_nature_citation_format,
    _nature_citation_plan,
    maybe_run_skill_scripts,
)


def _citation_record(root: Path) -> SkillRecord:
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "nature_citation.py").write_text("# stub\n", encoding="utf-8")
    return SkillRecord(
        id="nature-citation",
        name="Nature Citation",
        description="test",
        path=root,
        source="user",
        enabled=True,
    )


class NatureCitationPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.record = _citation_record(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_infer_format_defaults_to_ris(self) -> None:
        self.assertEqual(_infer_nature_citation_format("帮我加引用"), "ris")
        self.assertEqual(_infer_nature_citation_format("export endnote file"), "enw")

    def test_nature_citation_plan_writes_input_and_args(self) -> None:
        query = "引言 " + ("类器官成像分析需要准确分割。" * 20)
        plan = _nature_citation_plan(
            query,
            self.record,
            run_id="testRun123",
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan["script"], "scripts/nature_citation.py")
        self.assertEqual(plan.get("_timeout_sec"), 300)
        self.assertIn("--text-file", plan["args"])
        self.assertIn("--format", plan["args"])
        self.assertIn("ris", plan["args"])
        input_path = self.root / "input" / "runs" / "testRun123" / "manuscript.txt"
        self.assertTrue(input_path.is_file())
        self.assertIn("类器官", input_path.read_text(encoding="utf-8"))

    def test_nature_citation_skips_meta_query(self) -> None:
        plan = _nature_citation_plan("这个技能是什么", self.record, run_id="meta")
        self.assertIsNone(plan)

    def test_should_not_codegen_for_nature_citation(self) -> None:
        self.assertFalse(
            should_attempt_codegen("写引言加引用", self.record, builtin_ran=False)
        )

    @patch("src.services.skills.script_planner.run_skill_script")
    def test_maybe_run_skips_codegen_loop(self, mock_run) -> None:
        from src.services.skills.script_runner import ScriptRunResult

        mock_run.return_value = ScriptRunResult(
            script="scripts/nature_citation.py",
            argv=["python", "nature_citation.py"],
            returncode=0,
            stdout="Reference output: references.ris",
            stderr="",
        )
        query = "请为以下引言找 Nature 系列引用并导出 RIS\n" + ("MorphoMask 分割类器官。" * 15)
        ctx, runs, pending = maybe_run_skill_scripts(
            query,
            self.record,
            MagicMock(),
            run_id="runABC",
            allow_codegen=True,
        )
        self.assertIsNone(pending)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["script"], "scripts/nature_citation.py")
        self.assertIsNotNone(ctx)
        mock_run.assert_called_once()
        with patch("src.services.skills.script_planner.run_codegen_loop") as mock_codegen:
            maybe_run_skill_scripts(
                query,
                self.record,
                MagicMock(),
                run_id="runDEF",
                allow_codegen=True,
            )
            mock_codegen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
