"""Hybrid retrieval: BM25 + Pinecone dense + Reciprocal Rank Fusion."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.clients.nebius import get_nebius
from app.clients.pinecone_client import get_pinecone_store
from app.config import get_settings
from app.events.bus import event_bus
from app.rag.bm25_store import get_bm25_store
from app.rag.rrf import reciprocal_rank_fusion


def hybrid_search(
    question: str,
    policy_id: str,
    *,
    run_id: Optional[str] = None,
    top_k_bm25: Optional[int] = None,
    top_k_dense: Optional[int] = None,
    top_k_rrf: Optional[int] = None,
) -> Dict[str, Any]:
    """Run filtered BM25 + dense retrieval and fuse with RRF."""
    settings = get_settings()
    k_bm25 = top_k_bm25 or settings.top_k_bm25
    k_dense = top_k_dense or settings.top_k_dense
    k_rrf = top_k_rrf or settings.top_k_rrf

    if run_id:
        event_bus.emit(
            run_id,
            "retrieval_started",
            status="running",
            node_id="hybrid_retrieval",
            input_summary={"question": question, "policy_id": policy_id},
        )
        event_bus.emit(
            run_id,
            "node_started",
            status="running",
            node_id="bm25_search",
            input_summary={"query": question, "top_k": k_bm25, "policy_id": policy_id},
        )

    bm25 = get_bm25_store()
    bm25_hits = bm25.search(question, top_k=k_bm25, policy_id=policy_id)

    if run_id:
        event_bus.emit(
            run_id,
            "node_completed",
            status="completed",
            node_id="bm25_search",
            output_summary={
                "count": len(bm25_hits),
                "top_ids": [h.get("chunk_id") for h in bm25_hits[:3]],
                "scores": [h.get("bm25_score") for h in bm25_hits[:3]],
            },
        )
        event_bus.emit(
            run_id,
            "node_started",
            status="running",
            node_id="embeddings",
            input_summary={"model": settings.nebius_embed_model},
        )

    nebius = get_nebius()
    vectors = nebius.embed([question])
    query_vec = vectors[0]

    if run_id:
        event_bus.emit(
            run_id,
            "node_completed",
            status="completed",
            node_id="embeddings",
            output_summary={"dimension": len(query_vec)},
        )
        event_bus.emit(
            run_id,
            "node_started",
            status="running",
            node_id="pinecone_search",
            input_summary={"top_k": k_dense, "filter": {"policy_id": policy_id}},
        )

    pinecone = get_pinecone_store()
    dense_hits_raw = pinecone.query(
        vector=query_vec,
        top_k=k_dense,
        filter={"policy_id": {"$eq": policy_id}},
    )
    dense_hits: List[Dict[str, Any]] = []
    for hit in dense_hits_raw:
        meta = hit.get("metadata") or {}
        dense_hits.append(
            {
                "chunk_id": hit["id"],
                "score": hit["score"],
                "pinecone_score": hit["score"],
                **meta,
            }
        )

    if run_id:
        event_bus.emit(
            run_id,
            "node_completed",
            status="completed",
            node_id="pinecone_search",
            output_summary={
                "count": len(dense_hits),
                "top_ids": [h.get("chunk_id") for h in dense_hits[:3]],
                "scores": [h.get("pinecone_score") for h in dense_hits[:3]],
            },
        )
        event_bus.emit(
            run_id,
            "node_started",
            status="running",
            node_id="rrf_fusion",
            input_summary={"k": settings.rrf_k, "lists": 2},
        )

    fused = reciprocal_rank_fusion(
        [bm25_hits, dense_hits],
        k=settings.rrf_k,
        top_k=k_rrf,
    )

    # Optional rerank placeholder (disabled by default)
    if settings.enable_rerank:
        fused = fused  # no-op MVP hook

    citations = []
    for row in fused:
        citations.append(
            {
                "document_name": row.get("source_filename") or row.get("document_id"),
                "section": row.get("section"),
                "page_number": row.get("page_number"),
                "excerpt": (row.get("chunk_text") or "")[:500],
                "chunk_id": row.get("chunk_id"),
                "score": row.get("rrf_score"),
            }
        )

    result = {
        "policy_id": policy_id,
        "question": question,
        "bm25_results": bm25_hits,
        "pinecone_results": dense_hits,
        "rrf_results": fused,
        "citations": citations,
        "evidence_sufficient": len(fused) > 0,
    }

    if run_id:
        event_bus.emit(
            run_id,
            "node_completed",
            status="completed",
            node_id="rrf_fusion",
            output_summary={
                "count": len(fused),
                "top_ids": [h.get("chunk_id") for h in fused[:3]],
                "rrf_scores": [h.get("rrf_score") for h in fused[:3]],
            },
        )
        event_bus.emit(
            run_id,
            "retrieval_completed",
            status="completed",
            node_id="hybrid_retrieval",
            output_summary={
                "bm25": len(bm25_hits),
                "pinecone": len(dense_hits),
                "rrf": len(fused),
            },
        )

    return result
