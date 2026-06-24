"""技能产物收集单元测试。"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from src.services.skills.artifact_collector import (
    collect_skill_artifacts,
    snapshot_output_files,
)


class SkillArtifactCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.skill_root = Path(self.tmp.name) / "demo-skill"
        out = self.skill_root / "output"
        out.mkdir(parents=True)
        self.sample = out / "report.md"
        self.sample.write_text("# hello", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_snapshot_and_collect_new_file(self) -> None:
        before = snapshot_output_files(self.skill_root)
        self.assertIn("output/report.md", before)

        time.sleep(0.05)
        img = self.skill_root / "output" / "plot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")

        artifacts = collect_skill_artifacts(
            self.skill_root,
            before,
            "user1",
            "run-abc",
            since_ts=time.time() - 5,
        )
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "plot.png")
        self.assertEqual(artifacts[0]["kind"], "image")
        self.assertIn("/uploads/skills/user1/run-abc/", artifacts[0]["url"])

    def test_skip_unchanged_files(self) -> None:
        before = snapshot_output_files(self.skill_root)
        artifacts = collect_skill_artifacts(
            self.skill_root,
            before,
            "user1",
            "run-xyz",
        )
        self.assertEqual(artifacts, [])

    def test_collect_from_references_dir(self) -> None:
        before = snapshot_output_files(self.skill_root)
        refs = self.skill_root / "references"
        refs.mkdir()
        bib = refs / "paper.bib"
        bib.write_text("@article{}", encoding="utf-8")
        artifacts = collect_skill_artifacts(
            self.skill_root,
            before,
            "user1",
            "run-ref",
            since_ts=time.time() - 5,
        )
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "paper.bib")

    def test_collect_from_generated_output_dir(self) -> None:
        before = snapshot_output_files(self.skill_root)
        gen_out = self.skill_root / ".generated" / "output" / "runs" / "run1"
        gen_out.mkdir(parents=True)
        chart = gen_out / "model_comparison_bars.png"
        chart.write_bytes(b"\x89PNG\r\n\x1a\n")
        pdf = gen_out / "model_comparison_bars.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        artifacts = collect_skill_artifacts(
            self.skill_root,
            before,
            "user1",
            "run-gen",
            since_ts=time.time() - 5,
        )
        self.assertEqual(len(artifacts), 2)
        names = {a["name"] for a in artifacts}
        self.assertIn("model_comparison_bars.png", names)
        self.assertIn("model_comparison_bars.pdf", names)
        self.assertTrue(all(a["url"].startswith("/uploads/skills/user1/run-gen/output/") for a in artifacts))

    def test_skip_synced_input_figures(self) -> None:
        before = snapshot_output_files(self.skill_root)
        fig_dir = self.skill_root / "output" / "assets" / "figures"
        fig_dir.mkdir(parents=True)
        fig = fig_dir / "paper_p001.png"
        fig.write_bytes(b"\x89PNG\r\n\x1a\n")
        artifacts = collect_skill_artifacts(
            self.skill_root,
            before,
            "user1",
            "run-fig",
            since_ts=time.time() - 5,
        )
        self.assertEqual(artifacts, [])


if __name__ == "__main__":
    unittest.main()
