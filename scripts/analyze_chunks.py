import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.rag.indexing import _block_text, _map_block_type, chunk_paper_content_list, load_content_list
from src.services.rag.mineru_indexing import resolve_paper_content_list_path

pid = "doi:10.1016_j.neucom.2023.126295"
blocks = load_content_list(resolve_paper_content_list_path(pid))

lines = []
for i, b in enumerate(blocks):
    bt = _map_block_type(b)
    tx = _block_text(b)
    raw = str(b.get("type", ""))
    if bt == "table" or "table" in raw.lower() or (tx and "|" in tx[:200]) or tx.lower().startswith("table "):
        lines.append(f"{i}|{bt}|{raw}|{tx[:100]}")

rows = chunk_paper_content_list(blocks, kb_id="t", paper_id=pid)
table_chunks = [
    r for r in rows
    if r["block_type"] == "table" or re.search(r"Table\s*\d", r["chunk_text"][:80], re.I)
]

fig_chunks = [r for r in rows if re.search(r"\bFig\.?\s*\d", r["chunk_text"][:120], re.I)]
short = [r for r in rows if len(r["chunk_text"]) < 80]

out = ROOT / "tmp_analyze.txt"
parts = [
    f"raw_table_blocks={len(lines)}",
    f"total_chunks={len(rows)}",
    f"table_like_chunks={len(table_chunks)}",
    f"fig_chunks={len(fig_chunks)}",
    f"short_chunks={len(short)}",
    "RAW:",
    *lines[:40],
    "TABLE CHUNKS:",
]
parts += [f"len={len(r['chunk_text'])} type={r['block_type']} | {r['chunk_text'][:150]}" for r in table_chunks[:25]]
parts.append("FIG CHUNKS:")
parts += [f"len={len(r['chunk_text'])} | {r['chunk_text'][:150]}" for r in fig_chunks[:15]]
parts.append("SHORT:")
parts += [f"len={len(r['chunk_text'])} | {r['chunk_text'][:100]}" for r in short[:20]]
out.write_text("\n".join(parts), encoding="utf-8")
print("done", len(lines), len(rows), len(table_chunks))
