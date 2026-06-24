"""抓取任务可选枚举（与前端 constants 对齐，供 LLM 规划校验）。"""

ARXIV_CATEGORIES: frozenset[str] = frozenset({
    "cs.AI", "cs.LG", "cs.NE", "cs.CL", "cs.IR", "cs.MA",
    "cs.CV", "cs.MM", "cs.GR", "cs.SD",
    "cs.DB", "cs.DC", "cs.DS", "cs.NI", "cs.PF", "cs.SI",
    "cs.SE", "cs.CR", "cs.HC", "cs.RO", "cs.PL",
    "cs.CY", "cs.ET", "cs.IT", "cs.OH",
})

OPENREVIEW_VENUES: frozenset[str] = frozenset({
    "ICLR.cc/2025/Conference/-/Submission",
    "ICLR.cc/2024/Conference/-/Submission",
    "ICLR.cc/2023/Conference/-/Submission",
    "NeurIPS.cc/2024/Conference/-/Submission",
    "NeurIPS.cc/2023/Conference/-/Submission",
    "ICML.cc/2024/Conference/-/Submission",
    "ICML.cc/2023/Conference/-/Submission",
    "ACL.org/2024/Conference/-/Submission",
    "EMNLP/2024/Conference/-/Submission",
})

CRAWL_SOURCES: frozenset[str] = frozenset({"arxiv", "openreview", "openalex"})
OPENALEX_VENUE_TYPES: frozenset[str] = frozenset({"conference", "journal"})
OPENALEX_CCF_RANKS: frozenset[str] = frozenset({"A", "B", "C"})
