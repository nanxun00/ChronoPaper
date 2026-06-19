"""技能文献输入同步单元测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.skills.input_sync import (
    cleanup_stale_literature_assets,
    collect_paper_ids_from_meta,
    sync_literature_to_skill,
)


class SkillInputSyncTests(unittest.TestCase):
    def test_collect_paper_ids(self) -> None:
        meta = {
            "cited_literature": [{"arxiv_id": "2301.00001"}],
            "bind_paper_id": "2301.00002",
        }
        ids = collect_paper_ids_from_meta(meta)
        self.assertEqual(ids, ["2301.00001", "2301.00002"])

    def test_sync_pdf_and_render(self) -> None:
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        with tempfile.TemporaryDirectory() as tmp:
            uploads = Path(tmp) / "uploads" / "papers" / "2301_00001"
            uploads.mkdir(parents=True)
            pdf_path = uploads / "paper.pdf"
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "hello figure test")
            doc.save(pdf_path)
            doc.close()

            skill_root = Path(tmp) / "skill"
            skill_root.mkdir()

            with patch("src.services.skills.input_sync.resolve_paper_pdf_file", return_value=str(pdf_path)):
                ctx = sync_literature_to_skill(skill_root, ["2301.00001"])

            self.assertEqual(len(ctx.pdf_rels), 1)
            self.assertTrue((skill_root / ctx.pdf_rels[0]).is_file())
            self.assertGreater(len(ctx.figure_rels), 0)
            block = ctx.to_prompt_block()
            self.assertIn("add_picture", block)
            self.assertIn("output/assets/figures", block)
            self.assertIn("勿 glob", block)

    def test_cleanup_stale_literature_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_root = Path(tmp) / "skill"
            fig_dir = skill_root / "output" / "assets" / "figures"
            fig_dir.mkdir(parents=True)
            (fig_dir / "2301.00002_p001.png").write_bytes(b"png")
            (fig_dir / "2301.00001_p001.png").write_bytes(b"png")
            stale_pdf_dir = skill_root / "input" / "papers" / "2301.00002"
            stale_pdf_dir.mkdir(parents=True)
            (stale_pdf_dir / "paper.pdf").write_bytes(b"pdf")

            cleanup_stale_literature_assets(skill_root, ["2301.00001"])

            self.assertFalse((fig_dir / "2301.00002_p001.png").exists())
            self.assertTrue((fig_dir / "2301.00001_p001.png").exists())
            self.assertFalse(stale_pdf_dir.exists())


if __name__ == "__main__":
    unittest.main()
