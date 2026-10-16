"""Reciprocal Rank Fusion."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[Dict[str, Any]]],
    k: int = 60,
    id_key: str = "chunk_id",
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """RRF(d) = sum(1 / (k + rank(d))) with 1-based ranks.

    Deduplicates by stable chunk ID and returns fused ranked results.
    """
    scores: Dict[str, float] = {}
    payloads: Dict[str, Dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            cid = item.get(id_key) or item.get("id")
            if not cid:
                continue
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in payloads:
                payloads[cid] = dict(item)
            else:
                # Keep richer metadata / higher source score when available
                payloads[cid].update({kk: vv for kk, vv in item.items() if vv is not None})

    fused = []
    for cid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        row = payloads[cid]
        row["chunk_id"] = cid
        row["rrf_score"] = score
        fused.append(row)
        if len(fused) >= top_k:
            break
    return fused
