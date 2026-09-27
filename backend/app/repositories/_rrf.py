"""Reciprocal Rank Fusion, shared by snippet search and note retrieval (ADR 0005).

score(item) = Σ over branches it appears in of 1 / (RRF_K + rank in that branch).
"""

from sqlalchemy import CTE, Subquery, func, literal, select, union_all

RRF_K = 60


def fuse(keyword: CTE | None, semantic: CTE | None) -> Subquery | None:
    """Each branch is a CTE of (id, rank). Returns (id, score, by_keyword, by_semantic)."""
    branches = [
        select(branch.c.id, branch.c.rank, literal(name).label("source"))
        for name, branch in (("keyword", keyword), ("semantic", semantic))
        if branch is not None
    ]
    if not branches:
        return None
    ranked = union_all(*branches).subquery("ranked")
    return (
        select(
            ranked.c.id,
            func.sum(1.0 / (RRF_K + ranked.c.rank)).label("score"),
            func.bool_or(ranked.c.source == "keyword").label("by_keyword"),
            func.bool_or(ranked.c.source == "semantic").label("by_semantic"),
        )
        .group_by(ranked.c.id)
        .subquery("fused")
    )
