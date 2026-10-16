"""REST + SSE API routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import run_investigation
from app.clients.nebius import get_nebius
from app.clients.pinecone_client import get_pinecone_store
from app.config import get_settings
from app.data.loader import (
    claim_summary,
    load_claims,
    load_evaluation_questions,
    load_policies,
)
from app.data.models import InvestigateRequest, InvestigateResponse
from app.events.bus import event_bus
from app.rag.bm25_store import get_bm25_store

router = APIRouter()


@router.get("/health")
async def health() -> Dict[str, Any]:
    settings = get_settings()
    nebius_status = {"ok": False, "error": "not checked"}
    pinecone_status = {"ok": False, "error": "not checked"}
    bm25_ok = False
    try:
        if settings.nebius_api_key and not settings.nebius_api_key.startswith("your_"):
            nebius_status = get_nebius().health_check()
    except Exception as exc:  # noqa: BLE001
        nebius_status = {"ok": False, "error": str(exc)}
    try:
        if settings.pinecone_api_key and not settings.pinecone_api_key.startswith("your_"):
            pinecone_status = get_pinecone_store().health_check()
    except Exception as exc:  # noqa: BLE001
        pinecone_status = {"ok": False, "error": str(exc)}
    try:
        bm25_ok = bool(get_bm25_store().chunks)
    except Exception:  # noqa: BLE001
        bm25_ok = False

    backend_ok = True
    return {
        "status": "ok" if backend_ok else "degraded",
        "backend": {"ok": backend_ok},
        "nebius": nebius_status,
        "pinecone": pinecone_status,
        "bm25": {"ok": bm25_ok, "chunks": len(get_bm25_store().chunks) if bm25_ok else 0},
        "models": {
            "chat": settings.nebius_chat_model,
            "embed": settings.nebius_embed_model,
        },
        "report_builder": "v5_plain_dict",
        "code_stamp": "source-alias-fix-20261015",
    }


@router.get("/claims")
async def list_claims() -> List[Dict[str, Any]]:
    return [c.model_dump() for c in load_claims().values()]


@router.get("/claims/{claim_id}")
async def get_claim_endpoint(claim_id: str) -> Dict[str, Any]:
    try:
        return claim_summary(claim_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/policies")
async def list_policies() -> List[Dict[str, Any]]:
    return [p.model_dump() for p in load_policies().values()]


@router.get("/evaluation/questions")
async def evaluation_questions() -> List[Dict[str, Any]]:
    return load_evaluation_questions()


@router.get("/example-questions")
async def example_questions(claim_id: Optional[str] = None) -> List[str]:
    portfolio = [
        "How many policies are active?",
        "List all policies and their statuses.",
        "How many claims are in the dataset?",
        "Which policy IDs are expired?",
    ]
    claim_qs = [
        "Was the policy within its effective date range on the accident date?",
        "Is collision coverage listed? What is the deductible?",
        "Which policy clauses may apply, and are there relevant exclusions?",
        "Analyze the repair estimate for duplicates and compute illustrative net amount.",
        "Are required documents missing? What should the adjuster request next?",
        "Find similar claims and produce a full investigation report for human review.",
    ]
    cid = (claim_id or "").strip()
    if not cid or cid.lower() in {"none", "portfolio", "n/a"}:
        return portfolio
    return [f"For {cid}: {q}" for q in claim_qs]


def _run_sync(run_id: str, claim_id: str, question: str) -> None:
    try:
        run_investigation(run_id, claim_id, question)
    except Exception as exc:  # noqa: BLE001
        event_bus.emit(run_id, "workflow_failed", status="failed", error=str(exc))
        event_bus.update_run(run_id, status="failed", error=str(exc))


@router.post("/investigate", response_model=InvestigateResponse)
async def investigate(
    body: InvestigateRequest, background_tasks: BackgroundTasks
) -> InvestigateResponse:
    claims = load_claims()
    raw_claim = (body.claim_id or "").strip()
    portfolio_mode = (not raw_claim) or raw_claim.lower() in {"none", "portfolio", "n/a"}
    claim_id = "portfolio" if portfolio_mode else raw_claim
    if not portfolio_mode and claim_id not in claims:
        raise HTTPException(status_code=404, detail=f"Unknown claim_id: {claim_id}")

    settings = get_settings()
    try:
        settings.require_credentials()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = event_bus.create_run(claim_id, body.question)

    async def _bg() -> None:
        await asyncio.to_thread(_run_sync, run_id, claim_id, body.question)

    background_tasks.add_task(_bg)
    return InvestigateResponse(
        run_id=run_id,
        claim_id=claim_id,
        status="started",
        stream_url=f"/api/runs/{run_id}/events",
    )


@router.get("/runs")
async def list_runs() -> List[Dict[str, Any]]:
    return event_bus.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> Dict[str, Any]:
    run = event_bus.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return run


@router.get("/runs/{run_id}/events")
async def stream_events(
    run_id: str, last_event_id: Optional[str] = Query(default=None)
):
    if not event_bus.get_run(run_id):
        raise HTTPException(status_code=404, detail="Unknown run_id")

    async def event_generator():
        async for ev in event_bus.subscribe(run_id, last_event_id=last_event_id):
            yield {
                "id": ev.event_id,
                "event": ev.event_type,
                "data": json.dumps(ev.to_dict()),
            }

    return EventSourceResponse(event_generator())


@router.get("/workflow/nodes")
async def workflow_nodes() -> List[Dict[str, Any]]:
    """Static architecture node catalog for the React Flow canvas."""
    return [
        {"id": "start_trigger", "label": "Start Trigger", "icon": "play", "group": "flow"},
        {"id": "claim_intake", "label": "Claim Intake", "icon": "file-text", "group": "intake"},
        {"id": "langgraph_agent", "label": "LangGraph Agent", "icon": "brain", "group": "agent"},
        {"id": "nebius_llm", "label": "Nebius LLM", "icon": "sparkles", "group": "agent"},
        {"id": "claim_lookup", "label": "Claim Lookup", "icon": "search", "group": "tools"},
        {"id": "claim_database", "label": "Claim Database", "icon": "database", "group": "tools"},
        {"id": "portfolio_lookup", "label": "Portfolio Lookup", "icon": "database", "group": "tools"},
        {"id": "hybrid_retrieval", "label": "Hybrid Retrieval", "icon": "git-merge", "group": "rag"},
        {"id": "bm25_search", "label": "BM25 Search", "icon": "search", "group": "rag"},
        {"id": "embeddings", "label": "Embeddings", "icon": "vector", "group": "rag"},
        {"id": "pinecone_search", "label": "Pinecone Search", "icon": "pinecone", "group": "rag"},
        {"id": "rrf_fusion", "label": "RRF Fusion", "icon": "merge", "group": "rag"},
        {"id": "coverage_check", "label": "Coverage Check", "icon": "shield-check", "group": "tools"},
        {"id": "estimate_analysis", "label": "Estimate Analysis", "icon": "calculator", "group": "tools"},
        {"id": "missing_documents", "label": "Missing Documents", "icon": "folder-search", "group": "tools"},
        {"id": "similar_claims", "label": "Similar Claims", "icon": "files", "group": "tools"},
        {"id": "report_generator", "label": "Output Report Generator", "icon": "file-check", "group": "output"},
        {"id": "human_review", "label": "Human Review", "icon": "user-check", "group": "output"},
    ]
