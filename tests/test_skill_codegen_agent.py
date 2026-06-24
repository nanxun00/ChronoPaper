"""多轮 codegen 单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.skills.codegen_agent import (
    codegen_loop_context_block,
    extract_python_code,
    run_codegen_loop,
)
from src.services.skills.codegen_common import CodegenLoopResult
from src.services.skills.generated_runner import GeneratedRunRecord
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult


class CodegenAgentTests(unittest.TestCase):
    def test_extract_python_from_fence(self) -> None:
        text = "说明\n```python\nprint('hi')\n```\n"
        self.assertEqual(extract_python_code(text), "print('hi')")

    def test_extract_longest_fence(self) -> None:
        text = "```python\nx=1\n```\n```python\nfrom pathlib import Path\nPath('output').mkdir()\n```"
        code = extract_python_code(text)
        self.assertIn("pathlib", code or "")

    def test_context_block_success(self) -> None:
        rec = GeneratedRunRecord(
            purpose="test",
            script_rel=".generated/run_x.py",
            result=ScriptRunResult(
                script=".generated/run_x.py",
                argv=[],
                returncode=0,
                stdout="ok",
                stderr="",
            ),
        )
        loop = CodegenLoopResult(
            rounds=[rec],
            succeeded=True,
            artifacts=[{"name": "a.pptx", "url": "/u", "kind": "file", "size": 100}],
        )
        ctx = codegen_loop_context_block(loop)
        self.assertIn("成功", ctx)
        self.assertIn("产物质检", ctx)
        self.assertIn("a.pptx", ctx)

    def test_codegen_loop_success_with_mock_model(self) -> None:
        code = """
from pathlib import Path
Path("output").mkdir(parents=True, exist_ok=True)
(Path("output") / "deck.md").write_text("# hi", encoding="utf-8")
"""
        model = MagicMock()
        model.predict.return_value = MagicMock(content=f"```python\n{code}\n```")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            root.mkdir()
            record = SkillRecord(
                id="nature-paper2ppt",
                name="nature-paper2ppt",
                description="",
                path=root.resolve(),
            )
            with patch(
                "src.services.skills.codegen_graph.collect_skill_artifacts",
                return_value=[
                    {
                        "name": "deck.md",
                        "url": "/uploads/skills/u/r1/output/deck.md",
                        "kind": "file",
                        "size": 4,
                    }
                ],
            ), patch(
                "src.services.skills.codegen_graph.inspect_skill_deliverables",
            ) as mock_inspect:
                from src.services.skills.artifact_inspection.models import SkillInspectionReport

                mock_inspect.return_value = SkillInspectionReport(
                    skill_id="nature-paper2ppt",
                    run_id="r1",
                    ok=True,
                )
                loop = run_codegen_loop(
                    record,
                    "做PPT",
                    model,
                    run_id="r1",
                    user_id="u",
                    max_rounds=2,
                )
        self.assertTrue(loop.succeeded)
        self.assertEqual(len(loop.rounds), 1)


if __name__ == "__main__":
    unittest.main()
