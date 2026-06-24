"""CCF 推荐目录常见会议/期刊名称匹配（用于 OpenAlex venue 回填）。"""
from __future__ import annotations

# 子串匹配（venue display_name 小写后包含即命中）
CCF_VENUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "A": (
        "neurips", "nips", "neural information processing",
        "icml", "international conference on machine learning",
        "iclr", "international conference on learning representations",
        "cvpr", "computer vision and pattern recognition",
        "iccv", "international conference on computer vision",
        "eccv", "european conference on computer vision",
        "acl", "association for computational linguistics",
        "emnlp", "empirical methods in natural language",
        "naacl", "north american chapter of the acl",
        "aaai", "association for the advancement of artificial intelligence",
        "ijcai", "international joint conference on artificial intelligence",
        "kdd", "knowledge discovery and data mining",
        "sigir", "research and development in information retrieval",
        "www", "world wide web conference",
        "osdi", "operating systems design",
        "sosp", "symposium on operating systems principles",
        "nsdi", "networked systems design",
        "sigcomm", "data communication",
        "mobicom", "mobile computing and networking",
        "ieee transactions on pattern analysis",
        "tpami", "journal of machine learning research", "jmlr",
        "nature machine intelligence", "nature methods",
        "miccai", "medical image computing and computer assisted",
        "medical image analysis",
    ),
    "B": (
        "icassp", "interspeech", "coling", "aistats",
        "wacv", "bmvc", "accv",
        "icde", "vldb", "sigmod", "icdm", "pakdd", "wsdm",
        "cikm", "recsys", "icmr",
        "usenix atc", "fast", "eurosys",
        "ieee transactions on neural networks", "tnnls",
        "neural networks", "pattern recognition",
        "artificial intelligence", "ai journal",
        "computational linguistics",
        "ieee transactions on medical imaging",
        "international symposium on biomedical imaging", "isbi",
    ),
    "C": (
        "iconip", "ijcnn", "icann",
        "icpr", "icip", "icme",
        "icse", "fse", "ase",
        "icnp", "infocom",
        "expert systems with applications",
        "neurocomputing", "applied intelligence",
    ),
}


def match_ccf_rank(venue_name: str) -> str | None:
    """根据 venue 名称返回 CCF A/B/C，未命中返回 None。"""
    v = (venue_name or "").lower().strip()
    if not v:
        return None
    for rank in ("A", "B", "C"):
        for pattern in CCF_VENUE_PATTERNS[rank]:
            if pattern in v:
                return rank
    return None


def venue_matches_ccf_ranks(venue_name: str, allowed_ranks: set[str]) -> bool:
    if not allowed_ranks:
        return True
    rank = match_ccf_rank(venue_name)
    if rank is None:
        return False
    return rank in allowed_ranks


def openreview_venue_text(meta: dict) -> str:
    """拼接 OpenReview 候选的会议/邀请信息，供 CCF 匹配。"""
    parts = [
        meta.get("venue") or "",
        meta.get("venue_display") or "",
        meta.get("openreview_invitation") or "",
    ]
    cats = meta.get("categories")
    if isinstance(cats, list) and cats:
        parts.append(str(cats[0]))
    return " ".join(str(p) for p in parts if p)


def annotate_openreview_ccf(meta: dict) -> str | None:
    rank = match_ccf_rank(openreview_venue_text(meta))
    if rank:
        meta["venue_rank"] = rank
    return rank


def meta_matches_ccf_ranks(meta: dict, allowed_ranks: set[str]) -> bool:
    if not allowed_ranks:
        return True
    rank = meta.get("venue_rank") or annotate_openreview_ccf(meta)
    if rank is None:
        return False
    return rank in allowed_ranks
