"""Codegen 审批流程单元测试。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.services.skills.code_security_review import SecurityReviewResult
from src.services.skills.code_validator import classify_validation_errors, validate_generated_code


class CodegenApprovalFlowTests(unittest.TestCase):
    def test_classify_reviewable_vs_hard(self) -> None:
        hard, reviewable, quality = classify_validation_errors(
            [
                "第 1 行：禁止 import subprocess",
                "第 5 行：禁止 shutil.rmtree",
                "脚本仅创建约 3 张幻灯片，少于要求的 8 张",
            ]
        )
        self.assertEqual(len(hard), 1)
        self.assertEqual(len(reviewable), 1)
        self.assertEqual(len(quality), 1)

    @patch("src.services.skills.codegen_approval.create_pending_approval")
    @patch("src.services.skills.code_security_review.review_generated_code_security")
    def test_validate_node_creates_pending_when_llm_approves(
        self, mock_review, mock_create
    ) -> None:
        from src.services.skills.codegen_graph import _node_validate, CodegenGraphContext
        from src.services.skills.registry import SkillRecord
        from pathlib import Path

        mock_review.return_value = SecurityReviewResult(
            approved=True,
            summary="仅在 output 下清理临时目录",
            risks=["可能误删 output 内文件"],
        )
        mock_create.return_value = "cap-test123"

        record = SkillRecord(
            id="nature-figure",
            name="figure",
            description="",
            source="user",
            enabled=True,
            path=Path("data/skills/user/nature-figure"),
        )
        ctx = CodegenGraphContext(
            record=record,
            query="画图",
            model=MagicMock(),
            run_id="run1",
            user_id="u1",
            input_context="",
            max_rounds=3,
        )
        code = "import shutil\nshutil.rmtree('output/runs/run1/tmp', ignore_errors=True)\n"
        state = {"round_num": 1, "code": code}
        out = _node_validate(state, {"configurable": {"ctx": ctx}})
        self.assertEqual(out.get("route"), "pending_approval")
        self.assertIsNotNone(ctx.loop_result.pending_approval)
        self.assertEqual(ctx.loop_result.pending_approval["approval_id"], "cap-test123")


if __name__ == "__main__":
    unittest.main()
